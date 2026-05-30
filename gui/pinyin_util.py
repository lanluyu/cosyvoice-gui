# coding: utf-8
"""多音字工具：本地 pypinyin 扫描 + 调用 LLM 结合上下文识别 + dict 格式解析。

「AI 扫描多音字」走 detect_heteronyms_llm（Qwen，结合上下文给正确读音）；
LLM 不可用时回退 scan_heteronyms（本地 pypinyin + 白名单，给默认读音草稿）。
parse_corrections 支持把 {"乐":"le4","差":"ci1"} 形式批量解析进纠音表。
"""
from __future__ import annotations

import ast
import json
import re

from dashscope_audio.config import Settings


def _is_han(ch: str) -> bool:
    """是否为 CJK 基本区汉字。"""
    return "一" <= ch <= "鿿"


# --------------------------------------------------------- 本地扫描（兜底）
def scan_heteronyms(text: str, *, strict: bool = True) -> list[tuple[str, str]]:
    """本地 pypinyin 扫描多音字，返回 [(字, 默认拼音), ...]，按首次出现去重保序。

    strict=True：仅返回常用多音字白名单内的字，噪音低；strict=False：按
    heteronym 判定全量召回。读音为默认值草稿，需人工按文意校对。
    """
    from pypinyin import Style, lazy_pinyin, pinyin

    from .heteronyms import COMMON_HETERONYMS

    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for ch in text:
        if not _is_han(ch) or ch in seen:
            continue
        if strict:
            if ch not in COMMON_HETERONYMS:
                continue
            seen.add(ch)
            py = lazy_pinyin(ch, style=Style.TONE3, neutral_tone_with_five=True)
            result.append((ch, py[0] if py else ""))
        else:
            seen.add(ch)
            readings = pinyin(ch, heteronym=True, style=Style.TONE3, errors="ignore")
            if readings and len(readings[0]) > 1:
                result.append((ch, readings[0][0]))
    return result


# --------------------------------------------------------- LLM 上下文识别
_HETERONYM_PROMPT = '''你是中文注音专家，尤其擅长古文与诗词的多音字判定。
任务：分析下面三引号内的文本，找出需要纠正读音的多音字，结合上下文给出在本文中的正确读音。
规则：
1. 只输出真正的多音字（现代汉语中有两个或以上读音的字），不要输出单音字。
2. 读音用带声调数字的拼音：声调 1-4，轻声用 5，ü 写作 v。例如 le4、cen1、ci1、de5、nv3。
3. 【关键】当同一个字在文中不同位置读音不同时，必须改用“包含该字的词语”来区分：text 填该词、pinyin 填整词读音（各字拼音用空格分隔）。例如“至于”读 zhi4 yu2、“于嗟”读 xu1 jie1。
4. 当某字在全文读音一致时，text 可只填该字。
5. 只输出一个 JSON 数组，不要任何解释、前后缀或代码块标记。每个元素形如 {"text": "至于", "pinyin": "zhi4 yu2"} 或 {"text": "乐", "pinyin": "le4"}。
文本：
"""
__TEXT__
"""'''


def detect_heteronyms_llm(
    settings: Settings,
    text: str,
    *,
    model: str | None = None,
    enable_thinking: bool = True,
) -> list[tuple[str, str]]:
    """调用 Qwen 结合上下文识别多音字，返回 [(字, 读音), ...]。

    依赖网络与 API Key；解析失败或无结果返回空列表（由调用方决定是否回退本地）。
    """
    from dashscope_audio import llm

    prompt = _HETERONYM_PROMPT.replace("__TEXT__", text)
    content = llm.chat(
        settings,
        prompt,
        model=model or llm.DEFAULT_MODEL,
        enable_thinking=enable_thinking,
    )
    return _parse_heteronym_json(content)


def _parse_heteronym_json(content: str) -> list[tuple[str, str]]:
    """从 LLM 回复中提取 JSON 数组并解析为 [(词或字, 读音)]，按 key 去重保序。

    兼容 text（词级，推荐）与 char（旧字级）两种字段名。
    """
    match = re.search(r"\[.*\]", content, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        key = str(item.get("text") or item.get("char") or "").strip()
        py = str(item.get("pinyin", "")).strip()
        if key and key not in seen:
            seen.add(key)
            result.append((key, py))
    return result


# --------------------------------------------------------- dict 格式解析
def parse_corrections(text: str) -> list[tuple[str, str]]:
    """解析 {"乐": "le4", "差": "ci1"} 形式（可带 corrections= 前缀）为 [(字, 拼音)]。

    用 ast.literal_eval 安全解析（不执行任意代码）；非法输入返回空列表。
    """
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        data = ast.literal_eval(match.group(0))
    except (ValueError, SyntaxError):
        return []
    if not isinstance(data, dict):
        return []
    return [
        (str(k).strip(), str(v).strip())
        for k, v in data.items()
        if str(k).strip()
    ]


def format_corrections(pairs: list[tuple[str, str]], name: str = "corrections") -> str:
    """把 [(字, 拼音)] 格式化为 Python dict 字面量文本（与 parse_corrections 互逆）。

    便于在界面里导出/复制后，直接粘回脚本或再次批量导入。
    """
    if not pairs:
        return f"{name} = {{}}"
    body = "\n".join(f'    "{k}": "{v}",' for k, v in pairs)
    return f"{name} = {{\n{body}\n}}"

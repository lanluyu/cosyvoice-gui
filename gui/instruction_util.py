# coding: utf-8
"""调用 LLM 根据文本内容与情感基调生成 TTS 风格指令（约 30 字）。

供「风格指令」Tab 的「AI 生成」按钮使用，结果填入 instruction 供 CosyVoice 合成。
复用 dashscope_audio.llm（与多音字识别同一 Qwen 调用链路）。
"""
from __future__ import annotations

from dashscope_audio.config import Settings

_INSTRUCTION_PROMPT = '''你是专业的语音合成导演。请根据下面三引号内文本的内容与情感基调，写一条用于 TTS 朗读的中文风格指令。
要求：
1. 约 30 字，简洁凝练。
2. 描述朗读的语气、情感、语速、停顿等，贴合文本的内容与基调。
3. 只输出指令本身，不要解释、不要加引号、不要任何前后缀。
文本：
"""
__TEXT__
"""'''


def generate_instruction(
    settings: Settings,
    text: str,
    *,
    model: str | None = None,
    enable_thinking: bool = True,
) -> str:
    """根据文本生成约 30 字的朗读风格指令。"""
    from dashscope_audio import llm

    prompt = _INSTRUCTION_PROMPT.replace("__TEXT__", text)
    content = llm.chat(
        settings,
        prompt,
        model=model or llm.DEFAULT_MODEL,
        enable_thinking=enable_thinking,
    )
    return _clean_instruction(content)


def _clean_instruction(content: str) -> str:
    """清理模型输出：合并换行、去除首尾引号与多余空白。"""
    text = content.strip().replace("\n", " ").strip()
    for quote in ('"', "'", "“", "”", "「", "」", "『", "』"):
        text = text.strip(quote)
    return text.strip()

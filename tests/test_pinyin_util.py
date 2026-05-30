# coding: utf-8
"""单元测试：多音字 dict 解析与 LLM-JSON 解析（纯函数，无需 GUI / 网络）。

conda run -n trade python tests/test_pinyin_util.py  退出码 0=通过。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.pinyin_util import (
    _parse_heteronym_json,
    format_corrections,
    parse_corrections,
)


def main() -> int:
    failures: list[str] = []

    def check(name: str, got, want) -> None:
        if got != want:
            failures.append(f"{name}: 期望 {want}，实际 {got}")

    # parse_corrections：带前缀 / 纯字典 / 单引号 / 非法 / 空
    check("带前缀", parse_corrections('corrections = {"乐": "le4", "差": "ci1"}'),
          [("乐", "le4"), ("差", "ci1")])
    check("纯字典", parse_corrections('{"重": "chong2"}'), [("重", "chong2")])
    check("单引号", parse_corrections("{'参': 'cen1'}"), [("参", "cen1")])
    check("非法输入", parse_corrections("这不是字典"), [])
    check("空文本", parse_corrections(""), [])

    # _parse_heteronym_json：带文字前缀 / 代码块 / 同字去重 / 非法
    check("LLM带文字", _parse_heteronym_json('结果：[{"char":"差","pinyin":"ci1"}]'),
          [("差", "ci1")])
    check("LLM代码块",
          _parse_heteronym_json('```json\n[{"char":"乐","pinyin":"le4"}]\n```'),
          [("乐", "le4")])
    check("LLM去重",
          _parse_heteronym_json(
              '[{"char":"差","pinyin":"ci1"},{"char":"差","pinyin":"cha1"}]'),
          [("差", "ci1")])
    check("LLM非法", _parse_heteronym_json("模型拒绝回答"), [])
    # 词级消歧（text 字段）：同字不同音用不同词条
    check("LLM词级",
          _parse_heteronym_json(
              '[{"text":"至于","pinyin":"zhi4 yu2"},{"text":"于嗟","pinyin":"xu1 jie1"}]'),
          [("至于", "zhi4 yu2"), ("于嗟", "xu1 jie1")])
    check("LLM_text字段", _parse_heteronym_json('[{"text":"乐","pinyin":"le4"}]'),
          [("乐", "le4")])

    # format_corrections：与 parse 往返、空表
    rt = [("乐", "le4"), ("差", "ci1")]
    check("format往返", parse_corrections(format_corrections(rt, "corrections")), rt)
    check("format空", format_corrections([], "replaces"), "replaces = {}")

    if failures:
        print("FAIL:")
        for item in failures:
            print("  -", item)
        return 1
    print("PASS: 多音字解析全部正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())

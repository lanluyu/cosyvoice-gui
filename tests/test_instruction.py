# coding: utf-8
"""单元测试：AI 风格指令输出清理（纯函数，无需网络）。

conda run -n trade python tests/test_instruction.py  退出码 0=通过。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.instruction_util import _clean_instruction


def main() -> int:
    failures: list[str] = []

    def check(name: str, got, want) -> None:
        if got != want:
            failures.append(f"{name}: 期望 {want!r}，实际 {got!r}")

    check("去双引号", _clean_instruction('"以清静的语气朗读"'), "以清静的语气朗读")
    check("去中文引号", _clean_instruction("“轻柔、舒缓地朗读”"), "轻柔、舒缓地朗读")
    check("合并换行", _clean_instruction("以空灵语气朗读\n语速舒缓"), "以空灵语气朗读 语速舒缓")
    check("去首尾空白", _clean_instruction("  淡然疏离地朗读  "), "淡然疏离地朗读")

    if failures:
        print("FAIL:")
        for item in failures:
            print("  -", item)
        return 1
    print("PASS: 风格指令清理正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())

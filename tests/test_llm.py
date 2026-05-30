# coding: utf-8
"""单元测试：OpenAI 兼容流式回复的 content 聚合（纯函数，无需网络）。

conda run -n trade python tests/test_llm.py  退出码 0=通过。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashscope_audio.llm import _aggregate_content


def main() -> int:
    failures: list[str] = []

    def check(name: str, got, want) -> None:
        if got != want:
            failures.append(f"{name}: 期望 {want!r}，实际 {got!r}")

    # 聚合 content；忽略 reasoning_content / 心跳 / 空 choices；[DONE] 后停止
    lines = [
        'data: {"choices":[{"delta":{"reasoning_content":"思考中"}}]}',
        'data: {"choices":[{"delta":{"content":"你好"}}]}',
        ": keep-alive",
        'data: {"choices":[]}',
        'data: {"choices":[{"delta":{"content":"世界"}}]}',
        "data: [DONE]",
        'data: {"choices":[{"delta":{"content":"应被忽略"}}]}',
    ]
    check("聚合", _aggregate_content(lines), "你好世界")
    check("空", _aggregate_content([]), "")
    check("无content", _aggregate_content(['data: {"choices":[{"delta":{}}]}']), "")
    check(
        "跳过非法json",
        _aggregate_content(['data: {坏', 'data: {"choices":[{"delta":{"content":"x"}}]}']),
        "x",
    )

    if failures:
        print("FAIL:")
        for item in failures:
            print("  -", item)
        return 1
    print("PASS: SSE content 聚合正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())

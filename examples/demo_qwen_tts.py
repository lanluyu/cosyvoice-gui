# coding: utf-8
"""Qwen-TTS 非实时语音合成示例。

运行前：
  set DASHSCOPE_API_KEY=sk-xxx   (PowerShell: $env:DASHSCOPE_API_KEY="sk-xxx")
  conda run -n trade python examples/demo_qwen_tts.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashscope_audio import load_settings, qwen_tts  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

TEXT = "那我来给大家推荐一款T恤，这款真的超级好看，颜色很显气质。"


def main() -> None:
    settings = load_settings()

    # 基础合成（默认音色 Cherry，模型 qwen3-tts-flash）
    result = qwen_tts.synthesize_to_file(
        settings,
        text=TEXT,
        dest_path="qwen_tts_output.wav",
    )
    print(f"合成完成: request_id={result.request_id} url={result.audio_url[:60]}...")

    # 指令控制（仅 qwen3-tts-instruct-flash 系列支持）
    qwen_tts.synthesize_to_file(
        settings,
        text=TEXT,
        dest_path="qwen_tts_instruct.wav",
        model="qwen3-tts-instruct-flash",
        instructions="语速较快，带有明显的上扬语调，适合介绍时尚产品。",
        optimize_instructions=True,
    )
    print("指令控制合成完成: qwen_tts_instruct.wav")


if __name__ == "__main__":
    main()

# coding: utf-8
"""CosyVoice 非实时语音合成示例。

运行前：
  set DASHSCOPE_API_KEY=sk-xxx   (PowerShell: $env:DASHSCOPE_API_KEY="sk-xxx")
  conda run -n trade python examples/demo_cosyvoice.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# 允许从项目根目录直接运行脚本
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashscope_audio import cosyvoice_tts, load_settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

TEXT = "我家的后面有一个很大的花园。"


def main() -> None:
    settings = load_settings()  # 默认北京地域，从环境变量读 API Key

    # 非流式：合成并下载为 wav
    result = cosyvoice_tts.synthesize_to_file(
        settings,
        text=TEXT,
        voice="longanyang",
        dest_path="cosyvoice_output.wav",
        model="cosyvoice-v3-flash",
        format="wav",
        sample_rate=24000,
    )
    print(f"非流式完成: chars={result.characters} request_id={result.request_id}")

    # 流式：边合成边写入 mp3（流式拼接用 mp3 更稳妥）
    cosyvoice_tts.synthesize_stream_to_file(
        settings,
        text=TEXT,
        voice="longanyang",
        dest_path="cosyvoice_stream.mp3",
        model="cosyvoice-v3-flash",
        format="mp3",
    )
    print("流式完成: cosyvoice_stream.mp3")


if __name__ == "__main__":
    main()

# coding: utf-8
"""CosyVoice 声音复刻示例：创建音色 -> 轮询就绪 -> 查询列表 -> 删除。

运行前：
  set DASHSCOPE_API_KEY=sk-xxx   (PowerShell: $env:DASHSCOPE_API_KEY="sk-xxx")
  conda run -n trade python examples/demo_voice_clone.py

要点：
  - model 固定 voice-enrollment；target_model 用 cosyvoice 系列，
    且必须与后续合成时的 model 一致。
  - 样本音频通过【公网 URL】提交（建议 OSS），不收 base64。
  - 创建是异步任务，需轮询 query_voice 至 status=OK。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashscope_audio import load_settings, voice_clone  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

TARGET_MODEL = "cosyvoice-v3.5-plus"
# 公网可访问的样本音频 URL（请替换为自己的，建议上传到 OSS）
SAMPLE_URL = (
    "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/"
    "cosyvoice/cosyvoice-zeroshot-sample.wav"
)


def main() -> None:
    settings = load_settings()

    # 1. 创建音色（异步）
    info = voice_clone.create_voice(
        settings, url=SAMPLE_URL, target_model=TARGET_MODEL, prefix="demo"
    )
    print(f"创建已提交: voice_id={info.voice_id}")

    # 2. 轮询至就绪
    ready = voice_clone.wait_until_ready(settings, info.voice_id)
    print(f"音色就绪: status={ready.status}")

    # 3. 查询音色列表
    voices = voice_clone.list_voices(settings, page_size=10)
    print(f"当前音色数: {len(voices)}")
    for v in voices:
        print(f"  - {v.voice_id}  {v.status}  {v.gmt_create}  {v.target_model}")

    # 4. 删除（演示用，实际可保留供合成调用）
    voice_clone.delete_voice(settings, info.voice_id)
    print(f"已删除: {info.voice_id}")


if __name__ == "__main__":
    main()

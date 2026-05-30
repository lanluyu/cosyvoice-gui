# coding: utf-8
"""GUI 用到的静态常量：合成模型、音频格式、采样率等。

均为 DashScope CosyVoice 合成接口的可选值集合，集中放置便于维护与下拉填充。
系统预置音色清单待与《合成语音文档.md》核对后在阶段 2 补全，阶段 1 通过
list_voices 拉取复刻音色 + 允许手动输入音色名。
"""
from __future__ import annotations

# CosyVoice 合成模型；用复刻音色合成时，model 必须与音色的 target_model 一致，否则报 418
COSYVOICE_MODELS: list[str] = [
    "cosyvoice-v3.5-plus",
    "cosyvoice-v3.5-flash",
    "cosyvoice-v3-plus",
    "cosyvoice-v3-flash",
    "cosyvoice-v2",
]

# 音频格式
AUDIO_FORMATS: list[str] = ["wav", "mp3", "pcm", "opus"]

# 采样率(Hz)
SAMPLE_RATES: list[int] = [8000, 16000, 22050, 24000, 44100, 48000]

# 默认值
DEFAULT_MODEL: str = "cosyvoice-v3.5-plus"
DEFAULT_FORMAT: str = "wav"
DEFAULT_SAMPLE_RATE: int = 24000

# 韵律参数默认值与范围（范围见《合成语音文档.md》）
DEFAULT_VOLUME: int = 50      # 音量 [0, 100]
DEFAULT_RATE: float = 1.0     # 语速 [0.5, 2.0]
DEFAULT_PITCH: float = 1.0    # 音调 [0.5, 2.0]

# language_hints 可选值（空串表示不下发该参数，由模型自动判断）
LANGUAGE_HINTS: list[str] = ["", "zh", "en", "ja", "ko", "yue"]

# 不支持 hot_fix（文本热修复 / 多音字纠音）的模型；选中时禁用多音字面板
MODELS_NO_HOTFIX: frozenset[str] = frozenset({"cosyvoice-v2"})

# 「AI 扫描多音字」可选的 Qwen 文本模型（带深度思考的 max 更准但更慢）
QWEN_TEXT_MODELS: list[str] = [
    "qwen3.7-max",
    "qwen-max-latest",
    "qwen-plus",
    "qwen-turbo",
]
DEFAULT_QWEN_MODEL: str = "qwen3.7-max"

# coding: utf-8
"""阿里云百炼（DashScope）语音能力的 requests 封装。

三个子模块对应三份文档的核心功能：
  - cosyvoice_tts : 非实时语音合成（CosyVoice）
  - qwen_tts      : 非实时语音合成（Qwen-TTS）
  - voice_clone   : 声音复刻（千问 Omni 音色创建/查询/删除）

统一通过 config.load_settings() 获取配置（API Key 从环境变量注入）。
"""
from __future__ import annotations

from . import audio_post, cosyvoice_tts, qwen_tts, voice_clone
from ._client import DashScopeError
from .config import Region, Settings, load_settings

__all__ = [
    "cosyvoice_tts",
    "qwen_tts",
    "voice_clone",
    "audio_post",
    "DashScopeError",
    "Region",
    "Settings",
    "load_settings",
]

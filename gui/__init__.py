# coding: utf-8
"""PySide6 桌面 GUI：阿里云百炼 CosyVoice 语音合成。

纯表现层，不含业务逻辑；所有 DashScope 调用通过 dashscope_audio 包完成，
并经 controller 做线程化与错误中文化。
"""

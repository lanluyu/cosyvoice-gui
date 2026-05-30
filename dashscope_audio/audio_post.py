# coding: utf-8
"""音频后处理工具（基于 ffmpeg）。

合成结果有时需要做轻量后处理，例如在开头补一段静默，避免音频一上来就朗读、
听不清开头。相比 SSML 的 <break>（依赖模型是否裁剪首段静默），ffmpeg 后处理
对任意格式、任意模型都精确可控。

需要系统已安装 ffmpeg 并加入 PATH。
"""
from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def _require_ffmpeg() -> str:
    """返回 ffmpeg 可执行路径；未安装则报错。"""
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise RuntimeError("未找到 ffmpeg：请先安装并加入 PATH")
    return exe


def prepend_silence(input_path: str, output_path: str, *, ms: int = 2000) -> None:
    """在音频开头补 ms 毫秒静默，结果写入 output_path。

    用 ffmpeg 的 adelay 滤镜实现：adelay={ms}:all=1 对所有声道统一延迟，
    单声道/立体声均适用（等价于 `adelay=2000|2000`，但无需关心声道数）。

    注意：input_path 与 output_path 不能相同（ffmpeg 不支持原地读写）。
    """
    if input_path == output_path:
        raise ValueError("input_path 与 output_path 不能相同")
    exe = _require_ffmpeg()
    cmd = [
        exe,
        "-y",                       # 覆盖已存在的输出
        "-i", input_path,
        "-af", f"adelay={ms}:all=1",
        output_path,
    ]
    logger.info("开头补静默 %dms: %s -> %s", ms, input_path, output_path)
    # check=True：ffmpeg 失败时抛 CalledProcessError；capture_output 收集日志便于排查
    subprocess.run(cmd, check=True, capture_output=True)

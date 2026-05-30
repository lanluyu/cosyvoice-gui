# coding: utf-8
"""GUI 与 dashscope_audio 业务层之间的胶水层。

职责：
  - 把阻塞的网络调用（拉音色列表 / 语音合成）放到 QThreadPool 后台线程，避免冻结 UI；
  - 通过 Qt 信号把结果或【已转成中文】的错误回传到主线程更新界面。
GUI 控件代码只与本层交互，不直接处理线程与异常细节。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from dashscope_audio import (
    DashScopeError,
    Region,
    Settings,
    audio_post,
    cosyvoice_tts,
    load_settings,
    voice_clone,
)
from dashscope_audio.voice_clone import VoiceInfo

logger = logging.getLogger(__name__)


def build_settings(api_key: str, region: Region, proxy: str = "") -> Settings:
    """构造 Settings；api_key 空时回退环境变量，proxy 空时回退系统/环境代理。"""
    return load_settings(region=region, api_key=api_key or None, proxy=proxy or None)


def fetch_all_voices(settings: Settings) -> list[VoiceInfo]:
    """分页拉取账号下全部复刻音色（只读、免费）。"""
    voices: list[VoiceInfo] = []
    page_index = 0
    page_size = 50
    while True:
        batch = voice_clone.list_voices(
            settings, page_index=page_index, page_size=page_size
        )
        voices.extend(batch)
        if len(batch) < page_size:  # 不足一页说明已到末页
            break
        page_index += 1
    return voices


def synthesize_with_post(
    settings: Settings,
    text: str,
    voice: str,
    dest: str,
    *,
    model: str,
    prepend_ms: int = 0,
    **options: Any,
) -> str | None:
    """合成到 dest；prepend_ms>0 时合成后用 ffmpeg 在开头补一段静默。

    返回 None 表示完全成功；返回字符串表示有可降级的警告（如缺 ffmpeg，
    此时已保存未补静默的原始音频，不丢结果）。
    """
    if prepend_ms <= 0:
        cosyvoice_tts.synthesize_to_file(
            settings, text, voice, dest, model=model, **options
        )
        return None
    # ffmpeg 不支持原地读写：先合成到 _raw，再补静默到最终 dest
    raw = str(Path(dest).with_name(Path(dest).stem + "_raw" + Path(dest).suffix))
    cosyvoice_tts.synthesize_to_file(
        settings, text, voice, raw, model=model, **options
    )
    try:
        audio_post.prepend_silence(raw, dest, ms=prepend_ms)
    except Exception as err:  # 缺 ffmpeg 等：降级保留原始音频，不丢结果
        os.replace(raw, dest)
        return f"已合成，但补静默失败（{err}）；已保存未补静默的音频"
    os.remove(raw)
    return None


def format_error(err: Exception) -> str:
    """把异常转成面向用户的中文提示（DashScope 业务错误给排查建议，其余原样）。"""
    if isinstance(err, DashScopeError):
        code = err.code or ""
        if code == "AllocationQuota.FreeTierOnly":
            hint = "模型免费额度已用尽：请在百炼控制台关闭「仅使用免费额度」或开通付费。"
        elif err.status_code == 401 or code in ("InvalidApiKey", "Unauthorized"):
            hint = "鉴权失败：检查 API Key 是否正确、是否与所选地域匹配。"
        elif code == "Throttling.RateQuota":
            hint = "触发限流：稍后重试或降低频率。"
        elif code.startswith("Audio.") or code == "InvalidParameter":
            hint = "参数或音频不合规：检查文本长度、音色名、格式与时长。"
        else:
            hint = "请对照错误码文档排查：https://help.aliyun.com/zh/model-studio/error-code"
        rid = f"（request_id={err.request_id}）" if err.request_id else ""
        return f"[{code or err.status_code}] {err.message}\n{hint}{rid}"
    return f"{type(err).__name__}: {err}"


class WorkerSignals(QObject):
    """Worker 的信号载体（QRunnable 自身不是 QObject，不能直接定义信号）。"""

    result = Signal(object)   # 成功：业务返回值
    error = Signal(str)       # 失败：已转中文的错误文本
    finished = Signal()       # 无论成败都会发出，用于恢复按钮等收尾


class Worker(QRunnable):
    """在 QThreadPool 线程里运行任意阻塞函数，结果/异常经信号回主线程。"""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as err:  # 业务/网络异常统一捕获，转中文后回传主线程
            logger.exception("后台任务失败")
            self.signals.error.emit(format_error(err))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

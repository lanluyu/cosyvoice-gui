# coding: utf-8
"""非实时语音合成（Qwen-TTS）的 HTTP 实现。

对应文档《使用Qwen非实时语音合成.py》/ Qwen-TTS API 参考页。

说明：官方文档只给了 DashScope SDK 的 MultiModalConversation.call(...) 用法，
其底层走的是多模态生成 HTTP 端点：
    POST {base}/services/aigc/multimodal-generation/generation
请求体的 model + input（text/voice/...）结构与 SDK 参数一一对应。
本模块即按该端点用 requests 直接实现，行为与 SDK 等价。
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator

from . import _client
from .config import Settings

logger = logging.getLogger(__name__)

# MultiModalConversation 背后的 HTTP 端点路径
_PATH = "/services/aigc/multimodal-generation/generation"


@dataclass
class QwenTTSResult:
    """非流式合成结果。"""

    audio_url: str            # 完整音频文件 URL，有效期 24 小时
    expires_at: int           # URL 过期时间戳
    request_id: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


def _build_payload(
    text: str,
    voice: str,
    model: str,
    *,
    language_type: str = "Auto",
    instructions: str | None = None,
    optimize_instructions: bool | None = None,
) -> dict[str, Any]:
    """组装请求体。

    instructions / optimize_instructions 仅 qwen3-tts-instruct-flash 系列支持，
    为空时不下发，避免对不支持的模型造成参数错误。
    """
    input_obj: dict[str, Any] = {
        "text": text,
        "voice": voice,
        "language_type": language_type,
    }
    if instructions is not None:
        input_obj["instructions"] = instructions
    if optimize_instructions is not None:
        input_obj["optimize_instructions"] = optimize_instructions
    return {"model": model, "input": input_obj}


def synthesize(
    settings: Settings,
    text: str,
    voice: str = "Cherry",
    *,
    model: str = "qwen3-tts-flash",
    **options: Any,
) -> QwenTTSResult:
    """非流式合成：返回音频 URL（需另行下载）。

    options 透传给 _build_payload（language_type / instructions /
    optimize_instructions）。输入长度上限：qwen-tts 为 512 Token，
    qwen3-tts-flash 系列为 600 字符。
    """
    payload = _build_payload(text, voice, model, **options)
    body = _client.post_json(settings, _PATH, payload)
    audio = body.get("output", {}).get("audio", {})
    return QwenTTSResult(
        audio_url=audio.get("url", ""),
        expires_at=audio.get("expires_at", 0),
        request_id=body.get("request_id", ""),
        raw=body,
    )


def synthesize_to_file(
    settings: Settings,
    text: str,
    dest_path: str,
    voice: str = "Cherry",
    *,
    model: str = "qwen3-tts-flash",
    **options: Any,
) -> QwenTTSResult:
    """非流式合成并下载到本地文件。"""
    result = synthesize(settings, text, voice, model=model, **options)
    if not result.audio_url:
        raise _client.DashScopeError(200, None, "返回体中没有音频 URL", result.request_id)
    _client.download_to_file(result.audio_url, dest_path, settings)
    logger.info("Qwen-TTS 合成完成: %s", dest_path)
    return result


def synthesize_stream(
    settings: Settings,
    text: str,
    voice: str = "Cherry",
    *,
    model: str = "qwen3-tts-flash",
    **options: Any,
) -> Iterator[dict[str, Any]]:
    """流式合成：逐条返回 SSE 事件原始 JSON。

    流式输出时 output.audio.data 为 Base64 音频块，
    流式结束的事件 output.finish_reason 为 "stop"。
    """
    payload = _build_payload(text, voice, model, **options)
    yield from _client.post_sse(settings, _PATH, payload)


def synthesize_stream_to_file(
    settings: Settings,
    text: str,
    dest_path: str,
    voice: str = "Cherry",
    *,
    model: str = "qwen3-tts-flash",
    **options: Any,
) -> None:
    """流式合成并把音频块按序追加写入文件。"""
    with open(dest_path, "wb") as f:
        for event in synthesize_stream(settings, text, voice, model=model, **options):
            data_b64 = event.get("output", {}).get("audio", {}).get("data", "")
            if data_b64:
                f.write(base64.b64decode(data_b64))
    logger.info("Qwen-TTS 流式合成完成: %s", dest_path)

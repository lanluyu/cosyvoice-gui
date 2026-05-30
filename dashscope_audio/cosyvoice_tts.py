# coding: utf-8
"""非实时语音合成（CosyVoice）的 HTTP 实现。

对应文档《合成语音文档.md》。
端点：POST {base}/services/audio/tts/SpeechSynthesizer
仅北京地域可用，支持非流式与流式（SSE）两种输出。
"""
from __future__ import annotations

import base64
import html
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator

from . import _client
from .config import Settings

logger = logging.getLogger(__name__)

# 业务路径（相对 http_base）
_PATH = "/services/audio/tts/SpeechSynthesizer"


def wrap_ssml(
    text: str,
    *,
    lead_silence: str | None = None,
    trail_silence: str | None = None,
) -> str:
    """把纯文本包装成 SSML，可在开头/结尾插入静默。

    用于"合成时让开头留白"等场景：例如开头留 2 秒空白，避免音频一上来就朗读。
    使用时必须同时设置合成参数 enable_ssml=True，且仅 cosyvoice v2/v3/v3.5
    系列的复刻音色（及标记支持 SSML 的系统音色）生效。

    lead_silence / trail_silence：静默时长字符串，如 "2s" 或 "500ms"。
        取值：秒为 [1,10] 整数，毫秒为 [50,10000] 整数。

    文本中的 XML 特殊字符（& < > " '）会自动转义。
    """
    body = html.escape(text, quote=True)  # 转义 & < > " '
    parts = ["<speak>"]
    if lead_silence:
        parts.append(f'<break time="{lead_silence}"/>')
    parts.append(body)
    if trail_silence:
        parts.append(f'<break time="{trail_silence}"/>')
    parts.append("</speak>")
    return "".join(parts)


def _is_han(ch: str) -> bool:
    """是否为常用汉字（CJK 基本区）。"""
    return "一" <= ch <= "鿿"


def to_pinyin_ssml(
    text: str,
    *,
    corrections: dict[str, str] | None = None,
    lead_silence: str | None = None,
    trail_silence: str | None = None,
) -> str:
    """给全文逐字标注拼音并生成 SSML，使合成按拼音发音（需 enable_ssml=True）。

    适用于古文等多音字场景：用 pypinyin 自动生成带声调数字的拼音（声调 1-4，
    轻声为 5），对连续汉字用 <phoneme alphabet="py" ph="..."> 包裹，标点等非汉字
    原样保留以维持停顿与韵律。

    注意：对【全文】逐字加 <phoneme> 会显著降低 CosyVoice 的合成自然度。
    若只是纠正少数多音字，优先用 synthesize_to_file 的 hot_fix.pronunciation 参数
    （仅对指定词纠音，不影响其余文本），效果远好于整篇标音。

    corrections：{字: 拼音} 覆盖表，纠正多音字/古音（如 {"乐": "le4", "差": "ci1"}），
        对全文中该字统一生效。古文多音字 pypinyin 未必准确，建议人工校对后用此项纠正。

    依赖 pypinyin（pip install pypinyin）；仅调用本函数时才需要。
    注意：pypinyin 用 "v" 表示 ü（如 女→nv3），如遇发音异常可在 corrections 中改写。
    """
    from pypinyin import Style, lazy_pinyin  # 延迟导入，未用到拼音功能时不强制依赖

    corrections = corrections or {}
    parts = ["<speak>"]
    if lead_silence:
        parts.append(f'<break time="{lead_silence}"/>')

    i, n = 0, len(text)
    while i < n:
        if _is_han(text[i]):
            # 取一段连续汉字，整段交给 pypinyin 以利用上下文消歧多音字
            j = i
            while j < n and _is_han(text[j]):
                j += 1
            run = text[i:j]
            py = lazy_pinyin(run, style=Style.TONE3, neutral_tone_with_five=True)
            # 应用人工纠正（按字覆盖）
            py = [corrections.get(ch, p) for ch, p in zip(run, py)]
            parts.append(
                f'<phoneme alphabet="py" ph="{" ".join(py)}">{html.escape(run)}</phoneme>'
            )
            i = j
        else:
            # 非汉字段（标点/数字/英文等）原样保留
            j = i
            while j < n and not _is_han(text[j]):
                j += 1
            parts.append(html.escape(text[i:j]))
            i = j

    if trail_silence:
        parts.append(f'<break time="{trail_silence}"/>')
    parts.append("</speak>")
    return "".join(parts)


@dataclass
class CosyVoiceResult:
    """非流式合成结果。"""

    audio_url: str           # 完整音频文件 URL，有效期 24 小时
    expires_at: int          # URL 过期时间的 UNIX 时间戳
    characters: int          # 计费字符数
    request_id: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)  # 原始返回体，便于排查


def _build_input(
    text: str,
    voice: str,
    *,
    # —— 常用参数（带默认值，始终下发）——
    format: str = "mp3",                  # 音频格式：mp3 / pcm / wav / opus
    sample_rate: int = 22050,             # 采样率(Hz)：8000/16000/22050/24000/44100/48000
    volume: int = 50,                     # 音量：[0, 100]
    rate: float = 1.0,                    # 语速：[0.5, 2.0]
    pitch: float = 1.0,                   # 音调：[0.5, 2.0]
    # —— 可选参数（None 时不下发，避免对不支持的模型报错）——
    bit_rate: int | None = None,          # 码率(kbps) [6,510]，仅 format=opus 生效
    enable_ssml: bool | None = None,      # 是否启用 SSML
    word_timestamp_enabled: bool | None = None,  # 字级时间戳，仅部分模型/音色支持
    seed: int | None = None,              # 随机种子 [0,65535]，相同参数+seed 可复现
    language_hints: list[str] | None = None,     # 目标语种提示，如 ["zh"]/["en"]
    instruction: str | None = None,       # 指令：控制方言/情感/角色
    enable_aigc_tag: bool | None = None,  # 是否嵌入 AIGC 隐性标识，仅 v3-flash/v3-plus/v2
    aigc_propagator: str | None = None,   # AIGC 标识 ContentPropagator 字段
    aigc_propagate_id: str | None = None,  # AIGC 标识 PropagateID 字段
    hot_fix: dict[str, Any] | None = None,  # 文本热修复：自定义发音/文本替换（v2 不支持）
    enable_markdown_filter: bool | None = None,  # 过滤 Markdown 标记，仅 v3-flash 复刻音色
) -> dict[str, Any]:
    """组装 input 对象（文档《合成语音文档.md》中的全部合成参数）。"""
    payload: dict[str, Any] = {
        "text": text,
        "voice": voice,
        "format": format,
        "sample_rate": sample_rate,
        "volume": volume,
        "rate": rate,
        "pitch": pitch,
    }
    # 仅在显式提供时才下发的可选参数
    optional: dict[str, Any] = {
        "bit_rate": bit_rate,
        "enable_ssml": enable_ssml,
        "word_timestamp_enabled": word_timestamp_enabled,
        "seed": seed,
        "language_hints": language_hints,
        "instruction": instruction,
        "enable_aigc_tag": enable_aigc_tag,
        "aigc_propagator": aigc_propagator,
        "aigc_propagate_id": aigc_propagate_id,
        "hot_fix": hot_fix,
        "enable_markdown_filter": enable_markdown_filter,
    }
    payload.update({k: v for k, v in optional.items() if v is not None})
    return payload


def _parse_result(body: dict[str, Any]) -> CosyVoiceResult:
    """从返回体解析出 CosyVoiceResult。"""
    audio = body.get("output", {}).get("audio", {})
    return CosyVoiceResult(
        audio_url=audio.get("url", ""),
        expires_at=audio.get("expires_at", 0),
        characters=body.get("usage", {}).get("characters", 0),
        request_id=body.get("request_id", ""),
        raw=body,
    )


def synthesize(
    settings: Settings,
    text: str,
    voice: str,
    *,
    model: str = "cosyvoice-v3-flash",
    **options: Any,
) -> CosyVoiceResult:
    """非流式合成：一次性返回音频 URL（不含音频字节，需另行下载）。

    options 透传给 _build_input（完整参数见 _build_input / synthesize_to_file 签名）。
    """
    payload = {"model": model, "input": _build_input(text, voice, **options)}
    body = _client.post_json(settings, _PATH, payload)
    return _parse_result(body)


def synthesize_to_file(
    settings: Settings,
    text: str,
    voice: str,
    dest_path: str,
    *,
    model: str = "cosyvoice-v3-flash",     # cosyvoice-v3.5-plus / v3.5-flash / v3-plus / v3-flash / v2
    # —— 常用参数 ——
    format: str = "wav",                   # 落盘默认 wav；mp3/pcm/wav/opus
    sample_rate: int = 24000,              # 采样率(Hz)
    volume: int = 50,                      # 音量 [0,100]
    rate: float = 1.0,                     # 语速 [0.5,2.0]
    pitch: float = 1.0,                    # 音调 [0.5,2.0]
    # —— 可选参数（None 时不下发）——
    bit_rate: int | None = None,           # 码率(kbps)，仅 format=opus 生效
    enable_ssml: bool | None = None,       # 启用 SSML
    word_timestamp_enabled: bool | None = None,  # 字级时间戳
    seed: int | None = None,               # 随机种子 [0,65535]
    language_hints: list[str] | None = None,     # 目标语种提示
    instruction: str | None = None,        # 方言/情感/角色指令
    enable_aigc_tag: bool | None = None,   # AIGC 隐性标识
    aigc_propagator: str | None = None,    # AIGC ContentPropagator
    aigc_propagate_id: str | None = None,  # AIGC PropagateID
    hot_fix: dict[str, Any] | None = None,  # 文本热修复
    enable_markdown_filter: bool | None = None,  # 过滤 Markdown
) -> CosyVoiceResult:
    """非流式合成并把音频下载到本地文件（合成全部参数在此显式列出）。"""
    payload = {
        "model": model,
        "input": _build_input(
            text,
            voice,
            format=format,
            sample_rate=sample_rate,
            volume=volume,
            rate=rate,
            pitch=pitch,
            bit_rate=bit_rate,
            enable_ssml=enable_ssml,
            word_timestamp_enabled=word_timestamp_enabled,
            seed=seed,
            language_hints=language_hints,
            instruction=instruction,
            enable_aigc_tag=enable_aigc_tag,
            aigc_propagator=aigc_propagator,
            aigc_propagate_id=aigc_propagate_id,
            hot_fix=hot_fix,
            enable_markdown_filter=enable_markdown_filter,
        ),
    }
    body = _client.post_json(settings, _PATH, payload)
    result = _parse_result(body)
    if not result.audio_url:
        raise _client.DashScopeError(200, None, "返回体中没有音频 URL", result.request_id)
    _client.download_to_file(result.audio_url, dest_path, settings)
    logger.info("CosyVoice 合成完成: %s", dest_path)
    return result


def synthesize_stream(
    settings: Settings,
    text: str,
    voice: str,
    *,
    model: str = "cosyvoice-v3-flash",
    **options: Any,
) -> Iterator[dict[str, Any]]:
    """流式合成：逐条返回 SSE 事件原始 JSON。

    事件通过 output.type 区分：
      - sentence-begin：句子开始
      - sentence-synthesis：音频数据块（output.audio.data 为 Base64）
      - sentence-end：句子结束（返回累计计费字符数）
    options 透传给 _build_input。
    """
    payload = {"model": model, "input": _build_input(text, voice, **options)}
    yield from _client.post_sse(settings, _PATH, payload)


def synthesize_stream_to_file(
    settings: Settings,
    text: str,
    voice: str,
    dest_path: str,
    *,
    model: str = "cosyvoice-v3-flash",
    format: str = "mp3",
    **options: Any,
) -> None:
    """流式合成并把音频块按序追加写入文件。

    重要：流式拼接建议用 mp3 / pcm 这类可直接拼接的格式；wav 多块各带头，
    直接拼接会损坏文件，故这里默认 mp3。options 透传给 _build_input。
    """
    with open(dest_path, "wb") as f:
        for event in synthesize_stream(
            settings, text, voice, model=model, format=format, **options
        ):
            data_b64 = event.get("output", {}).get("audio", {}).get("data", "")
            if data_b64:
                f.write(base64.b64decode(data_b64))
    logger.info("CosyVoice 流式合成完成: %s", dest_path)

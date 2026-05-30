# coding: utf-8
"""声音复刻（音色管理）的 HTTP 实现 —— CosyVoice 版。

对应文档《使用 CosyVoice 声音复刻 API 创建和管理音色》。
端点：POST {base}/services/audio/tts/customization
靠 input.action 区分操作：
  create_voice / list_voice / query_voice / update_voice / delete_voice

关键概念，切勿混淆：
  - model        固定为 "voice-enrollment"，是声音复刻引擎本身
  - target_model 驱动音色的语音合成模型（cosyvoice-v3.5-plus / cosyvoice-v3-flash 等），
                 必须与后续调用 CosyVoice 语音合成接口时一致，否则合成失败

注意事项：
  - 复刻样本音频通过【公网可访问的 URL】提交（如上传到 OSS），不收 base64
  - 创建是【异步任务】：create_voice 返回 voice_id 后，需轮询 query_voice
    直到 status == "OK" 才能用于合成
  - 创建 / 查询 / 更新 / 删除 音色均免费，仅后续语音合成按字符计费
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from . import _client
from .config import Settings

logger = logging.getLogger(__name__)

_PATH = "/services/audio/tts/customization"
_ENROLLMENT_MODEL = "voice-enrollment"        # 声音复刻/设计模型，固定值
DEFAULT_TARGET_MODEL = "cosyvoice-v3.5-plus"  # 默认驱动音色的合成模型

# 音色状态
STATUS_OK = "OK"                # 审核通过，可用于合成
STATUS_DEPLOYING = "DEPLOYING"  # 审核中
STATUS_UNDEPLOYED = "UNDEPLOYED"  # 审核不通过，不可用


@dataclass
class VoiceInfo:
    """音色信息（不同 action 返回的字段子集不同，未返回的留默认值）。"""

    voice_id: str               # 音色 ID，可直接用于合成接口的 voice 参数
    target_model: str = ""      # 驱动该音色的合成模型
    status: str = ""            # DEPLOYING / OK / UNDEPLOYED
    gmt_create: str = ""        # 创建时间
    gmt_modified: str = ""      # 修改时间
    resource_link: str = ""     # 复刻所用源音频的 URL（仅 query_voice 返回）
    request_id: str = ""
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


def _call(settings: Settings, input_obj: dict[str, Any]) -> dict[str, Any]:
    """统一发起 customization 请求。"""
    return _client.post_json(
        settings, _PATH, {"model": _ENROLLMENT_MODEL, "input": input_obj}
    )


def create_voice(
    settings: Settings,
    url: str,
    *,
    target_model: str = DEFAULT_TARGET_MODEL,
    prefix: str = "myvoice",
    language_hints: list[str] | None = None,
    max_prompt_audio_length: float | None = None,
    enable_preprocess: bool | None = None,
) -> VoiceInfo:
    """创建自定义音色（异步任务，返回的音色需轮询至 OK 后才能用）。

    url：复刻样本音频的公网可访问 URL（推荐 OSS）。音频要求见文档：
        WAV/MP3 等、单声道、>=16kHz、10~20s、无背景噪音。
    prefix：音色名前缀，仅数字和英文字母，<=10 字符，会出现在最终 voice_id 中。
    language_hints：辅助识别样本语种的提示，默认 ["zh"]；仅 v3.5/v3 系列生效。
    max_prompt_audio_length：用于复刻的样本音频最大时长（秒），[3.0, 30.0]，
        仅 v3.5-plus/v3.5-flash/v3-flash 生效。
    enable_preprocess：是否对样本做降噪/增强/音量规整，仅上述模型生效。
    """
    input_obj: dict[str, Any] = {
        "action": "create_voice",
        "target_model": target_model,
        "prefix": prefix,
        "url": url,
    }
    if language_hints is not None:
        input_obj["language_hints"] = language_hints
    if max_prompt_audio_length is not None:
        input_obj["max_prompt_audio_length"] = max_prompt_audio_length
    if enable_preprocess is not None:
        input_obj["enable_preprocess"] = enable_preprocess

    body = _call(settings, input_obj)
    out = body.get("output", {})
    info = VoiceInfo(
        voice_id=out.get("voice_id", ""),
        target_model=out.get("target_model", target_model),
        request_id=body.get("request_id", ""),
        raw=body,
    )
    logger.info("创建音色已提交: %s (target_model=%s)", info.voice_id, info.target_model)
    return info


def query_voice(settings: Settings, voice_id: str) -> VoiceInfo:
    """查询单个音色的详情，用于轮询复刻是否就绪、或查源音频 URL。

    返回的 resource_link 是复刻时所用样本音频的 URL，可据此区分音色来源。
    """
    body = _call(settings, {"action": "query_voice", "voice_id": voice_id})
    out = body.get("output", {})
    return VoiceInfo(
        voice_id=voice_id,
        target_model=out.get("target_model", ""),
        status=out.get("status", ""),
        gmt_create=out.get("gmt_create", ""),
        gmt_modified=out.get("gmt_modified", ""),
        resource_link=out.get("resource_link", ""),
        request_id=body.get("request_id", ""),
        raw=body,
    )


def list_voices(
    settings: Settings,
    *,
    prefix: str | None = None,
    page_index: int = 0,
    page_size: int = 10,
) -> list[VoiceInfo]:
    """分页查询已创建的音色列表（查询免费）。

    prefix：按创建时的前缀过滤；不传则返回全部。
    """
    input_obj: dict[str, Any] = {
        "action": "list_voice",
        "page_index": page_index,
        "page_size": page_size,
    }
    if prefix is not None:
        input_obj["prefix"] = prefix

    body = _call(settings, input_obj)
    request_id = body.get("request_id", "")
    voices = body.get("output", {}).get("voice_list", [])
    return [
        VoiceInfo(
            voice_id=v.get("voice_id", ""),
            target_model=v.get("target_model", ""),
            status=v.get("status", ""),
            gmt_create=v.get("gmt_create", ""),
            gmt_modified=v.get("gmt_modified", ""),
            request_id=request_id,
            raw=v,
        )
        for v in voices
    ]


def update_voice(settings: Settings, voice_id: str, url: str) -> str:
    """用新的样本音频更新已有音色（仅声音复刻支持）。返回 request_id。"""
    body = _call(
        settings, {"action": "update_voice", "voice_id": voice_id, "url": url}
    )
    request_id = body.get("request_id", "")
    logger.info("更新音色成功: %s (request_id=%s)", voice_id, request_id)
    return request_id


def delete_voice(settings: Settings, voice_id: str) -> str:
    """删除指定音色（不可逆，释放配额，免费）。返回 request_id。"""
    body = _call(settings, {"action": "delete_voice", "voice_id": voice_id})
    request_id = body.get("request_id", "")
    logger.info("删除音色成功: %s (request_id=%s)", voice_id, request_id)
    return request_id


def wait_until_ready(
    settings: Settings,
    voice_id: str,
    *,
    interval: float = 10.0,
    max_attempts: int = 30,
) -> VoiceInfo:
    """轮询音色状态，直到 OK 返回；UNDEPLOYED 抛错；超时抛 TimeoutError。

    复刻是异步任务，创建后需等待审核/部署完成才能用于合成。
    """
    for attempt in range(1, max_attempts + 1):
        info = query_voice(settings, voice_id)
        logger.info("轮询音色状态 %d/%d: %s", attempt, max_attempts, info.status)
        if info.status == STATUS_OK:
            return info
        if info.status == STATUS_UNDEPLOYED:
            raise _client.DashScopeError(
                200, "VoiceUndeployed", f"音色 {voice_id} 审核不通过，检查样本音频质量",
                info.request_id,
            )
        time.sleep(interval)
    raise TimeoutError(f"轮询超时：音色 {voice_id} 在 {max_attempts} 次后仍未就绪")

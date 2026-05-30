# coding: utf-8
"""DashScope 文本生成（Qwen）调用封装——OpenAI 兼容模式，用 requests 实现。

参考 qwen模型示例.py：经百炼「兼容模式」端点调用，支持深度思考模型
（默认 qwen3.7-max，流式返回 reasoning_content + content）。本模块只聚合并
返回最终回复 content，思考过程仅用于提升质量、不返回。不引入 openai 依赖，
与项目其余部分统一用 requests。
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable

import requests

from ._client import DEFAULT_TIMEOUT, DashScopeError, _proxies, _try_json
from .config import Region, Settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3.7-max"

# 各地域的 OpenAI 兼容端点 base url（与语音用的 /api/v1 路径不同）
_COMPATIBLE_BASE: dict[Region, str] = {
    Region.BEIJING: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    Region.SINGAPORE: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
}


def chat(
    settings: Settings,
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    enable_thinking: bool = True,
) -> str:
    """单轮对话，返回最终回复文本（不含思考过程）。

    深度思考模型要求流式返回，这里聚合所有 content 分片后返回。
    """
    url = _COMPATIBLE_BASE[settings.region] + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "enable_thinking": enable_thinking,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    logger.debug("LLM chat model=%s enable_thinking=%s", model, enable_thinking)
    with requests.post(
        url, json=payload, headers=headers,
        timeout=DEFAULT_TIMEOUT, stream=True, proxies=_proxies(settings),
    ) as resp:
        if resp.status_code != 200:
            _raise_compat_error(resp)
        return _aggregate_content(resp.iter_lines(decode_unicode=True))


def _aggregate_content(lines: Iterable[str]) -> str:
    """从 OpenAI 风格 SSE 行中聚合 choices[0].delta.content（忽略思考与心跳）。"""
    parts: list[str] = []
    for line in lines:
        if not line or not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = obj.get("choices") or []
        if not choices:
            continue
        content = choices[0].get("delta", {}).get("content")
        if content:
            parts.append(content)
    return "".join(parts)


def _raise_compat_error(resp: requests.Response) -> None:
    """兼容端点错误（OpenAI 风格 {"error": {...}}）转成 DashScopeError。"""
    body = _try_json(resp.text)
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    raise DashScopeError(
        status_code=resp.status_code,
        code=err.get("code") or body.get("code"),
        message=err.get("message") or body.get("message", resp.text),
        request_id=body.get("request_id") or body.get("id"),
    )

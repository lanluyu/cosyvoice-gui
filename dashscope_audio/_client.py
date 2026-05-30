# coding: utf-8
"""DashScope HTTP 调用的公共封装：鉴权、错误处理、SSE 流式解析、文件下载。

三个语音接口（CosyVoice 合成 / Qwen-TTS 合成 / 声音复刻）共用同一套
请求范式，差异仅在 URL 与请求体，因此把通用逻辑收敛到这里。
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Iterator

import requests

from .config import Settings

logger = logging.getLogger(__name__)

# 默认超时（秒）：连接 10s，读取 300s（语音合成 / 复刻可能耗时较长）
DEFAULT_TIMEOUT: tuple[int, int] = (10, 300)


class DashScopeError(RuntimeError):
    """接口返回非 2xx，或返回体中带有业务错误码时抛出。"""

    def __init__(
        self,
        status_code: int,
        code: str | None,
        message: str,
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(
            f"[HTTP {status_code}] code={code!r} message={message!r} request_id={request_id!r}"
        )


def _headers(settings: Settings, *, sse: bool = False) -> dict[str, str]:
    """构造请求头：Bearer 鉴权 + JSON 媒体类型；流式时额外开启 SSE。"""
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    if sse:
        # 仅流式合成时使用，固定值 enable
        headers["X-DashScope-SSE"] = "enable"
    return headers


def _proxies(settings: Settings) -> dict[str, str] | None:
    """requests 用的代理表：优先 settings.proxy，否则回退环境变量代理。

    requests 默认只认环境变量代理、不读 Windows 系统代理设置；在 PyCharm 等
    不继承 shell 代理 env 的环境里需由 settings.proxy 显式指定。
    """
    if settings.proxy:
        p = settings.proxy if "://" in settings.proxy else f"http://{settings.proxy}"
        return {"http": p, "https": p}
    env = urllib.request.getproxies()
    return env or None


def post_json(settings: Settings, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """发送非流式 POST 请求并返回解析后的 JSON。

    path: 相对 http_base 的路径，例如 "/services/audio/tts/SpeechSynthesizer"。
    """
    url = settings.http_base + path
    logger.debug("POST %s payload=%s", url, _safe_log(payload))
    resp = requests.post(
        url, json=payload, headers=_headers(settings),
        timeout=DEFAULT_TIMEOUT, proxies=_proxies(settings),
    )
    return _parse_response(resp)


def post_sse(
    settings: Settings, path: str, payload: dict[str, Any]
) -> Iterator[dict[str, Any]]:
    """发送流式 POST 请求，逐条 yield SSE 事件里的 JSON 数据。

    DashScope 的 SSE 每条事件形如 ``data: {...}``，以空行分隔；
    这里只关心 ``data:`` 行，跳过空行和心跳。
    """
    url = settings.http_base + path
    logger.debug("POST(SSE) %s payload=%s", url, _safe_log(payload))
    with requests.post(
        url,
        json=payload,
        headers=_headers(settings, sse=True),
        timeout=DEFAULT_TIMEOUT,
        stream=True,
        proxies=_proxies(settings),
    ) as resp:
        if resp.status_code != 200:
            _raise_for_error(resp.status_code, _try_json(resp.text))
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data in ("", "[DONE]"):
                continue
            yield json.loads(data)


def download_to_file(
    url: str, dest_path: str, settings: Settings, *, retries: int = 2
) -> None:
    """把合成结果的音频 URL 下载到本地文件（合成接口常只返回 URL）。

    走与 API 相同的代理；失败重试，最终失败转成带中文提示的 DashScopeError
    （说明音频已合成、问题在本地下载，引导检查代理）。
    """
    logger.debug("下载音频: %s -> %s", url, dest_path)
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with requests.get(
                url, stream=True, timeout=DEFAULT_TIMEOUT, proxies=_proxies(settings)
            ) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            return
        except requests.RequestException as err:
            last_err = err
            logger.warning("下载失败(第 %d/%d 次): %s", attempt + 1, retries + 1, err)
    raise DashScopeError(
        0,
        "DownloadFailed",
        f"音频已合成成功（URL 24 小时内有效），但下载到本地失败：{last_err}。"
        "常见原因：请求未走代理或本地无法解析 OSS 域名——请在界面「代理」处填写代理后重试。",
        None,
    )


def _parse_response(resp: requests.Response) -> dict[str, Any]:
    """统一解析返回体：HTTP 错误或业务错误码都转成 DashScopeError。"""
    body = _try_json(resp.text)
    if resp.status_code != 200:
        _raise_for_error(resp.status_code, body)
    # 个别接口即便 HTTP 200，也可能在返回体里带非空 code 表示业务失败
    if body.get("code"):
        _raise_for_error(resp.status_code, body)
    return body


def _raise_for_error(status_code: int, body: dict[str, Any]) -> None:
    raise DashScopeError(
        status_code=status_code,
        code=body.get("code"),
        message=body.get("message", ""),
        request_id=body.get("request_id"),
    )


def _try_json(text: str) -> dict[str, Any]:
    """尽量把响应体解析为 dict；非 JSON 时把原文塞进 message 字段。"""
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"data": parsed}
    except (ValueError, TypeError):
        return {"message": text}


def _safe_log(payload: dict[str, Any], max_len: int = 120) -> str:
    """日志脱敏：音频 base64 / data URI 可能极长，记录前递归截断长字符串。"""

    def trunc(value: Any) -> Any:
        if isinstance(value, str) and len(value) > max_len:
            return value[:max_len] + f"...<{len(value)} chars>"
        if isinstance(value, dict):
            return {k: trunc(v) for k, v in value.items()}
        if isinstance(value, list):
            return [trunc(v) for v in value]
        return value

    return json.dumps(trunc(payload), ensure_ascii=False)

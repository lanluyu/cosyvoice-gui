# coding: utf-8
"""阿里云百炼（DashScope）语音服务的全局配置。

集中管理 API Key、服务地域与各类 base url，避免在业务代码里硬编码。
API Key 通过环境变量 DASHSCOPE_API_KEY 注入，禁止写入源码或提交到 Git。

注意：北京（中国内地）与新加坡（国际）两个地域的 API Key 互不通用，
base url 也不同，调用前务必选对地域。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class Region(str, Enum):
    """服务地域。"""

    BEIJING = "beijing"      # 中国内地（北京）
    SINGAPORE = "singapore"  # 国际（新加坡）


# 各地域的 HTTP REST base url（不含具体业务路径）
_HTTP_BASE: dict[Region, str] = {
    Region.BEIJING: "https://dashscope.aliyuncs.com/api/v1",
    Region.SINGAPORE: "https://dashscope-intl.aliyuncs.com/api/v1",
}


@dataclass(frozen=True)
class Settings:
    """一次调用所需的运行时配置（不可变）。"""

    api_key: str
    region: Region = Region.BEIJING
    proxy: str | None = None  # 代理地址（如 http://127.0.0.1:7890）；None 时回退环境变量代理

    @property
    def http_base(self) -> str:
        """当前地域对应的 HTTP REST base url。"""
        return _HTTP_BASE[self.region]


def load_settings(
    region: Region = Region.BEIJING,
    api_key: str | None = None,
    proxy: str | None = None,
) -> Settings:
    """加载配置。

    优先使用显式传入的 api_key；否则读取环境变量 DASHSCOPE_API_KEY。
    两者都缺失时抛出异常，避免把空 Key 带到请求里产生难懂的 401。
    """
    key = api_key or os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError(
            "未找到 API Key：请设置环境变量 DASHSCOPE_API_KEY，或显式传入 api_key 参数"
        )
    return Settings(api_key=key, region=region, proxy=proxy)

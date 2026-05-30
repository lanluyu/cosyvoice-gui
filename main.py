# coding: utf-8
"""阿里云百炼语音能力调用样例（统一入口）。

只做启动入口与调用演示，业务逻辑都在 dashscope_audio 包内。
运行前需设置环境变量 DASHSCOPE_API_KEY（北京地域 Key）。

用法：
    conda run -n trade python main.py            # 默认跑 qwen-tts 样例
    conda run -n trade python main.py cosyvoice  # CosyVoice 合成
    conda run -n trade python main.py qwen       # Qwen-TTS 合成
    conda run -n trade python main.py clone      # 声音复刻（create/list/delete）
    conda run -n trade python main.py list        # 仅查询当前音色列表
    conda run -n trade python main.py all        # 依次跑前两个合成样例
"""
from __future__ import annotations

import logging
import sys

from dashscope_audio import (
    DashScopeError,
    cosyvoice_tts,
    load_settings,
    qwen_tts,
    voice_clone,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def demo_qwen_tts() -> None:
    """Qwen-TTS 非实时合成：基础调用 + 流式落盘。"""
    settings = load_settings()  # 默认北京地域，从环境变量读 Key
    text = "那我来给大家推荐一款T恤，颜色很显气质，搭配绝佳。"

    # 非流式：返回音频 URL 并下载为本地文件
    result = qwen_tts.synthesize_to_file(
        settings, text=text, dest_path="out_qwen.wav", voice="Cherry"
    )
    print(f"[qwen] 非流式完成 request_id={result.request_id}")

    # 流式：边收边写
    qwen_tts.synthesize_stream_to_file(
        settings, text=text, dest_path="out_qwen_stream.wav", voice="Cherry"
    )
    print("[qwen] 流式完成 out_qwen_stream.wav")


def demo_cosyvoice() -> None:
    """CosyVoice 非实时合成：非流式下载 + 流式 mp3。"""
    settings = load_settings()
    text = "我家的后面有一个很大的花园。"

    result = cosyvoice_tts.synthesize_to_file(
        settings,
        text=text,
        voice="longanyang",
        dest_path="out_cosyvoice.wav",
        # model="cosyvoice-v3-flash",
        model="cosyvoice-v3.5-plus",
        format="wav",
        sample_rate=24000,
    )
    print(f"[cosyvoice] 非流式完成 chars={result.characters}")

    cosyvoice_tts.synthesize_stream_to_file(
        settings,
        text=text,
        voice="longanyang",
        dest_path="out_cosyvoice_stream.mp3",
        model="cosyvoice-v3-flash",
        format="mp3",
    )
    print("[cosyvoice] 流式完成 out_cosyvoice_stream.mp3")


def demo_list_voices() -> None:
    """仅查询当前账号下已创建的音色列表（不创建、不删除，查询免费）。"""
    settings = load_settings()

    # 分页拉取全部音色：逐页查询直到某页返回数量不足 page_size
    page_size = 50
    page_index = 0
    all_voices: list[voice_clone.VoiceInfo] = []
    while True:
        page = voice_clone.list_voices(
            settings, page_index=page_index, page_size=page_size
        )
        all_voices.extend(page)
        if len(page) < page_size:
            break
        page_index += 1

    print(f"[list] 当前音色数 {len(all_voices)}")
    for v in all_voices:
        print(f"        {v.voice_id}  {v.status}  {v.gmt_create}  {v.target_model}")


def demo_voice_clone() -> None:
    """CosyVoice 声音复刻：创建音色 -> 轮询就绪 -> 用复刻音色合成 -> 删除。

    样本音频通过公网 URL 提交（这里用官方示例音频）。
    target_model 必须与后续合成时的 model 一致，否则合成失败。
    """
    settings = load_settings()
    target_model = "cosyvoice-v3.5-plus"
    # 公网可访问的样本音频 URL（请替换为自己的，建议上传到 OSS）
    sample_url = (
        "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/"
        "cosyvoice/cosyvoice-zeroshot-sample.wav"
    )

    info = voice_clone.create_voice(
        settings, url=sample_url, target_model=target_model, prefix="demo"
    )
    print(f"[clone] 创建已提交 voice_id={info.voice_id}")

    # 复刻是异步任务，轮询至就绪
    ready = voice_clone.wait_until_ready(settings, info.voice_id)
    print(f"[clone] 音色就绪 status={ready.status}")

    # 用复刻音色合成（模型必须等于创建时的 target_model）
    cosyvoice_tts.synthesize_to_file(
        settings,
        text="恭喜，已成功复刻并合成了属于自己的声音。",
        voice=info.voice_id,
        dest_path="out_clone.wav",
        model=target_model,
        format="wav",
    )
    print("[clone] 合成完成 out_clone.wav")

    # 清理（演示用；实际可保留供后续合成）
    voice_clone.delete_voice(settings, info.voice_id)
    print(f"[clone] 已删除 {info.voice_id}")


# 子命令到样例函数的映射
_DEMOS = {
    "qwen": demo_qwen_tts,
    "cosyvoice": demo_cosyvoice,
    "clone": demo_voice_clone,
    "list": demo_list_voices,
}


def _hint_for_error(err: DashScopeError) -> str:
    """根据错误码给出中文排查建议，降低看到英文报错时的排查成本。"""
    code = err.code or ""
    if code == "AllocationQuota.FreeTierOnly":
        return "模型免费额度已用尽：请在百炼控制台关闭「仅使用免费额度」模式，或确认已开通付费。"
    if err.status_code == 401 or code in ("InvalidApiKey", "Unauthorized"):
        return "鉴权失败：检查 DASHSCOPE_API_KEY 是否正确、是否与当前地域（北京/新加坡）匹配。"
    if code == "Throttling.RateQuota":
        return "触发限流：稍后重试或降低并发。"
    if code.startswith("Audio.") or code == "InvalidParameter":
        return "请求参数或音频不合规：检查文本长度、音色名、音频格式与时长是否满足要求。"
    return "请对照错误码文档排查：https://help.aliyun.com/zh/model-studio/error-code"


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else "qwen"
    demo = _DEMOS.get(cmd)
    if cmd != "all" and demo is None:
        print(f"未知子命令: {cmd}；可选: {', '.join(_DEMOS)}, all")
        sys.exit(2)

    try:
        if cmd == "all":
            demo_qwen_tts()
            demo_cosyvoice()
        else:
            demo()
    except DashScopeError as err:
        # 把英文业务错误转成中文提示，并保留 request_id 方便提工单
        print(f"调用失败 [{err.code or err.status_code}]: {err.message}")
        print(f"建议: {_hint_for_error(err)}")
        if err.request_id:
            print(f"request_id: {err.request_id}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)

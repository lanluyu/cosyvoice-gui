# coding: utf-8
"""示例：经百炼 OpenAI 兼容模式调用 qwen3.7-max 深度思考模型（流式）。

演示 reasoning_content（思考过程）与 content（最终回复）的流式区分。项目内 GUI 的
多音字识别 / 风格指令生成已用 requests 重写为 dashscope_audio.llm.chat（无需 openai
依赖），本脚本仅作底层协议参考。

依赖：pip install openai；运行前设置环境变量 DASHSCOPE_API_KEY。
"""
import os

from openai import OpenAI

client = OpenAI(
	# 如果没有配置环境变量，请用阿里云百炼API Key替换：api_key="sk-xxx"
	api_key=os.getenv("DASHSCOPE_API_KEY"),
	base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

messages = [{"role": "user", "content": "你是谁"}]
completion = client.chat.completions.create(
	model="qwen3.7-max",  # 您可以按需更换为其它深度思考模型
	messages=messages,
	extra_body={"enable_thinking": True},
	stream=True
)
is_answering = False  # 是否进入回复阶段
print("\n" + "=" * 20 + "思考过程" + "=" * 20)
for chunk in completion:
	if not chunk.choices:
		continue
	delta = chunk.choices[0].delta
	if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
		if not is_answering:
			print(delta.reasoning_content, end="", flush=True)
	if hasattr(delta, "content") and delta.content:
		if not is_answering:
			print("\n" + "=" * 20 + "完整回复" + "=" * 20)
			is_answering = True
		print(delta.content, end="", flush=True)
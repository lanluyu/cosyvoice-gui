# coding: utf-8
"""示例：用原始 HTTP（requests）查询百炼 CosyVoice 音色列表。

演示 customization 端点 action=list 的裸调用，便于理解底层请求；生产代码请改用
封装好的 dashscope_audio.voice_clone.list_voices（含鉴权、分页、错误处理与地域切换）。

运行：先设置环境变量 DASHSCOPE_API_KEY，再 python examples/list_voices_raw.py
"""
import os

import requests

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
api_key = os.getenv("DASHSCOPE_API_KEY")
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization
url = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"

payload = {
	"model": "cosyvoice-v3-plus", # 不要修改该值
	"input": {
		"action": "list",
		"page_size": 10,
		"page_index": 0
	}
}

headers = {
	"Authorization": f"Bearer {api_key}",
	"Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print("HTTP 状态码:", response.status_code)

if response.status_code == 200:
	data = response.json()
	voice_list = data["output"]["voice_list"]
	
	print("查询到的音色列表：")
	for item in voice_list:
		print(f"- 音色: {item['voice']}  创建时间: {item['gmt_create']}  模型: {item['target_model']}")
else:
	print("请求失败:", response.text)

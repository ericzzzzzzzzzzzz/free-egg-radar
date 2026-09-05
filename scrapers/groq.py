"""Groq 免费模型池抓取器（官方 API/文档，所有模型免费调用，限速）

数据源：https://api.groq.com/openai/v1/models（需 API Key）或 https://console.groq.com/docs/models
产出：一条聚合蛋——Groq 免费模型池（注册即取 API Key，所有模型免费调用，高速推理）。
"""

import os
import re
from datetime import date
from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

API_URL = "https://api.groq.com/openai/v1/models"
DOCS_URL = "https://console.groq.com/docs/models"
LINK = "https://console.groq.com/docs/models"
SIGNUP_LINK = "https://console.groq.com/"


class GroqScraper(BaseScraper):
    name = "groq"

    def scrape(self) -> List[Egg]:
        models = []

        # 方式1：如果配置了 GROQ_API_KEY，用官方 API 获取模型列表
        api_key = os.environ.get("GROQ_API_KEY", "")
        if api_key:
            try:
                resp = self._get(
                    API_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for m in data:
                        mid = m.get("id", "")
                        if mid and mid not in models:
                            models.append(mid)
            except Exception:
                pass

        # 方式2：尝试抓取文档页
        if not models:
            try:
                resp = self._get(
                    DOCS_URL,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    },
                )
                text = re.sub(r"<[^>]+>", " ", resp.text)
                text = re.sub(r"\s+", " ", text)
                # 提取模型名
                for m in re.finditer(r"([\w\-]+-[\w\-\.]+(?:-[\w\-\.]+)*)", text):
                    name = m.group(1)
                    if any(k in name.lower() for k in ["llama", "mixtral", "gemma", "mistral", "qwen", "deepseek"]):
                        if name not in models:
                            models.append(name)
            except Exception:
                pass

        # 方式3：兜底——Groq 常见支持模型（长期稳定）
        if not models:
            models = [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
                "llama-guard-3-8b",
                "whisper-large-v3",
            ]

        today = date.today().isoformat()
        model_names = "、".join(models[:6])
        if len(models) > 6:
            model_names += f" 等 {len(models)} 款"

        egg = Egg(
            id=f"groq-free-{today}",
            title=f"Groq 免费模型池（{len(models)} 款模型 · 高速推理）",
            vendor="Groq",
            category="api-quota",
            score=0.0,
            summary=f"注册即取 API Key，{model_names} 免费调用，LPU 高速推理",
            content=(
                f"Groq 官方 API/文档自动探测（{today} 快照）。\n\n"
                f"- **免费层**：所有模型免费调用，注册即取 API Key\n"
                f"- **覆盖模型**：{model_names}\n"
                f"- **推理速度**：LPU 芯片加速，tokens/s 远超传统 GPU\n"
                f"- **速率限制**：免费层约 30 RPM（每分钟请求数），并发 1\n"
                f"- **功能**：Chat Completion、JSON Mode、Function Calling、Whisper 语音转文字\n\n"
                f"使用步骤：\n\n"
                f"1. 打开 [Groq Console]({SIGNUP_LINK}) 注册账号\n"
                f"2. 在 API Keys 页面创建免费 API Key\n"
                f"3. 调用 Groq API（OpenAI 兼容格式，base_url=https://api.groq.com/openai/v1）即可\n\n"
                f"**注意**：免费层有 RPM 限制，超出后返回 429；模型清单以 [官方文档]({LINK}) 为准。"
                f"本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "longterm", "region": "global"},
            published_at=today,
            updated_at=today,
            source="groq",
        )
        egg._quota = None
        egg._unit = "api-quota"
        egg._threshold = "注册即用"
        return [egg]

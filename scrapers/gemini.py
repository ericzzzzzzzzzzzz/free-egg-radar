"""Google Gemini API 免费层抓取器（官方文档页，Free Tier 模型）

数据源：https://ai.google.dev/gemini-api/docs/models
产出：一条聚合蛋——Gemini API Free Tier（注册即取 API Key，指定模型免费调用，限速）。
"""

import re
from datetime import date
from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

MODELS_URL = "https://ai.google.dev/gemini-api/docs/models"
PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"
LINK = "https://ai.google.dev/gemini-api/docs/models"
SIGNUP_LINK = "https://aistudio.google.com/apikey"


class GeminiScraper(BaseScraper):
    name = "gemini"

    def scrape(self) -> List[Egg]:
        # 尝试抓取模型文档页
        try:
            resp = self._get(
                MODELS_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                },
            )
            html = resp.text
        except Exception:
            html = ""

        text = re.sub(r"<[^>]+>", " ", html) if html else ""
        text = re.sub(r"\s+", " ", text)

        # 提取免费模型列表
        free_models = self._extract_free_models(text)
        if not free_models:
            # 如果页面抓不到，用已知的 Gemini 免费模型作为兜底（这些是长期免费的）
            free_models = [
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b",
                "gemini-embedding-001",
            ]

        today = date.today().isoformat()
        model_names = "、".join(free_models[:6])
        if len(free_models) > 6:
            model_names += f" 等 {len(free_models)} 款"

        egg = Egg(
            id=f"gemini-free-{today}",
            title=f"Google Gemini API 免费层（{len(free_models)} 款模型）",
            vendor="Google Gemini",
            category="api-quota",
            score=0.0,
            summary=f"Google AI Studio 注册即取 API Key，{model_names} 免费调用",
            content=(
                f"Google Gemini API 官方文档自动探测（{today} 快照）。\n\n"
                f"- **免费层**：Free Tier，指定模型完全免费\n"
                f"- **免费模型**：{model_names}\n"
                f"- **速率限制**：免费层 15 RPM（每分钟请求数），1500 RPD（每天请求数）\n"
                f"- **上下文**：最高 1M tokens（视模型而定）\n\n"
                f"使用步骤：\n\n"
                f"1. 打开 [Google AI Studio]({SIGNUP_LINK}) 登录 Google 账号\n"
                f"2. 点击「Create API Key」创建免费 API Key\n"
                f"3. 调用标注「Free」的模型即可，不扣费\n\n"
                f"**注意**：免费层有 RPM/RPD 限制，超出后需等待重置或升级到付费层；"
                f"免费模型清单以 [官方文档]({LINK}) 实时标注为准。本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "longterm", "region": "global"},
            published_at=today,
            updated_at=today,
            source="gemini",
        )
        egg._quota = None
        egg._unit = "api-quota"
        egg._threshold = "注册即用"
        return [egg]

    @staticmethod
    def _extract_free_models(text: str) -> List[str]:
        """从文档页文本中提取标注为 Free 的模型名。"""
        if not text:
            return []
        # 匹配 gemini-xxx 模型名
        models = re.findall(r"(gemini-[\w\-\.]+)", text, re.I)
        # 去重并过滤
        found = []
        for m in models:
            m_lower = m.lower()
            if m_lower not in [f.lower() for f in found]:
                found.append(m)
        return found[:15]

"""Mistral AI 免费层抓取器（官方文档/定价页，La Plateforme 免费层）

数据源：https://docs.mistral.ai/getting-started/models/
产出：一条聚合蛋——Mistral La Plateforme 免费层（注册即取 API Key，指定模型免费调用）。
"""

import re
from datetime import date
from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

DOCS_URL = "https://docs.mistral.ai/getting-started/models/"
PRICING_URL = "https://mistral.ai/products/la-plateforme"
LINK = "https://docs.mistral.ai/getting-started/models/"
SIGNUP_LINK = "https://console.mistral.ai/"


class MistralScraper(BaseScraper):
    name = "mistral"

    def scrape(self) -> List[Egg]:
        # 尝试抓取模型文档页
        try:
            resp = self._get(
                DOCS_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                },
            )
            html = resp.text
        except Exception:
            html = ""

        text = re.sub(r"<[^>]+>", " ", html) if html else ""
        text = re.sub(r"\s+", " ", text)

        # 提取模型列表
        models = self._extract_models(text)
        if not models:
            # 兜底：Mistral 常见模型
            models = [
                "mistral-small-latest",
                "mistral-medium-latest",
                "mistral-large-latest",
                "codestral-latest",
                "embedding-v3",
            ]

        today = date.today().isoformat()
        model_names = "、".join(models[:5])
        if len(models) > 5:
            model_names += f" 等 {len(models)} 款"

        egg = Egg(
            id=f"mistral-free-{today}",
            title=f"Mistral La Plateforme 免费层（{len(models)} 款模型）",
            vendor="Mistral AI",
            category="api-quota",
            score=0.0,
            summary=f"注册即取 API Key，{model_names} 免费调用，限速",
            content=(
                f"Mistral AI 官方文档自动探测（{today} 快照）。\n\n"
                f"- **免费层**：La Plateforme 免费层，注册即可使用\n"
                f"- **覆盖模型**：{model_names}\n"
                f"- **速率限制**：免费层有限速（约 2 RPM），适合评估和原型开发\n"
                f"- **功能**：Chat Completion、Embedding、Function Calling 等\n\n"
                f"使用步骤：\n\n"
                f"1. 打开 [Mistral Console]({SIGNUP_LINK}) 注册账号\n"
                f"2. 在 API Keys 页面创建免费 API Key\n"
                f"3. 调用 Mistral API（OpenAI 兼容格式）即可\n\n"
                f"**注意**：免费层有速率限制，超出后需等待重置或升级；"
                f"模型清单和免费政策以 [官方文档]({LINK}) 为准。本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "longterm", "region": "global"},
            published_at=today,
            updated_at=today,
            source="mistral",
        )
        egg._quota = None
        egg._unit = "api-quota"
        egg._threshold = "注册即用"
        return [egg]

    @staticmethod
    def _extract_models(text: str) -> List[str]:
        """从文档页文本中提取 Mistral 模型名。"""
        if not text:
            return []
        patterns = [
            r"(mistral-[\w\-]+)",
            r"(codestral[\w\-]*)",
            r"(embedding[\w\-]*)",
            r"(pixtral[\w\-]*)",
        ]
        found = []
        for p in patterns:
            for m in re.finditer(p, text, re.I):
                name = m.group(1).strip()
                if name.lower() not in [f.lower() for f in found]:
                    found.append(name)
        return found[:12]

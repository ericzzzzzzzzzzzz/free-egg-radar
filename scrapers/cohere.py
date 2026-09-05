"""Cohere 定价页抓取器（官方公开页面，Trial 层免费）

数据源：https://cohere.com/pricing
产出：一条聚合蛋——Cohere Trial 免费层（注册即取 API Key，所有模型免费调用，限速）。
"""

import re
from datetime import date
from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

PRICING_URL = "https://cohere.com/pricing"
LINK = "https://cohere.com/pricing"
SIGNUP_LINK = "https://dashboard.cohere.com/welcome/register"


class CohereScraper(BaseScraper):
    name = "cohere"

    def scrape(self) -> List[Egg]:
        resp = self._get(
            PRICING_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            },
        )
        resp.raise_for_status()
        html = resp.text

        # 验证页面包含 Trial 免费信息
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        if "Trial" not in text and "trial" not in text:
            return []
        if "free" not in text.lower():
            return []

        # 提取 Trial 层的关键信息（速率限制、模型列表等）
        models = self._extract_models(text)
        rate_limit = self._extract_rate_limit(text)

        today = date.today().isoformat()
        model_names = "、".join(models[:8]) if models else "Command R、Command R+、Embed 等"

        egg = Egg(
            id=f"cohere-trial-{today}",
            title="Cohere Trial 免费层（注册即取 API Key）",
            vendor="Cohere",
            category="api-quota",
            score=0.0,
            summary="注册即获 Trial API Key，所有模型免费调用，限速 10 RPM",
            content=(
                f"Cohere 官方定价页自动探测（{today} 快照）。\n\n"
                f"- **免费层**：Trial API Key 调用完全免费\n"
                f"- **覆盖模型**：{model_names}\n"
                f"- **速率限制**：{rate_limit}\n"
                f"- **用途限制**：Trial Key 仅限评估和原型开发，不可用于生产\n\n"
                f"使用步骤：\n\n"
                f"1. 打开 [Cohere 注册页]({SIGNUP_LINK}) 注册账号\n"
                f"2. 在 Dashboard 创建 API Key（默认 Trial 层）\n"
                f"3. 调用 Cohere API（Chat / Embed / Rerank 等）即可，不扣费\n\n"
                f"**注意**：Trial Key 有速率限制且不可用于生产环境；如需生产用量需升级到 Production 层。"
                f"本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "longterm", "region": "global"},
            published_at=today,
            updated_at=today,
            source="cohere",
        )
        egg._quota = None
        egg._unit = "api-quota"
        egg._threshold = "注册即用"
        return [egg]

    @staticmethod
    def _extract_models(text: str) -> List[str]:
        """从页面文本中提取 Cohere 模型名。"""
        patterns = [
            r"(Command R\+?)",
            r"(Command [A-Z][\w\-]*)",
            r"(Embed [\w\-]+)",
            r"(Rerank [\w\-]+)",
        ]
        found = []
        for p in patterns:
            for m in re.finditer(p, text):
                name = m.group(1).strip()
                if name not in found:
                    found.append(name)
        return found

    @staticmethod
    def _extract_rate_limit(text: str) -> str:
        """提取 Trial 层的速率限制。"""
        m = re.search(r"(\d+)\s*(RPM|requests per minute|calls per minute)", text, re.I)
        if m:
            return f"{m.group(1)} {m.group(2).upper()}"
        # 默认值
        return "10 RPM（每分钟 10 次请求）"

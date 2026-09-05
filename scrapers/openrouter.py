"""OpenRouter 免费模型池抓取器（官方公开 API，无需密钥）

数据源：https://openrouter.ai/api/v1/models
产出：一条聚合蛋——当前定价为 $0 的免费模型清单。
"""

from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

API_URL = "https://openrouter.ai/api/v1/models"
LINK = "https://openrouter.ai/models?max_price=0"


class OpenRouterScraper(BaseScraper):
    name = "openrouter"

    def scrape(self) -> List[Egg]:
        resp = self._get(API_URL)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        free_models = []
        for m in data:
            pricing = m.get("pricing") or {}
            prompt = str(pricing.get("prompt") or "0").strip()
            completion = str(pricing.get("completion") or "0").strip()
            if prompt == "0" and completion == "0":
                free_models.append({
                    "id": m.get("id", ""),
                    "name": m.get("name", m.get("id", "")),
                    "ctx": m.get("context_length"),
                })

        if not free_models:
            return []

        today = __import__("datetime").date.today().isoformat()
        names = "、".join([f["name"] for f in free_models[:12]])
        if len(free_models) > 12:
            names += f" 等 {len(free_models)} 款"

        egg = Egg(
            id=f"openrouter-free-{today}",
            title=f"OpenRouter 免费模型池（{len(free_models)} 款 $0 模型）",
            vendor="OpenRouter",
            category="api-quota",
            score=0.0,  # 由评分引擎计算
            summary=f"官方 API 实时探测：当前 {len(free_models)} 款模型输入/输出均免费",
            content=(
                f"OpenRouter 聚合网关免费模型池，由官方公开 API 自动探测（{today} 快照）。\n\n"
                f"- 免费模型数：**{len(free_models)} 款**（pricing 均为 $0）\n"
                f"- 代表模型：{names}\n"
                f"- 接入：OpenAI 兼容 API，注册创建 Key 后调用 `:free` 后缀模型\n\n"
                f"使用步骤：\n\n1. 打开 [OpenRouter 免费模型页]({LINK}) 筛选 Free\n2. 注册并创建 API Key\n3. 调用标注 Free 的模型即可\n\n"
                f"**注意**：免费模型上下架频繁，额度与限速以模型页实时标注为准；本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "longterm", "region": "global"},
            published_at=today,
            updated_at=today,
            source="openrouter",
        )
        # 评分用元数据
        egg._quota = None
        egg._unit = "api-quota"
        egg._threshold = "注册即用"
        return [egg]

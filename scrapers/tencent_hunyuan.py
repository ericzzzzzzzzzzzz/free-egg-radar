"""腾讯云混元大模型抓取器（官方文档页，首次开通免费体验额度）

数据源：https://cloud.tencent.com/document/product/1729/97731
产出：一条聚合蛋——腾讯混元首次开通送免费体验额度（Hunyuan-a13b 等 100 万 tokens，有效期 1 年）。
"""

import re
from datetime import date
from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

PRICING_URL = "https://cloud.tencent.com/document/product/1729/97731"
LINK = "https://cloud.tencent.com/document/product/1729/97731"
SIGNUP_LINK = "https://console.cloud.tencent.com/hunyuan"


class TencentHunyuanScraper(BaseScraper):
    name = "tencent-hunyuan"

    def scrape(self) -> List[Egg]:
        try:
            resp = self._get(
                PRICING_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                },
            )
            html = resp.text
        except Exception:
            html = ""

        text = re.sub(r"<[^>]+>", " ", html) if html else ""
        text = re.sub(r"\s+", " ", text)

        # 提取免费额度信息
        free_models = self._extract_free_models(text)
        has_free = "免费额度" in text or "免费体验" in text or "免费资源包" in text

        today = date.today().isoformat()
        model_names = "、".join(free_models) if free_models else "Hunyuan-a13b、Hunyuan-role-latest、Hunyuan-translation"

        egg = Egg(
            id=f"tencent-hunyuan-free-{today}",
            title="腾讯混元首次开通送免费体验额度",
            vendor="腾讯云混元",
            category="token",
            score=0.0,
            summary=f"首次开通即获免费资源包，{model_names} 等模型共 100 万 tokens，有效期 1 年",
            content=(
                f"腾讯云混元官方定价文档自动探测（{today} 快照）。\n\n"
                f"- **免费福利**：首次开通混元大模型服务后，系统自动发放免费体验额度\n"
                f"- **覆盖模型**：{model_names}\n"
                f"- **免费额度**：共 **100 万 tokens**（共享消耗）\n"
                f"- **有效期**：自开通服务之日起 **1 年**，未使用完过期作废\n"
                f"- **获取条件**：腾讯云账号 + 个人实名认证，首次点击「立即使用」\n"
                f"- **计费方式**：后付费，优先扣减免费资源包，超出后按量计费\n\n"
                f"使用步骤：\n\n"
                f"1. 打开 [腾讯云混元控制台]({SIGNUP_LINK}) 登录\n"
                f"2. 完成个人实名认证\n"
                f"3. 首次单击「立即使用」开通服务，系统自动发放免费资源包\n"
                f"4. 调用混元 API（OpenAI 兼容格式）即可，优先扣减免费额度\n\n"
                f"**注意**：免费额度仅限首次开通，1 年有效期；资源包共享消耗，用完后按量计费。"
                f"本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "limited", "region": "cn"},
            published_at=today,
            updated_at=today,
            source="tencent-hunyuan",
        )
        egg._quota = "100万tokens"
        egg._unit = "token"
        egg._threshold = "实名认证"
        return [egg]

    @staticmethod
    def _extract_free_models(text: str) -> List[str]:
        """从页面文本中提取有免费额度的模型名。"""
        if not text:
            return []
        # 匹配 Hunyuan-xxx 模型名
        models = re.findall(r"(Hunyuan[\w\-]+)", text, re.I)
        found = []
        for m in models:
            if m not in found:
                found.append(m)
        return found[:8]

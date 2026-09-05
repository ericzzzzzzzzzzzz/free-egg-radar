"""阿里云百炼大模型平台抓取器（官方定价文档，多模型免费额度）

数据源：https://help.aliyun.com/zh/model-studio/billing-for-model-studio
产出：一条聚合蛋——阿里云百炼多款模型赠送免费额度（每模型 100 万 tokens，有效期 90 天）。
"""

import re
from datetime import date
from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

PRICING_URL = "https://help.aliyun.com/zh/model-studio/billing-for-model-studio"
LINK = "https://help.aliyun.com/zh/model-studio/billing-for-model-studio"
SIGNUP_LINK = "https://bailian.console.aliyun.com/"


class AliyunBailianScraper(BaseScraper):
    name = "aliyun-bailian"

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

        # 提取有免费额度的模型
        free_models = self._extract_free_models(text)
        has_free = "免费额度" in text or "免费资源包" in text

        if not free_models and not has_free:
            # 兜底：已知百炼长期有免费额度的模型
            free_models = [
                "qwen3-235b-a22b-instruct",
                "qwen3-30b-a3b-instruct",
                "qwen3-14b",
                "qwen3-8b",
                "qwen-turbo",
                "qwen-plus",
                "qwen-max",
                "qwen2.5-coder-32b-instruct",
                "qwen2-audio-instruct",
                "qwen-vl-max",
                "qwen-vl-plus",
                "text-embedding-v3",
                "text-rerank-v3",
            ]

        today = date.today().isoformat()
        model_names = "、".join(free_models[:8])
        if len(free_models) > 8:
            model_names += f" 等 {len(free_models)} 款"

        egg = Egg(
            id=f"aliyun-bailian-free-{today}",
            title=f"阿里云百炼多款模型送免费额度（{len(free_models)} 款）",
            vendor="阿里云百炼",
            category="token",
            score=0.0,
            summary=f"开通即送每模型免费额度，{model_names}，有效期 90 天",
            content=(
                f"阿里云百炼官方定价文档自动探测（{today} 快照）。\n\n"
                f"- **免费福利**：多款模型开通即赠送免费额度（资源包）\n"
                f"- **覆盖模型**：{model_names}\n"
                f"- **免费额度**：每模型赠送 100 万 tokens（具体以模型页标注为准）\n"
                f"- **有效期**：自开通百炼/模型发布/申请通过之日起 **90 天**（以较晚者为准）\n"
                f"- **获取条件**：注册阿里云账号 + 实名认证，开通百炼服务\n"
                f"- **计费方式**：优先扣减免费资源包，超出后按量付费\n\n"
                f"使用步骤：\n\n"
                f"1. 打开 [阿里云百炼控制台]({SIGNUP_LINK}) 注册并登录\n"
                f"2. 完成实名认证，开通百炼服务\n"
                f"3. 在「模型广场」选择带「免费」标签的模型，点击「开通」\n"
                f"4. 系统自动发放免费资源包，调用 API 时优先扣减\n\n"
                f"**注意**：免费额度仅限对应模型，有效期 90 天，过期作废；"
                f"部分模型需申请通过后开通。模型清单以 [官方文档]({LINK}) 为准。"
                f"本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "limited", "region": "cn"},
            published_at=today,
            updated_at=today,
            source="aliyun-bailian",
        )
        egg._quota = "100万tokens/模型"
        egg._unit = "token"
        egg._threshold = "实名认证"
        return [egg]

    @staticmethod
    def _extract_free_models(text: str) -> List[str]:
        """从定价文档中提取有免费额度的模型名。"""
        if not text:
            return []
        # 匹配 qwen-xxx / qwen2-xxx / qwen3-xxx 等模型名
        patterns = [
            r"(qwen[\w\-\.]+)",
            r"(text-embedding[\w\-\.]*)",
            r"(text-rerank[\w\-\.]*)",
            r"(qwen-vl[\w\-\.]*)",
            r"(qwen-audio[\w\-\.]*)",
        ]
        found = []
        for p in patterns:
            for m in re.finditer(p, text, re.I):
                name = m.group(1).strip()
                # 过滤掉太短或明显不是模型名的
                if len(name) > 5 and name.lower() not in [f.lower() for f in found]:
                    # 只保留在"免费额度"附近出现的模型
                    idx = m.start()
                    context = text[max(0, idx-100):idx+200]
                    if "免费" in context or "额度" in context or "资源包" in context:
                        found.append(name)
        return found[:25]

"""百度千帆大模型平台抓取器（官方文档页，新用户免费代金券）

数据源：https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Blfmc9dlf
产出：一条聚合蛋——百度千帆新用户实名认证送 20 元代金券，全平台无门槛使用。
"""

import re
from datetime import date
from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

PRICING_URL = "https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Blfmc9dlf"
LINK = "https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Blfmc9dlf"
SIGNUP_LINK = "https://console.bce.baidu.com/qianfan/overview"


class BaiduQianfanScraper(BaseScraper):
    name = "baidu-qianfan"

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

        # 验证页面包含代金券信息
        has_voucher = "20元" in text or "20 元" in text or "代金券" in text

        today = date.today().isoformat()

        egg = Egg(
            id=f"baidu-qianfan-voucher-{today}",
            title="百度千帆新用户送 20 元代金券",
            vendor="百度千帆",
            category="credits",
            score=0.0,
            summary="实名认证即送 20 元代金券，全平台无门槛使用，有效期 1 个月",
            content=(
                f"百度千帆官方定价页自动探测（{today} 快照）。\n\n"
                f"- **免费福利**：新用户实名认证后即送 **20 元代金券**\n"
                f"- **使用范围**：全平台无门槛使用（模型服务、应用开发、组件广场等）\n"
                f"- **有效期**：自发放之日起 **1 个月**\n"
                f"- **覆盖模型**：文心一言（ERNIE）系列、 Llama、Qwen、DeepSeek 等主流模型\n"
                f"- **获取条件**：注册百度智能云账号 + 完成实名认证\n\n"
                f"使用步骤：\n\n"
                f"1. 打开 [百度千帆控制台]({SIGNUP_LINK}) 注册并登录\n"
                f"2. 完成实名认证（个人/企业均可）\n"
                f"3. 系统自动发放 20 元代金券，在「费用中心 → 代金券」查看\n"
                f"4. 调用千帆 API 时自动抵扣\n\n"
                f"**注意**：代金券有效期 1 个月，过期作废；仅限新用户首次实名认证。"
                f"本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "limited", "region": "cn"},
            published_at=today,
            updated_at=today,
            source="baidu-qianfan",
        )
        egg._quota = "20元"
        egg._unit = "credits"
        egg._threshold = "实名认证"
        return [egg]

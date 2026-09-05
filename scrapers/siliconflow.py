"""硅基流动定价页抓取器（官方公开页面，SSR 内嵌模型 JSON）

数据源：https://siliconflow.cn/pricing
产出：一条聚合蛋——页面中标注免费（DisplayName 含 Free / 模型级 price=0）的模型清单。
"""

import re
from datetime import date
from typing import List

from core.models import Egg
from scrapers.base import BaseScraper

PRICING_URL = "https://siliconflow.cn/pricing"
LINK = "https://siliconflow.cn/pricing"

# Next.js RSC payload 中模型对象是转义 JSON，形如：
#   {"modelId":"17885302573","modelName":"Qwen/Qwen2.5-7B-Instruct",...,"price":"0",...,"DisplayName":"Qwen2.5-7B-Instruct (Free)",...}
# 页面源码中反斜杠以字面 \" 出现，因此正则用 \\" 匹配一个反斜杠 + 引号。
_MODEL_BLOCK = re.compile(
    r'"modelName\\":\\"([^\\]+?)\\"(.{0,1800}?)"DisplayName\\":\\"([^\\]+?)\\"',
    re.S,
)


class SiliconFlowScraper(BaseScraper):
    name = "siliconflow"

    def scrape(self) -> List[Egg]:
        resp = self._get(
            PRICING_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            },
        )
        resp.raise_for_status()
        html = resp.text

        free_models = self._extract_free_models(html)
        if not free_models:
            return []

        today = date.today().isoformat()
        names = "、".join(free_models[:10])
        if len(free_models) > 10:
            names += f" 等 {len(free_models)} 款"

        egg = Egg(
            id=f"siliconflow-free-{today}",
            title=f"硅基流动免费模型（{len(free_models)} 款）",
            vendor="硅基流动",
            category="api-quota",
            score=0.0,
            summary=f"官方定价页实时探测：{len(free_models)} 款模型标注免费",
            content=(
                f"硅基流动 SiliconCloud 定价页自动探测（{today} 快照），页面标注免费（价格 ¥0）的模型：\n\n"
                f"- 免费模型：**{len(free_models)} 款**，含 {names}\n"
                f"- 计费：平台按量付费，免费档模型不扣费，注册即可调用\n\n"
                f"使用步骤：\n\n1. 打开 [硅基流动官网](https://siliconflow.cn/)注册并登录\n2. 在控制台创建 API Key\n3. 调用时选择标注「免费」的模型即可\n\n"
                f"**注意**：免费档以官方[定价页]({LINK})实时标注为准；本条目由自动抓取生成，未人工实测。"
            ),
            link=LINK,
            tags={"duration": "longterm", "region": "cn"},
            published_at=today,
            updated_at=today,
            source="siliconflow",
        )
        egg._quota = None
        egg._unit = "api-quota"
        egg._threshold = "注册即用"
        return [egg]

    @staticmethod
    def _extract_free_models(html: str, limit: int = 80) -> List[str]:
        """从 Next.js SSR 转义数据中提取免费模型名（DisplayName 含 (Free) 或模型级 price=0）。"""
        found: List[str] = []
        for m in _MODEL_BLOCK.finditer(html):
            name, window, display = m.group(1), m.group(2), m.group(3)
            is_free = "(Free)" in display or "(free)" in display
            price_m = re.search(r'"price\\":\\"([0-9.]+)\\"', window)
            if not is_free and price_m:
                is_free = price_m.group(1) in ("0", "0.00", "0.0")
            if is_free and name not in found:
                found.append(name)
            if len(found) >= limit:
                break
        return found


def _debug_local(path: str) -> None:
    """离线调试：对本地保存的定价页 HTML 运行解析，验证免费模型提取。"""
    html = open(path, encoding="utf-8", errors="ignore").read()
    models = SiliconFlowScraper._extract_free_models(html)
    print(f"共 {len(models)} 款免费模型:")
    for m in models:
        print(" -", m)


if __name__ == "__main__":
    import sys

    _debug_local(sys.argv[1])

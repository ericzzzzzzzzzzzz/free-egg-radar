"""LLM 解析模块：用硅基流动的免费模型把"公告/线报文本"转成结构化"蛋"。

默认关闭（config.yaml 中 llm.enabled=false）。
不配置 API Key 时系统照常运行——自动抓取源用代码直接解析，不依赖 LLM。
"""

import json
import os
import re
from datetime import date
from typing import Optional

import requests

from core.models import Egg

DEFAULT_BASE = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"  # 硅基流动标注免费的模型

SCHEMA_HINT = (
    "请从下面的活动/公告文本中抽取信息，只输出 JSON，不要输出其他文字。字段：\n"
    '{"title": 活动名称, "vendor": 厂商, "category": "token|credits|api-quota", '
    '"quota_value": 额度数字或 null, "quota_unit": "token|credits|calls", '
    '"duration": "longterm|limited", "expiry_date": "YYYY-MM-DD或null", '
    '"threshold": 领取条件一句话, "summary": 一句话摘要, '
    '"link": 官方链接或null, "steps": [领取步骤]}'
)


class LLMParser:
    def __init__(self, api_key: Optional[str] = None, base_url: str = DEFAULT_BASE, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY", "")
        self.base_url = base_url
        self.model = model
        self.enabled = bool(self.api_key)

    def parse_text(self, text: str, source: str = "llm") -> Optional[Egg]:
        if not self.enabled:
            return None
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SCHEMA_HINT},
                {"role": "user", "content": text[:6000]},
            ],
            "temperature": 0.1,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        link = parsed.get("link") or ""
        if link and not re.match(r"^https?://", link):
            link = ""

        today = date.today().isoformat()
        egg = Egg(
            id=self._make_id(parsed.get("vendor", ""), today),
            title=parsed.get("title") or "未命名福利",
            vendor=parsed.get("vendor") or "未知厂商",
            category=parsed.get("category") or "other",
            score=0.0,
            summary=parsed.get("summary") or "",
            content=text[:400],
            link=link,
            tags={"duration": parsed.get("duration") or "limited", "region": "cn"},
            expiry_date=parsed.get("expiry_date") or None,
            published_at=today,
            updated_at=today,
            source=source,
        )
        egg._quota = parsed.get("quota_value")
        egg._unit = parsed.get("quota_unit") or "token"
        egg._threshold = parsed.get("threshold") or "注册即用"
        return egg

    @staticmethod
    def _make_id(vendor: str, day: str) -> str:
        slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", vendor.lower()).strip("-")[:24] or "vendor"
        return f"{slug}-{day}"

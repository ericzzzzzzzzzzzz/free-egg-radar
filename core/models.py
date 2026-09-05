"""数据模型：一条"蛋"（福利情报条目）"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Egg:
    id: str
    title: str
    vendor: str
    category: str  # token / credits / api-quota / other
    score: float
    summary: str
    content: str = ""
    link: str = ""
    tags: dict = field(default_factory=lambda: {"duration": "longterm", "region": "cn"})
    expired: bool = False
    expiry_date: Optional[str] = None  # ISO 8601
    published_at: str = ""
    updated_at: str = ""
    source: str = "auto"  # openrouter / siliconflow / llm / seed / manual

    def to_dict(self):
        return asdict(self)


def tier_of(score: float) -> str:
    """金蛋 >80 / 银蛋 60-80 / 铜蛋 <60"""
    if score > 80:
        return "gold"
    if score >= 60:
        return "silver"
    return "copper"

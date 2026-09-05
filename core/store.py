"""合并去重 + 过期判定 + 排序"""

import json
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path

from core.models import Egg
from core.scorer import compute_score


def is_expired(egg: Egg, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if egg.expired:
        return True
    if egg.expiry_date:
        try:
            dt = datetime.fromisoformat(egg.expiry_date)
            if dt <= now:
                return True
        except ValueError:
            pass
    return False


def load_seeds(path: Path) -> List[Egg]:
    """读取初始种子库（第一天就有内容）。"""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    eggs = []
    for item in raw.get("eggs", []):
        item.setdefault("tags", {"duration": "longterm", "region": "cn"})
        item.setdefault("score", 60.0)
        item.setdefault("source", "seed")
        eggs.append(Egg(**item))
    return eggs


def merge_and_score(
    seeds: List[Egg],
    scraped: List[Egg],
    weights: dict,
    now: Optional[datetime] = None,
) -> List[Egg]:
    """合并：自动抓取的条目覆盖/新增；种子条目保留人工分数。
    自动条目（source 不是 seed）用公式打分。
    """
    by_id: dict = {}
    for egg in seeds:
        by_id[egg.id] = egg
    for egg in scraped:
        # 自动条目标注"未实测"
        if "实测" not in egg.content:
            egg.content = (egg.content + "\n\n**实测状态**：自动抓取，未人工实测，请以官方页面为准。").strip()
        if egg.source != "seed":
            egg.score = compute_score(
                quota=getattr(egg, "_quota", None),
                unit=getattr(egg, "_unit", "token"),
                duration=egg.tags.get("duration", "longterm"),
                threshold=getattr(egg, "_threshold", "注册即用"),
                expiry_date=egg.expiry_date,
                source=egg.source,
                weights=weights,
            )
        by_id[egg.id] = egg
    result = list(by_id.values())
    # 过期标记
    for egg in result:
        egg.expired = is_expired(egg, now)
    # 排序：未过期在前，按 score 降序；过期按截止时间倒序
    active = sorted([e for e in result if not e.expired], key=lambda e: -e.score)
    expired = sorted([e for e in result if e.expired], key=lambda e: e.expiry_date or "", reverse=True)
    return active + expired

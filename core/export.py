"""生成站点数据文件：site/data/eggs.json + meta.json"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from core.models import Egg, tier_of


def export_site_data(eggs: List[Egg], site_data_dir: Path) -> dict:
    site_data_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes")

    active = [e for e in eggs if not e.expired]
    expired = [e for e in eggs if e.expired]

    stats = {"gold": 0, "silver": 0, "copper": 0, "total": len(active), "expired": len(expired)}
    for e in active:
        stats[tier_of(e.score)] += 1

    payload = {
        "version": now,
        "stats": stats,
        "eggs": [e.to_dict() for e in active],
        "expired": [e.to_dict() for e in expired],
    }
    with open(site_data_dir / "eggs.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    meta = {
        "version": now,
        "stats": stats,
        "updated_at": now,
    }
    with open(site_data_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return stats

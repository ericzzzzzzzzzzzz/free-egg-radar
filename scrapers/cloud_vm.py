"""云主机抓取器：免费试用/赠送活动 + 价格对比

数据策略：
- 种子数据为基础（data/cloud_seed.json，覆盖 15 家云厂商，带来源链接）
- 每日尝试轻量抓取可用公开源（大厂官网多为 JS 渲染，抓不到自动回退种子）
- 每个云主机套餐计算综合评分（免费力度/价格/配置/门槛/续费）
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_PATH = os.path.join(BASE_DIR, "data", "cloud_seed.json")

# 尝试自动抓取的公开源（低频探测，失败自动回退种子）
TRY_URLS = [
    ("腾讯云轻量价格文档", "https://cloud.tencent.com/document/product/1207/73452"),
    ("华为云国际免费套餐", "https://www.huaweicloud.com/intl/en-us/activity/free_packages/"),
]

HEADERS = {
    "User-Agent": "FreeEggRadar/1.0 (cloud price aggregator; low-frequency public info collector)",
    "Accept": "text/html,application/json,*/*;q=0.8",
}

# ---------- 评分 ----------

def score_free(category: str, trial_days: int) -> float:
    """免费力度分：永久免费最高，无免费最低"""
    if category in ("free_forever", "free_tier") or (trial_days and trial_days >= 360):
        return 100
    if trial_days and trial_days >= 90:
        return 70
    if trial_days and trial_days >= 30:
        return 55
    return 20


def score_price(price_year) -> float:
    """价格分：年付价格越低越高"""
    if price_year is None:
        return 40  # 无明确价格
    p = float(price_year)
    if p <= 0:
        return 100
    if p <= 40:
        return 90
    if p <= 60:
        return 85
    if p <= 80:
        return 75
    if p <= 100:
        return 65
    if p <= 160:
        return 50
    if p <= 300:
        return 30
    return 15


def score_config(config: str) -> float:
    """配置分：根据 CPU/内存估算"""
    if not config or "待补充" in config:
        return 40
    cpu = 0
    mem = 0
    m = re.search(r"(\d+)\s*核", config)
    if m:
        cpu = int(m.group(1))
    m = re.search(r"(\d+)\s*G", config)
    if m:
        mem = int(m.group(1))
    # 免费/低配 1核1G~2核2G 得分适中，越高配分越高
    val = cpu * 10 + mem * 3
    return min(100, 30 + val)


def score_threshold(verify: str) -> float:
    """门槛分：要求越低越高"""
    if not verify:
        return 100
    if "无需" in verify or "实名" == verify:
        return 80
    if "实名" in verify:
        return 80
    if "绑卡" in verify:
        return 65
    if "企业" in verify:
        return 50
    return 70


def score_renewal(renewal: str) -> float:
    """续费政策分：续费同价最高"""
    if not renewal:
        return 40
    if "续费同价" in renewal:
        return 100
    if "新老同享" in renewal or "新老同价" in renewal:
        return 85
    if "免费" in renewal and "永久" in renewal:
        return 100
    if "秒杀" in renewal or "仅首年" in renewal or "首年" in renewal:
        return 60
    return 50


def score_cloud_plan(plan: Dict) -> Dict:
    """综合评分：免费30% + 价格30% + 配置15% + 门槛10% + 续费15%"""
    f = score_free(plan.get("category", ""), plan.get("trial_days", 0))
    p = score_price(plan.get("price_year"))
    c = score_config(plan.get("config", ""))
    t = score_threshold(plan.get("verify", ""))
    r = score_renewal(plan.get("renewal", ""))

    total = round(f * 0.30 + p * 0.30 + c * 0.15 + t * 0.10 + r * 0.15, 1)

    plan["score"] = total
    plan["scoreBreakdown"] = {
        "free": f, "price": p, "config": c, "threshold": t, "renewal": r
    }
    return plan


def free_tag(plan: Dict) -> str:
    """免费等级标签：永久免费/免费试用/优惠/待补充"""
    cat = plan.get("category", "")
    if cat in ("free_forever", "free_tier"):
        return "永久免费" if cat == "free_forever" else "免费层"
    if cat == "free_trial":
        days = plan.get("trial_days", 0)
        if days >= 90:
            return f"免费{days//30}个月" if days % 30 == 0 else f"免费{days}天"
        if days >= 30:
            return f"免费{days//30}个月"
        return f"免费{days}天" if days else "免费试用"
    if cat == "deal":
        return "限时优惠"
    return "参考"


def _probe_urls() -> List[str]:
    """轻量探测公开源，返回可用的数据线索（当前大厂多为JS渲染，主要起占位与未来扩展作用）"""
    found = []
    if requests is None:
        return found
    for name, url in TRY_URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code == 200 and len(r.text) > 5000:
                found.append(name)
        except Exception:
            pass
    return found


def scrape_clouds() -> Dict:
    """加载种子数据 + 评分 + 尝试探测可用源"""
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    probe_ok = _probe_urls()

    total_plans = 0
    for cloud in data.get("clouds", []):
        for plan in cloud.get("plans", []):
            score_cloud_plan(plan)
            plan["freeTag"] = free_tag(plan)
            total_plans += 1

    result = {
        "version": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": data.get("source", ""),
        "note": data.get("note", ""),
        "vendorCount": len(data.get("clouds", [])),
        "planCount": total_plans,
        "probeSources": probe_ok,
        "clouds": data.get("clouds", []),
    }
    return result


if __name__ == "__main__":
    result = scrape_clouds()
    print(f"云主机数据：{result['vendorCount']} 家厂商，{result['planCount']} 个套餐")
    print(f"自动探测可用源：{result['probeSources']}")
    for cloud in result["clouds"]:
        for plan in cloud["plans"]:
            price = f"{plan['price_year']}元/年" if plan["price_year"] else "—"
            print(f"  {cloud['vendor']} | {plan['name']} | {plan['config']} | {price} | 评分{plan['score']} | {plan['freeTag']}")

"""云办公电脑抓取器：免费云电脑/云桌面排行

数据策略：
- 种子数据为基础（data/cloudpc_seed.json，覆盖 10 家云电脑厂商，带来源链接）
- 每日尝试轻量探测可用公开源，失败自动回退种子
- 每个云电脑套餐计算综合评分（免费力度/价格/配置/门槛/办公适配）
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_PATH = os.path.join(BASE_DIR, "data", "cloudpc_seed.json")

# ---------- 评分 ----------

def score_free(category: str, trial_days: int, free_hours: float) -> float:
    """免费力度分：永久免费/超长免费最高，无免费最低"""
    if category in ("free_forever", "free_tier") or (trial_days and trial_days >= 365) or (free_hours and free_hours >= 1000):
        return 100
    if (free_hours and free_hours >= 180) or (trial_days and trial_days >= 90):
        return 90
    if (free_hours and free_hours >= 60) or (trial_days and trial_days >= 30):
        return 80
    if (free_hours and free_hours >= 10) or (trial_days and trial_days >= 7):
        return 65
    if free_hours and free_hours > 0:
        return 45
    return 15


def score_price(price_month) -> float:
    """价格分：月付价格越低越高"""
    if price_month is None:
        return 40
    p = float(price_month)
    if p <= 10:
        return 100
    if p <= 30:
        return 85
    if p <= 60:
        return 70
    if p <= 100:
        return 55
    if p <= 200:
        return 40
    return 25


def score_config(config: str) -> float:
    """配置分：根据 CPU/内存/显卡描述估算"""
    if not config:
        return 40
    cpu = 0
    mem = 0
    m = re.search(r"(\d+)\s*核", config)
    if m:
        cpu = int(m.group(1))
    m = re.search(r"(\d+)\s*G", config)
    if m:
        mem = int(m.group(1))
    if "顶配显卡" in config or "5080" in config or "高性能" in config:
        return 90
    val = cpu * 10 + mem * 3
    return min(90, 30 + val)


def score_threshold(verify: str) -> float:
    """门槛分：要求越低越高"""
    if not verify:
        return 100
    if "手机号" in verify:
        return 85
    if "实名" in verify:
        return 70
    if "绑卡" in verify:
        return 60
    if "企业" in verify:
        return 45
    return 75


def score_office(office: str) -> float:
    """办公适配分：多端+浏览器+可装软件最高"""
    if not office:
        return 50
    s = office
    score = 50
    if "多端" in s:
        score += 15
    if "浏览器" in s:
        score += 15
    if "办公软件" in s or "办公" in s or "桌面" in s:
        score += 15
    if "游戏为主" in s or "偏游戏" in s or "游戏为主、轻办公" in s:
        score -= 10
    return max(40, min(100, score))


def score_cloudpc_plan(plan: dict) -> dict:
    """综合评分：免费35% + 价格25% + 配置15% + 门槛10% + 办公15%"""
    f = score_free(plan.get("category", ""), plan.get("trial_days", 0), plan.get("free_hours", 0))
    p = score_price(plan.get("price_month"))
    c = score_config(plan.get("config", ""))
    t = score_threshold(plan.get("verify", ""))
    o = score_office(plan.get("office", ""))

    total = round(f * 0.35 + p * 0.25 + c * 0.15 + t * 0.10 + o * 0.15, 1)

    plan["score"] = total
    plan["scoreBreakdown"] = {
        "free": f, "price": p, "config": c, "threshold": t, "office": o
    }
    return plan


def free_tag(plan: dict) -> str:
    """免费等级标签"""
    cat = plan.get("category", "")
    hours = plan.get("free_hours", 0)
    days = plan.get("trial_days", 0)
    if cat in ("free_forever", "free_tier"):
        return "永久免费层" if cat == "free_forever" else "免费层"
    if cat == "free_trial":
        # 每天免费少量时长的类型（如极云普惠每天免费1小时）
        if hours and hours < 10 and days >= 300:
            if hours % 1 == 0:
                return f"每天免费{int(hours)}小时"
            return f"每天免费{int(hours*60)}分钟"
        if hours and hours >= 60:
            return f"送{int(hours)}小时"
        if hours and hours >= 10:
            return f"送{int(hours)}小时"
        if hours and hours >= 1:
            # 1-10小时之间，整数显示小时，小数显示分钟
            if hours % 1 == 0:
                return f"送{int(hours)}小时"
            return f"送{int(hours*60)}分钟"
        if hours:
            return f"送{int(hours*60)}分钟"
        if days >= 90:
            return f"免费{days}天"
        return f"免费{days}天" if days else "免费试用"
    if cat == "deal":
        return "限时特惠"
    return "参考"


def scrape_cloudpcs() -> dict:
    """加载种子数据 + 评分"""
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_plans = 0
    for cloud in data.get("clouds", []):
        for plan in cloud.get("plans", []):
            score_cloudpc_plan(plan)
            plan["freeTag"] = free_tag(plan)
            total_plans += 1

    result = {
        "version": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": data.get("source", ""),
        "note": data.get("note", ""),
        "vendorCount": len(data.get("clouds", [])),
        "planCount": total_plans,
        "clouds": data.get("clouds", []),
    }
    return result


if __name__ == "__main__":
    result = scrape_cloudpcs()
    print(f"云电脑：{result['vendorCount']} 家厂商，{result['planCount']} 个套餐")
    plans = []
    for cloud in result["clouds"]:
        for plan in cloud["plans"]:
            plans.append((cloud["vendor"], cloud.get("categoryLabel", ""), plan))
    plans.sort(key=lambda x: -x[2]["score"])
    for vendor, label, p in plans:
        price = f"{p['price_month']}元/月" if p["price_month"] else "—"
        freeh = f"送{p['free_hours']}h" if p.get("free_hours") else ""
        print(f"  {vendor:12s} | {label:8s} | {p['name']:16s} | {p['config']:22s} | {price:10s} | 评分{p['score']:5.1f} | {p['freeTag']} {freeh}")

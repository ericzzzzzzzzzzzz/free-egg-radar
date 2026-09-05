"""自动评分引擎：可解释的"蛋力分"公式，替代人工主观打分。

蛋力分 = 额度量级×w1 + 长期性×w2 + 门槛低×w3 + 时效×w4 + 来源可信×w5
各子项 0-100 分，权重在 config.yaml 的 score_weights 中配置。
"""

from datetime import datetime, timezone
from typing import Optional

# 各子项打分函数，全部输出 0-100


def score_quota(quota: Optional[float], unit: str = "token") -> float:
    """额度量级分。quota 为数字（token/积分/次数），unit 决定量级换算。"""
    if quota is None:
        return 50  # 未标注额度，给中值
    if unit == "token":
        if quota >= 1e8:
            return 100
        if quota >= 1e7:
            return 85
        if quota >= 1e6:
            return 70
        if quota >= 1e5:
            return 55
        return 40
    if unit in ("credits", "calls"):
        if quota >= 5000:
            return 100
        if quota >= 1000:
            return 85
        if quota >= 200:
            return 70
        if quota >= 50:
            return 55
        return 40
    return 50


def score_duration(duration: str, expiry_date: Optional[str] = None) -> float:
    """长期性分：长期=100；限时按剩余天数。"""
    if duration == "longterm":
        return 100
    # 限时：按截止日期剩余天数
    if expiry_date:
        try:
            dt = datetime.fromisoformat(expiry_date)
            days = (dt - datetime.now(timezone.utc)).total_seconds() / 86400
            if days >= 30:
                return 80
            if days >= 7:
                return 60
            if days >= 2:
                return 40
            return 25
        except ValueError:
            return 60
    return 60


def score_threshold(threshold: str) -> float:
    """门槛分：越低越好。"""
    t = threshold
    if "注册" in t or "登录" in t or "零门槛" in t or "免费" in t:
        return 100
    if "实名" in t or "认证" in t:
        return 70
    if "企业" in t or "订阅" in t or "付费" in t or "充值" in t:
        return 30
    if "学生" in t or "教育" in t:
        return 45
    if "邀请" in t:
        return 55
    return 60


def score_urgency(expiry_date: Optional[str]) -> float:
    """时效紧迫分：越临近截止越高（对限时活动有提示价值）。"""
    if not expiry_date:
        return 50
    try:
        dt = datetime.fromisoformat(expiry_date)
        days = (dt - datetime.now(timezone.utc)).total_seconds() / 86400
        if days < 0:
            return 0
        if days <= 2:
            return 100
        if days <= 7:
            return 75
        if days <= 30:
            return 50
        return 30
    except ValueError:
        return 50


def score_source(source: str) -> float:
    """来源可信分。"""
    trust = {
        "openrouter": 100,   # 官方公开 API
        "siliconflow": 100,  # 官方定价页
        "official": 100,
        "llm": 75,           # LLM 从公告解析，需人工复核
        "seed": 70,          # 初始迁移数据
        "manual": 60,        # 用户线报
    }
    return trust.get(source, 60)


def compute_score(
    quota: Optional[float],
    unit: str,
    duration: str,
    threshold: str,
    expiry_date: Optional[str],
    source: str,
    weights: dict,
) -> float:
    """加权合成蛋力分。"""
    s = (
        score_quota(quota, unit) * weights.get("quota", 0.4)
        + score_duration(duration, expiry_date) * weights.get("duration", 0.2)
        + score_threshold(threshold) * weights.get("threshold", 0.15)
        + score_urgency(expiry_date) * weights.get("urgency", 0.15)
        + score_source(source) * weights.get("source", 0.1)
    )
    return round(s, 1)

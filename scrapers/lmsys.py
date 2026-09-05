"""LMSYS Chatbot Arena 抓取器（公开 ELO 分数，最有公信力的盲测榜单）

数据源（按优先级）：
1. 第三方归档 API：https://api.wulong.dev/arena-ai-leaderboards/v1/leaderboard?name=text
   （免费、无需 key、自动更新 LMSYS 数据）
2. HuggingFace 原始数据：https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard/raw/main/data/leaderboard.json
   （GitHub Actions 海外可访问）
3. LMSYS 官方 API：https://leaderboard.lmsys.org/v1/get_arena_leaderboard

产出：以模型名为 key 的 ELO 分数字典。

LMSYS Chatbot Arena 是最有公信力的 LLM 盲测榜单，通过用户两两对比投票计算 ELO 分数。
"""

import re
import time
from typing import Dict, Optional

from scrapers.base import BaseScraper

# 数据源列表（按优先级）
DATA_SOURCES = [
    {
        "name": "third_party_api",
        "url": "https://api.wulong.dev/arena-ai-leaderboards/v1/leaderboard?name=text",
        "timeout": 15,
    },
    {
        "name": "huggingface",
        "url": "https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard/raw/main/data/leaderboard.json",
        "timeout": 30,
    },
    {
        "name": "official_api",
        "url": "https://leaderboard.lmsys.org/v1/get_arena_leaderboard",
        "timeout": 15,
    },
]


class LMSYSScraper(BaseScraper):
    name = "lmsys"

    def scrape(self) -> Dict[str, Dict]:
        """抓取 LMSYS 榜单，返回以模型名为 key 的字典，包含 elo、rank、votes 等。"""
        for source in DATA_SOURCES:
            try:
                print(f"[LMSYS] 尝试数据源: {source['name']}")
                resp = self._get(source["url"], timeout=source["timeout"])

                # 429 限流，等待后重试一次
                if resp.status_code == 429:
                    print(f"[LMSYS] 数据源 {source['name']} 被限流(429)，等待 5 秒后重试...")
                    time.sleep(5)
                    resp = self._get(source["url"], timeout=source["timeout"])

                resp.raise_for_status()
                data = resp.json()

                models = self._parse_data(data)
                if models:
                    print(f"[LMSYS] 数据源 {source['name']} 成功，获取到 {len(models)} 个模型")
                    return models
                else:
                    print(f"[LMSYS] 数据源 {source['name']} 返回空数据，尝试下一个")
            except Exception as e:
                print(f"[LMSYS] 数据源 {source['name']} 失败: {e}")
                continue

        print("[LMSYS] 所有数据源均失败，将使用种子数据兜底")
        return {}

    def _parse_data(self, data) -> Dict[str, Dict]:
        """解析不同格式的 LMSYS 数据。"""
        models = {}

        # 格式 1: 第三方 API 返回的格式
        if isinstance(data, dict) and "leaderboard" in data:
            model_list = data["leaderboard"]
        elif isinstance(data, dict) and "data" in data:
            model_list = data["data"]
        elif isinstance(data, dict) and "models" in data:
            model_list = data["models"]
        elif isinstance(data, list):
            model_list = data
        else:
            model_list = []

        for m in model_list:
            if not isinstance(m, dict):
                continue

            name = (
                m.get("Model")
                or m.get("model")
                or m.get("name")
                or m.get("model_name")
                or ""
            )
            if not name:
                continue

            # 提取 ELO 分数（字段名可能不同）
            elo = (
                m.get("Arena Elo")
                or m.get("elo")
                or m.get("Elo")
                or m.get("score")
                or m.get("rating")
                or m.get("elo_rating")
            )

            # 有些数据中 elo 是字符串，需要提取数字
            if isinstance(elo, str):
                num_match = re.search(r"[\d.]+", elo)
                if num_match:
                    try:
                        elo = float(num_match.group())
                    except ValueError:
                        elo = None
                else:
                    elo = None

            rank = m.get("Rank") or m.get("rank")
            votes = m.get("Votes") or m.get("votes") or m.get("num_votes")
            organization = (
                m.get("Organization")
                or m.get("organization")
                or m.get("vendor")
                or m.get("company")
                or ""
            )

            # 归一化模型名
            normalized_name = self._normalize_name(name)

            models[normalized_name] = {
                "name": name,
                "elo": elo,
                "rank": rank,
                "votes": votes,
                "organization": organization,
            }

        return models

    @staticmethod
    def _normalize_name(name: str) -> str:
        """归一化模型名，用于匹配。"""
        n = name.lower().strip()
        n = re.sub(r"[\s\-_]+", "-", n)
        n = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", n)
        return n

    def find_model(self, name: str, models: Dict[str, Dict]) -> Optional[Dict]:
        """在 LMSYS 数据中模糊匹配模型名。"""
        if not models:
            return None

        normalized = self._normalize_name(name)

        # 精确匹配
        if normalized in models:
            return models[normalized]

        # 模糊匹配
        keywords = [k for k in normalized.split("-") if len(k) > 2]
        if not keywords:
            return None

        best_match = None
        best_score = 0

        for lmsys_name, lmsys_data in models.items():
            score = 0
            for kw in keywords:
                if kw in lmsys_name:
                    score += 1
            if score > 0 and abs(len(lmsys_name) - len(normalized)) < 10:
                score += 0.5
            if score > best_score:
                best_score = score
                best_match = lmsys_data

        if best_score >= 2:
            return best_match

        return None

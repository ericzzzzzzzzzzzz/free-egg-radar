"""LMSYS Chatbot Arena 抓取器（公开 ELO 分数，最有公信力的盲测榜单）

数据源：https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard/raw/main/data/leaderboard.json
产出：以模型名为 key 的 ELO 分数字典。

LMSYS Chatbot Arena 是最有公信力的 LLM 盲测榜单，通过用户两两对比投票计算 ELO 分数。
数据公开透明，无需 API key，GitHub Actions（海外）可直接访问 HuggingFace。
"""

import re
from typing import Dict, Optional

from scrapers.base import BaseScraper

LMSYS_DATA_URL = "https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard/raw/main/data/leaderboard.json"


class LMSYSScraper(BaseScraper):
    name = "lmsys"

    def scrape(self) -> Dict[str, Dict]:
        """抓取 LMSYS 榜单，返回以模型名为 key 的字典，包含 elo、rank、votes 等。"""
        try:
            resp = self._get(LMSYS_DATA_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[LMSYS] 获取失败: {e}")
            return {}

        models = {}

        # LMSYS 数据格式可能是 dict 或 list
        if isinstance(data, dict):
            # 尝试常见的 key
            model_list = (
                data.get("data")
                or data.get("models")
                or data.get("leaderboard")
                or []
            )
        elif isinstance(data, list):
            model_list = data
        else:
            model_list = []

        for m in model_list:
            if not isinstance(m, dict):
                continue

            name = m.get("Model") or m.get("model") or m.get("name") or ""
            if not name:
                continue

            # 提取 ELO 分数（字段名可能不同）
            elo = (
                m.get("Arena Elo")
                or m.get("elo")
                or m.get("Elo")
                or m.get("score")
                or m.get("rating")
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
            organization = m.get("Organization") or m.get("organization") or m.get("vendor") or ""

            # 归一化模型名（小写、去空格、去特殊字符）
            normalized_name = self._normalize_name(name)

            models[normalized_name] = {
                "name": name,
                "elo": elo,
                "rank": rank,
                "votes": votes,
                "organization": organization,
                "raw": m,
            }

        print(f"[LMSYS] 获取到 {len(models)} 个模型的 ELO 分数")
        return models

    @staticmethod
    def _normalize_name(name: str) -> str:
        """归一化模型名，用于匹配。"""
        n = name.lower().strip()
        # 替换特殊字符
        n = re.sub(r"[\s\-_]+", "-", n)
        # 去掉版本号中的点（如 gpt-4o-2024-05-13 -> gpt-4o）
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

        # 模糊匹配：检查 LMSYS 模型名是否包含关键词
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
            # 偏好长度相近的模型名
            if score > 0 and abs(len(lmsys_name) - len(normalized)) < 10:
                score += 0.5
            if score > best_score:
                best_score = score
                best_match = lmsys_data

        # 至少匹配 2 个关键词才算成功
        if best_score >= 2:
            return best_match

        return None

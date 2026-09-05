"""模型榜抓取器：多来源公开数据综合评分自动更新

数据源（按公信力排序）：
1. LMSYS Chatbot Arena - 盲测 ELO 分数（最有公信力，HuggingFace/第三方 API）
2. LiveBench - 无污染实时基准（Global Average，每月更新问题）
3. OpenRouter API - 最新价格（公开 API，无需 key）
4. 种子数据 - 多家公开榜单综合分（兜底）

综合评分公式（动态权重，缺失来源自动重新分配）：
- LMSYS ELO 归一化（0-100）× 40%
- LiveBench Global Average（0-100）× 30%
- 价格合理性分（0-100）× 15%
- 种子性能分（0-100）× 15%

产出：site/data/models.json（按综合分降序排列的模型榜单）
"""

import json
import os
import pickle
import io
import requests
from datetime import date
from typing import List, Dict, Any, Optional

from scrapers.base import BaseScraper
from scrapers.livebench import LiveBenchScraper

OPENROUTER_API = "https://openrouter.ai/api/v1/models"
LMSYS_API_URL = "https://huggingface.co/api/spaces/lmarena-ai/chatbot-arena-leaderboard/tree/main"
LMSYS_DOWNLOAD_URL = "https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard/resolve/main/"
SEED_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "models_seed.json")


class ModelRankingScraper(BaseScraper):
    name = "model-ranking"

    def scrape(self) -> List[Dict[str, Any]]:
        """抓取多来源数据并返回综合评分后的模型榜单。"""
        # 1. 加载种子数据（性能分数兜底）
        seed_models = self._load_seed_models()
        print(f"[模型榜] 种子数据: {len(seed_models)} 个模型")

        # 2. 从 LMSYS 获取 ELO 分数（最有公信力，直接使用正确 URL）
        lmsys_data = self._fetch_lmsys_data()

        # 3. 从 LiveBench 获取 Global Average（无污染基准）
        livebench_data = {}
        try:
            lb_scraper = LiveBenchScraper()
            livebench_data = lb_scraper.scrape()
        except Exception as e:
            print(f"[模型榜] LiveBench 获取失败（将使用其他来源兜底）: {e}")

        # 4. 从 OpenRouter 获取最新价格
        openrouter_models = self._fetch_openrouter_models()

        # 5. 合并多来源数据，计算综合分
        models = self._merge_and_score(
            seed_models, lmsys_data, livebench_data, openrouter_models
        )

        # 6. 按综合分降序排列
        models.sort(key=lambda m: m.get("score", 0), reverse=True)

        return models

    def _load_seed_models(self) -> List[Dict[str, Any]]:
        """加载种子模型数据（包含性能分数）。"""
        try:
            with open(SEED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("models", [])
        except Exception as e:
            print(f"[模型榜] 加载种子数据失败: {e}")
            return []

    def _fetch_lmsys_data(self) -> Dict[str, Dict[str, Any]]:
        """从 LMSYS Chatbot Arena 获取 ELO 分数（参考 arena-catalog 项目的正确方式）。"""
        try:
            # 1. 通过 HuggingFace API 获取空间中的文件列表
            print(f"[模型榜] 获取 LMSYS 文件列表: {LMSYS_API_URL}")
            resp = requests.get(LMSYS_API_URL, timeout=30)
            print(f"[模型榜] LMSYS API 响应状态: {resp.status_code}")
            resp.raise_for_status()

            file_data = resp.json()
            pkl_files = [f["path"] for f in file_data if f.get("type") == "file" and ".pkl" in f.get("path", "")]
            print(f"[模型榜] 找到 pkl 文件: {pkl_files}")

            if not pkl_files:
                print("[模型榜] 未找到 pkl 文件")
                return {}

            # 2. 下载最新的 pkl 文件（使用 resolve/main/）
            latest_file = pkl_files[-1]
            download_url = LMSYS_DOWNLOAD_URL + latest_file
            print(f"[模型榜] 下载 LMSYS 数据: {download_url}")
            resp = requests.get(download_url, timeout=60, allow_redirects=True)
            print(f"[模型榜] 下载响应状态: {resp.status_code}, 最终 URL: {resp.url}")
            resp.raise_for_status()
            print(f"[模型榜] LMSYS 数据下载成功，大小: {len(resp.content)} 字节")

            # 3. 解析 pkl 文件（使用自定义 Unpickler 避免 plotly 版本兼容问题）
            print(f"[模型榜] 开始解析 pkl 文件...")
            import pickle

            class SafeUnpickler(pickle.Unpickler):
                """自定义 Unpickler，将 plotly 等未知对象替换为字典。"""
                def find_class(self, module, name):
                    # 跳过 plotly 对象，替换为简单字典
                    if 'plotly' in module:
                        return dict
                    try:
                        return super().find_class(module, name)
                    except Exception:
                        return dict

            battle_info = SafeUnpickler(io.BytesIO(resp.content)).load()
            print(f"[模型榜] LMSYS pkl 解析成功，类型: {type(battle_info)}")

            # 4. 提取 text 类别的模型 ELO 分数
            import pandas as pd
            lmsys_data = {}
            if isinstance(battle_info, dict) and "text" in battle_info:
                text_data = battle_info["text"]
                for category, category_data in text_data.items():
                    if "style_control" in category:
                        continue  # 跳过 style_control 类别
                    if "leaderboard_table_df" in category_data:
                        df = category_data["leaderboard_table_df"]
                        if hasattr(df, "iterrows"):
                            for _, row in df.iterrows():
                                model_name = str(row.get("model") or row.get("model_name") or row.index[0]).strip()
                                rating = row.get("rating")
                                if model_name and rating is not None and pd.notna(rating):
                                    elo = float(rating)
                                    if elo > 0:
                                        key = model_name.lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "")
                                        lmsys_data[key] = {
                                            "name": model_name,
                                            "elo": elo,
                                            "source": "lmsys",
                                        }
            elif hasattr(battle_info, "iterrows"):
                # 直接是 DataFrame
                for _, row in battle_info.iterrows():
                    model_name = str(row.get("model") or row.get("model_name") or "").strip()
                    rating = row.get("rating")
                    if model_name and rating is not None and pd.notna(rating):
                        elo = float(rating)
                        if elo > 0:
                            key = model_name.lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "")
                            lmsys_data[key] = {
                                "name": model_name,
                                "elo": elo,
                                "source": "lmsys",
                            }

            print(f"[模型榜] LMSYS ELO 数据: {len(lmsys_data)} 个模型")
            return lmsys_data

        except Exception as e:
            print(f"[模型榜] LMSYS 获取失败（将使用其他来源兜底）: {e}")
            import traceback
            traceback.print_exc()
            return {}

    @staticmethod
    def _fuzzy_match_model(name: str, data_dict: Dict[str, Dict]) -> Optional[Dict]:
        """简单模糊匹配模型名（去掉空格/点号/横线，关键词匹配）。"""
        if not name or not data_dict:
            return None

        # 标准化模型名
        def normalize(s):
            return s.lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "")

        name_norm = normalize(name)

        # 1. 精确匹配
        if name_norm in data_dict:
            return data_dict[name_norm]

        # 2. 关键词匹配（至少匹配 2 个关键词）
        name_keywords = set(name_norm.split())
        if not name_keywords:
            name_keywords = {name_norm}

        best_match = None
        best_score = 0

        for key, value in data_dict.items():
            data_name = value.get("name", key)
            data_norm = normalize(data_name)
            data_keywords = set(data_norm.split())
            if not data_keywords:
                data_keywords = {data_norm}

            # 计算匹配分数
            common = name_keywords & data_keywords
            score = len(common)

            # 额外加分：一个名称包含另一个
            if name_norm in data_norm or data_norm in name_norm:
                score += 2

            if score > best_score and score >= 2:
                best_score = score
                best_match = value

        return best_match

    def _fetch_openrouter_models(self) -> Dict[str, Dict[str, Any]]:
        """从 OpenRouter API 获取模型列表和价格，返回以模型名为 key 的字典。"""
        try:
            resp = self._get(OPENROUTER_API)
            resp.raise_for_status()
            data = resp.json().get("data", [])

            models = {}
            for m in data:
                name = m.get("name", "")
                pricing = m.get("pricing") or {}
                prompt = pricing.get("prompt")
                completion = pricing.get("completion")
                ctx = m.get("context_length")

                input_cost = self._parse_price(prompt)
                output_cost = self._parse_price(completion)

                models[name.lower()] = {
                    "name": name,
                    "inputCost": input_cost,
                    "outputCost": output_cost,
                    "contextLength": ctx,
                    "id": m.get("id", ""),
                }
            return models
        except Exception as e:
            print(f"[模型榜] OpenRouter API 获取失败: {e}")
            return {}

    @staticmethod
    def _parse_price(price_str) -> Optional[float]:
        """将 OpenRouter 价格字符串转换为美元/百万 Token。"""
        if price_str is None:
            return None
        try:
            return round(float(price_str) * 1_000_000, 4)
        except (ValueError, TypeError):
            return None

    def _merge_and_score(
        self,
        seed_models: List[Dict],
        lmsys_data: Dict[str, Dict],
        livebench_data: Dict[str, Dict],
        openrouter_models: Dict[str, Dict],
    ) -> List[Dict]:
        """合并多来源数据，计算综合分（动态权重）。"""
        today = date.today().isoformat()
        lb_scraper = LiveBenchScraper()

        # 计算 LMSYS ELO 的归一化范围
        elo_values = [v.get("elo") for v in lmsys_data.values() if v.get("elo")]
        elo_min = min(elo_values) if elo_values else 1000
        elo_max = max(elo_values) if elo_values else 1300

        merged = []
        sources_used = set()

        for m in seed_models:
            name = m.get("name", "")
            model = dict(m)  # 复制种子数据

            # 1. 匹配 LMSYS ELO 分数（简单模糊匹配）
            lmsys_match = self._fuzzy_match_model(name, lmsys_data)
            if lmsys_match and lmsys_match.get("elo"):
                model["lmsysElo"] = lmsys_match["elo"]
                sources_used.add("lmsys")
            else:
                model["lmsysElo"] = None

            # 2. 匹配 LiveBench Global Average
            lb_match = lb_scraper.find_model(name, livebench_data)
            if lb_match and lb_match.get("global_average"):
                model["livebenchScore"] = lb_match["global_average"]
                model["livebenchReasoning"] = lb_match.get("reasoning")
                model["livebenchCoding"] = lb_match.get("coding")
                sources_used.add("livebench")
            else:
                model["livebenchScore"] = None

            # 3. 匹配 OpenRouter 最新价格
            or_model = self._find_openrouter_match(name, openrouter_models)
            if or_model:
                model["inputCost"] = or_model.get("inputCost", model.get("inputCost"))
                model["outputCost"] = or_model.get("outputCost", model.get("outputCost"))
                if or_model.get("contextLength"):
                    model["contextLength"] = or_model["contextLength"]
                model["priceUpdatedAt"] = today
                model["priceSource"] = "openrouter"
                sources_used.add("openrouter")
            else:
                model["priceSource"] = model.get("priceSource", "seed")

            # 4. 计算各来源归一化分数
            seed_score = m.get("score", 50)
            lmsys_score = self._normalize_elo(model.get("lmsysElo"), elo_min, elo_max)
            lb_score = model.get("livebenchScore")  # LiveBench 已经是 0-100 范围
            price_score = self._score_price(model.get("inputCost"), model.get("outputCost"))

            # 5. 动态权重综合评分
            # 基础权重：LMSYS 40% + LiveBench 30% + 价格 15% + 种子 15%
            # 缺失的来源权重自动重新分配给可用来源
            weights = {"lmsys": 0.40, "livebench": 0.30, "price": 0.15, "seed": 0.15}
            available = {}
            if lmsys_score is not None:
                available["lmsys"] = lmsys_score
            if lb_score is not None:
                available["livebench"] = lb_score
            available["price"] = price_score
            available["seed"] = seed_score

            # 重新计算权重
            total_weight = sum(weights[k] for k in available.keys())
            final_score = 0
            for k, v in available.items():
                final_score += v * (weights[k] / total_weight)
            final_score = round(final_score, 1)

            model["score"] = final_score
            model["scoreBreakdown"] = {
                "lmsys": lmsys_score,
                "livebench": lb_score,
                "price": price_score,
                "seed": seed_score,
            }
            model["scoreSource"] = "+".join(sorted(available.keys()))
            model["updatedAt"] = today

            merged.append(model)

        print(f"[模型榜] 数据来源: {', '.join(sorted(sources_used)) or 'seed only'}")
        return merged

    @staticmethod
    def _normalize_elo(elo: Optional[float], elo_min: float, elo_max: float) -> Optional[float]:
        """将 LMSYS ELO 分数归一化到 0-100。"""
        if elo is None or elo_max <= elo_min:
            return None
        normalized = ((elo - elo_min) / (elo_max - elo_min)) * 100
        return round(max(0, min(100, normalized)), 1)

    @staticmethod
    def _score_price(input_cost: Optional[float], output_cost: Optional[float]) -> float:
        """根据价格计算合理性分数（越便宜分越高，0-100）。"""
        if input_cost is None and output_cost is None:
            return 50

        ic = input_cost if input_cost is not None else 0
        oc = output_cost if output_cost is not None else 0
        blended = (ic * 3 + oc) / 4

        if blended <= 0.1:
            return 95
        if blended <= 0.5:
            return 85
        if blended <= 1:
            return 75
        if blended <= 3:
            return 65
        if blended <= 5:
            return 55
        if blended <= 10:
            return 45
        if blended <= 20:
            return 35
        return 25

    @staticmethod
    def _find_openrouter_match(name: str, openrouter_models: Dict[str, Dict]) -> Optional[Dict]:
        """在 OpenRouter 模型中模糊匹配种子模型名。"""
        if not openrouter_models:
            return None

        name_lower = name.lower().replace(" ", "-").replace(".", "-")

        if name_lower in openrouter_models:
            return openrouter_models[name_lower]

        keywords = [k for k in name_lower.replace("-", " ").split() if len(k) > 2]
        if not keywords:
            return None

        for or_name, or_model in openrouter_models.items():
            if all(k in or_name for k in keywords):
                return or_model

        return None

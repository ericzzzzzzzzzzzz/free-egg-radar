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
LIVEBENCH_SEED_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "livebench_seed.json")


class ModelRankingScraper(BaseScraper):
    name = "model-ranking"

    def scrape(self) -> List[Dict[str, Any]]:
        """抓取多来源数据并返回综合评分后的模型榜单。"""
        # 1. 加载 LiveBench 种子数据（最新的无污染基准，优先使用）
        livebench_seed = self._load_livebench_seed()
        print(f"[模型榜] LiveBench 种子数据: {len(livebench_seed)} 个模型")

        # 2. 加载旧种子数据（性能分数兜底）
        seed_models = self._load_seed_models()
        print(f"[模型榜] 旧种子数据: {len(seed_models)} 个模型")

        # 3. 从 LMSYS 获取 ELO 分数（盲测数据，可能过时）
        lmsys_data = self._fetch_lmsys_data()

        # 4. 从 LiveBench 网站获取最新数据（如果能获取到的话）
        livebench_data = {}
        try:
            lb_scraper = LiveBenchScraper()
            livebench_data = lb_scraper.scrape()
        except Exception as e:
            print(f"[模型榜] LiveBench 网站获取失败（将使用种子数据）: {e}")

        # 5. 从 OpenRouter 获取最新价格
        openrouter_models = self._fetch_openrouter_models()

        # 6. 合并多来源数据，计算综合分
        # 优先使用 LiveBench 种子数据中的模型，旧种子数据作为补充
        primary_models = livebench_seed if livebench_seed else seed_models
        models = self._merge_and_score(
            primary_models, lmsys_data, livebench_data, openrouter_models
        )

        # 7. 按综合分降序排列
        models.sort(key=lambda m: m.get("score", 0), reverse=True)

        return models

    def _load_livebench_seed(self) -> List[Dict[str, Any]]:
        """加载 LiveBench 种子数据（最新的无污染基准）。"""
        try:
            with open(LIVEBENCH_SEED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            models = data.get("models", [])
            # 转换为统一格式
            result = []
            for m in models:
                name = m.get("name", "")
                # 去掉 Effort 后缀，统一模型名
                clean_name = name
                for suffix in [" Max Effort", " xHigh Effort", " High Effort", " High", " Thinking"]:
                    if clean_name.endswith(suffix):
                        clean_name = clean_name[:-len(suffix)]
                        break
                
                model = {
                    "name": clean_name,
                    "original_name": name,
                    "vendor": self._extract_vendor(clean_name),
                    "releaseDate": data.get("version", "2026-06-25"),
                    "score": m.get("overall", 0),
                    "livebenchScore": m.get("overall"),
                    "livebenchReasoning": m.get("reasoning"),
                    "livebenchCoding": m.get("coding"),
                    "livebenchMath": m.get("mathematics"),
                    "livebenchDataAnalysis": m.get("data_analysis"),
                    "livebenchLanguage": m.get("language"),
                    "livebenchInstructionFollowing": m.get("instruction_following"),
                    "cost": m.get("cost"),
                    "inputCost": None,
                    "outputCost": None,
                    "contextLength": None,
                    "lmsysElo": None,
                }
                result.append(model)
            return result
        except Exception as e:
            print(f"[模型榜] 加载 LiveBench 种子数据失败: {e}")
            return []

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
                            for idx, row in df.iterrows():
                                # 模型名在索引中
                                model_name = str(idx).strip() if idx is not None else ""
                                if not model_name or model_name == "nan":
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
                        # 只处理第一个非 style_control 类别（通常是 full/overall）
                        break
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
        """模糊匹配模型名（精确匹配优先，然后子字符串匹配，最后关键词匹配）。"""
        if not name or not data_dict:
            return None

        # 标准化模型名
        def normalize(s):
            return s.lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "")

        name_norm = normalize(name)

        # 1. 精确匹配
        if name_norm in data_dict:
            return data_dict[name_norm]

        # 2. 子字符串匹配（一个名称包含另一个，且长度差异不大）
        for key, value in data_dict.items():
            data_name = value.get("name", key)
            data_norm = normalize(data_name)
            if name_norm in data_norm or data_norm in name_norm:
                len_ratio = min(len(name_norm), len(data_norm)) / max(len(name_norm), len(data_norm))
                if len_ratio > 0.7:
                    return value

        # 3. 关键词匹配（保留版本号，至少匹配 2 个关键词）
        def extract_keywords(s):
            # 保留版本号（如 3.5、5.3），但去掉单独的数字
            import re
            # 先提取版本号（如 3.5）
            versions = re.findall(r'\d+\.\d+', s)
            # 去掉所有数字和点
            s = re.sub(r'[\d.]+', ' ', s)
            words = [w for w in s.split() if len(w) > 1]
            # 加上版本号作为关键词
            words.extend(versions)
            return set(words) if words else {s}

        name_keywords = extract_keywords(name_norm)

        best_match = None
        best_score = 0

        for key, value in data_dict.items():
            data_name = value.get("name", key)
            data_norm = normalize(data_name)
            data_keywords = extract_keywords(data_norm)

            # 计算匹配分数
            common = name_keywords & data_keywords
            score = len(common)

            # 版本号匹配额外加分
            name_versions = {v for v in name_keywords if '.' in v}
            data_versions = {v for v in data_keywords if '.' in v}
            if name_versions & data_versions:
                score += 2

            # 长度相似度加分
            len_diff = abs(len(name_norm) - len(data_norm))
            if len_diff < 3:
                score += 1

            if score > best_score and score >= 3:
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
        """合并多来源数据，计算综合分（动态权重）。
        优先使用 LiveBench 种子数据（最新无污染基准），LMSYS 作为补充。
        """
        today = date.today().isoformat()
        lb_scraper = LiveBenchScraper()

        # 计算 LMSYS ELO 的归一化范围
        elo_values = [v.get("elo") for v in lmsys_data.values() if v.get("elo")]
        elo_min = min(elo_values) if elo_values else 1000
        elo_max = max(elo_values) if elo_values else 1300

        merged = []
        sources_used = set()
        used_names = set()

        # 1. 优先使用种子数据中的模型（LiveBench 最新数据，包含 35 个最新模型）
        for m in seed_models:
            name = m.get("name", "")
            if not name or name in used_names:
                continue
            used_names.add(name)

            model = dict(m)  # 复制种子数据（已包含 LiveBench 分数）

            # 如果种子数据已有 LiveBench 分数，标记来源
            if model.get("livebenchScore"):
                sources_used.add("livebench")

            # 尝试匹配 LMSYS ELO 分数（作为补充，可能过时）
            lmsys_match = self._fuzzy_match_model(name, lmsys_data)
            if lmsys_match and lmsys_match.get("elo"):
                model["lmsysElo"] = lmsys_match["elo"]
                sources_used.add("lmsys")
            else:
                model["lmsysElo"] = model.get("lmsysElo")

            # 如果种子数据没有 LiveBench 分数，尝试从 LiveBench 网站获取
            if not model.get("livebenchScore"):
                lb_match = lb_scraper.find_model(name, livebench_data)
                if lb_match and lb_match.get("global_average"):
                    model["livebenchScore"] = lb_match["global_average"]
                    model["livebenchReasoning"] = lb_match.get("reasoning")
                    model["livebenchCoding"] = lb_match.get("coding")
                    sources_used.add("livebench")

            # 匹配 OpenRouter 最新价格
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
                model["priceSource"] = model.get("priceSource", "unknown")

            # 计算综合分
            seed_score = m.get("score", 50)  # LiveBench overall 分数
            lmsys_score = self._normalize_elo(model.get("lmsysElo"), elo_min, elo_max)
            lb_score = model.get("livebenchScore")  # 已经是 0-100 范围
            price_score = self._score_price(model.get("inputCost"), model.get("outputCost"))

            # 动态权重：LiveBench 最高（最新无污染基准），LMSYS 次之，价格和种子补充
            weights = {"livebench": 0.45, "lmsys": 0.25, "price": 0.15, "seed": 0.15}
            available = {}
            if lb_score is not None:
                available["livebench"] = lb_score
            if lmsys_score is not None:
                available["lmsys"] = lmsys_score
            available["price"] = price_score
            available["seed"] = seed_score

            total_weight = sum(weights[k] for k in available.keys())
            final_score = 0
            for k, v in available.items():
                final_score += v * (weights[k] / total_weight)
            final_score = round(final_score, 1)

            model["score"] = final_score
            model["scoreBreakdown"] = {
                "livebench": lb_score,
                "lmsys": lmsys_score,
                "price": price_score,
                "seed": seed_score,
            }
            model["scoreSource"] = "+".join(sorted(available.keys()))
            model["updatedAt"] = today

            merged.append(model)

        # 2. 如果种子模型不足 30 个，用 LMSYS 数据补充
        if len(merged) < 30:
            lmsys_sorted = sorted(lmsys_data.values(), key=lambda x: x.get("elo", 0), reverse=True)
            for lmsys_model in lmsys_sorted:
                if len(merged) >= 30:
                    break
                name = lmsys_model.get("name", "")
                if not name or name in used_names:
                    continue
                # 跳过与已有模型相似的
                if any(self._names_similar(name, mm["name"]) for mm in merged):
                    continue
                used_names.add(name)

                model = {
                    "name": name,
                    "vendor": self._extract_vendor(name),
                    "releaseDate": today,
                    "contextLength": None,
                    "inputCost": None,
                    "outputCost": None,
                    "lmsysElo": lmsys_model.get("elo"),
                    "livebenchScore": None,
                    "score": 0,
                    "scoreBreakdown": {},
                    "scoreSource": "",
                    "updatedAt": today,
                }
                sources_used.add("lmsys")

                # 匹配 OpenRouter 价格
                or_model = self._find_openrouter_match(name, openrouter_models)
                if or_model:
                    model["inputCost"] = or_model.get("inputCost")
                    model["outputCost"] = or_model.get("outputCost")
                    if or_model.get("contextLength"):
                        model["contextLength"] = or_model["contextLength"]
                    model["priceSource"] = "openrouter"
                    sources_used.add("openrouter")
                else:
                    model["priceSource"] = "unknown"

                # 计算综合分
                lmsys_score = self._normalize_elo(model.get("lmsysElo"), elo_min, elo_max)
                price_score = self._score_price(model.get("inputCost"), model.get("outputCost"))

                weights = {"lmsys": 0.60, "price": 0.40}
                available = {}
                if lmsys_score is not None:
                    available["lmsys"] = lmsys_score
                available["price"] = price_score

                total_weight = sum(weights[k] for k in available.keys())
                final_score = 0
                for k, v in available.items():
                    final_score += v * (weights[k] / total_weight)
                final_score = round(final_score, 1)

                model["score"] = final_score
                model["scoreBreakdown"] = {
                    "lmsys": lmsys_score,
                    "price": price_score,
                }
                model["scoreSource"] = "+".join(sorted(available.keys()))

                merged.append(model)

        # 按综合分降序排列
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)

        print(f"[模型榜] 数据来源: {', '.join(sorted(sources_used)) or 'seed only'}")
        print(f"[模型榜] 最终模型数: {len(merged)} (LiveBench 种子: {min(len(seed_models), len(used_names))})")
        return merged

    @staticmethod
    def _extract_vendor(name: str) -> str:
        """从模型名中提取厂商名。"""
        name_lower = name.lower()
        vendors = {
            "openai": ["gpt", "o1", "o3", "chatgpt"],
            "google": ["gemini", "palm"],
            "anthropic": ["claude"],
            "meta": ["llama", "muse"],
            "mistral": ["mistral", "mixtral"],
            "deepseek": ["deepseek"],
            "qwen": ["qwen", "tongyi"],
            "zhipu": ["glm", "chatglm"],
            "xai": ["grok"],
            "cohere": ["command", "cohere"],
            "baidu": ["ernie", "wenxin"],
            "alibaba": ["qwen", "tongyi"],
            "tencent": ["hunyuan"],
        }
        for vendor, keywords in vendors.items():
            for kw in keywords:
                if kw in name_lower:
                    return vendor.capitalize()
        return "Unknown"

    @staticmethod
    def _names_similar(name1: str, name2: str) -> bool:
        """判断两个模型名是否相似（用于去重）。"""
        def normalize(s):
            return s.lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "")
        n1 = normalize(name1)
        n2 = normalize(name2)
        return n1 in n2 or n2 in n1

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

        def normalize(s):
            # 去掉厂商前缀（如 qwen/、google/）
            if "/" in s:
                s = s.split("/", 1)[1]
            # 去掉日期后缀（如 -2507、-20250701）
            import re
            s = re.sub(r'-\d{4}$', '', s)  # 去掉 -2507
            s = re.sub(r'-\d{8}$', '', s)  # 去掉 -20250701
            return s.lower().replace(" ", "-").replace("_", "-")

        name_norm = normalize(name)

        # 1. 精确匹配（去掉厂商前缀和日期后缀后）
        for or_name, or_model in openrouter_models.items():
            or_norm = normalize(or_name)
            if or_norm == name_norm:
                return or_model

        # 2. 子字符串匹配（一个名称包含另一个）
        for or_name, or_model in openrouter_models.items():
            or_norm = normalize(or_name)
            if name_norm in or_norm or or_norm in name_norm:
                len_ratio = min(len(name_norm), len(or_norm)) / max(len(name_norm), len(or_norm))
                if len_ratio > 0.6:
                    return or_model

        # 3. 关键词匹配（至少匹配 2 个关键词）
        keywords = [k for k in name_norm.replace("-", " ").split() if len(k) > 2]
        if not keywords:
            return None

        best_match = None
        best_score = 0

        for or_name, or_model in openrouter_models.items():
            or_norm = normalize(or_name)
            or_keywords = set(or_norm.replace("-", " ").split())
            common = set(keywords) & or_keywords
            score = len(common)

            if score > best_score and score >= 2:
                best_score = score
                best_match = or_model

        return best_match

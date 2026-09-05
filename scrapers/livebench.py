"""LiveBench 抓取器（无污染实时 LLM 基准测试）

数据源：https://livebench.ai/
产出：以模型名为 key 的字典，包含 global_average、reasoning、coding、math 等分数。

LiveBench 是一个具有挑战性的、数据污染有限的 LLM 基准测试，
每月更新问题以避免模型在测试集上训练。
"""

import re
import json
from typing import Dict, Optional

from scrapers.base import BaseScraper

LIVEBENCH_URL = "https://livebench.ai/"


class LiveBenchScraper(BaseScraper):
    name = "livebench"

    def scrape(self) -> Dict[str, Dict]:
        """抓取 LiveBench 榜单，返回以模型名为 key 的字典。"""
        try:
            resp = self._get(LIVEBENCH_URL, timeout=30)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            print(f"[LiveBench] 获取失败: {e}")
            return {}

        models = {}

        # 尝试从 HTML 中提取 JSON 数据（LiveBench 通常将数据嵌入在 script 标签中）
        # 方法 1: 查找 __NEXT_DATA__ 或类似的 JSON 数据
        json_match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                models = self._parse_next_data(data)
            except Exception as e:
                print(f"[LiveBench] 解析 __NEXT_DATA__ 失败: {e}")

        # 方法 2: 从表格中提取数据
        if not models:
            models = self._parse_table(html)

        # 方法 3: 从 JavaScript 变量中提取
        if not models:
            models = self._parse_js_variables(html)

        if models:
            print(f"[LiveBench] 获取到 {len(models)} 个模型的分数")
        else:
            print("[LiveBench] 未能解析到数据")

        return models

    def _parse_next_data(self, data: dict) -> Dict[str, Dict]:
        """从 Next.js 数据中提取模型分数。"""
        models = {}

        # 递归查找包含模型数据的列表
        def find_model_list(obj, depth=0):
            if depth > 10:
                return None
            if isinstance(obj, list) and len(obj) > 0:
                # 检查是否是模型列表（第一个元素是否有 model 或 name 字段）
                first = obj[0]
                if isinstance(first, dict):
                    if any(k in first for k in ["model", "name", "Model", "model_name"]):
                        return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    result = find_model_list(v, depth + 1)
                    if result:
                        return result
            return None

        model_list = find_model_list(data)
        if not model_list:
            return {}

        for m in model_list:
            if not isinstance(m, dict):
                continue

            name = (
                m.get("model")
                or m.get("name")
                or m.get("Model")
                or m.get("model_name")
                or ""
            )
            if not name:
                continue

            global_avg = (
                m.get("global_average")
                or m.get("Global Average")
                or m.get("average")
                or m.get("score")
            )
            reasoning = m.get("reasoning_average") or m.get("Reasoning Average") or m.get("reasoning")
            coding = m.get("coding_average") or m.get("Coding Average") or m.get("coding")
            math = m.get("mathematics_average") or m.get("Mathematics Average") or m.get("math")
            organization = m.get("organization") or m.get("Organization") or m.get("vendor") or ""

            normalized_name = self._normalize_name(name)
            models[normalized_name] = {
                "name": name,
                "global_average": global_avg,
                "reasoning": reasoning,
                "coding": coding,
                "math": math,
                "organization": organization,
            }

        return models

    def _parse_table(self, html: str) -> Dict[str, Dict]:
        """从 HTML 表格中提取模型分数。"""
        models = {}

        # 查找表格行
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
        for row in rows:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
            if len(cells) < 3:
                continue

            # 清理 HTML 标签
            clean_cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]

            # 第一列通常是排名，第二列是模型名
            name = clean_cells[1] if len(clean_cells) > 1 else ""
            if not name or name.lower() in ["model", "模型"]:
                continue

            # 尝试提取分数
            global_avg = None
            for cell in clean_cells[2:]:
                try:
                    val = float(cell)
                    if 0 < val < 100:
                        global_avg = val
                        break
                except ValueError:
                    continue

            if global_avg:
                normalized_name = self._normalize_name(name)
                models[normalized_name] = {
                    "name": name,
                    "global_average": global_avg,
                }

        return models

    def _parse_js_variables(self, html: str) -> Dict[str, Dict]:
        """从 JavaScript 变量中提取模型数据。"""
        models = {}

        # 查找包含模型数据的 JS 数组
        # 常见模式: const data = [{model: "...", score: ...}, ...]
        js_arrays = re.findall(
            r'(?:const|let|var)\s+\w+\s*=\s*(\[[^\]]+\{[^\}]+\}[^\]]+\])',
            html,
            re.DOTALL,
        )

        for arr_str in js_arrays[:5]:  # 只检查前 5 个
            try:
                # 尝试解析为 JSON（可能需要清理）
                cleaned = re.sub(r"(\w+):", r'"\1":', arr_str)  # 键加引号
                cleaned = re.sub(r",\s*}", "}", cleaned)  # 去掉 trailing comma
                data = json.loads(cleaned)
                if isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, dict) and any(
                        k in first for k in ["model", "name", "score"]
                    ):
                        for m in data:
                            name = m.get("model") or m.get("name") or ""
                            score = m.get("score") or m.get("global_average")
                            if name and score:
                                normalized_name = self._normalize_name(name)
                                models[normalized_name] = {
                                    "name": name,
                                    "global_average": score,
                                }
                        if models:
                            break
            except Exception:
                continue

        return models

    @staticmethod
    def _normalize_name(name: str) -> str:
        """归一化模型名，用于匹配。"""
        n = name.lower().strip()
        n = re.sub(r"[\s\-_]+", "-", n)
        n = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", n)
        return n

    def find_model(self, name: str, models: Dict[str, Dict]) -> Optional[Dict]:
        """在 LiveBench 数据中模糊匹配模型名。"""
        if not models:
            return None

        normalized = self._normalize_name(name)

        if normalized in models:
            return models[normalized]

        keywords = [k for k in normalized.split("-") if len(k) > 2]
        if not keywords:
            return None

        best_match = None
        best_score = 0

        for lb_name, lb_data in models.items():
            score = 0
            for kw in keywords:
                if kw in lb_name:
                    score += 1
            if score > 0 and abs(len(lb_name) - len(normalized)) < 10:
                score += 0.5
            if score > best_score:
                best_score = score
                best_match = lb_data

        if best_score >= 2:
            return best_match

        return None

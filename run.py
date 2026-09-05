"""FreeEgg Radar 主流程：抓取 → 解析 → 评分 → 生成 → （可选）上传

用法：
  python run.py                 # 抓取+生成（不上传，GitHub Actions 默认）
  python run.py --no-fetch      # 只用种子库+本地数据生成（离线演示）
  python run.py --upload        # 生成后上传到七牛云/COS
  python run.py --dry-run       # 只生成到 site/data，便于本地预览
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.models import Egg  # noqa: E402
from core.store import load_seeds, merge_and_score  # noqa: E402
from core.export import export_site_data  # noqa: E402


def load_config() -> dict:
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_fetch(cfg: dict) -> list:
    """执行所有启用的抓取器，返回自动抓到的蛋。"""
    scraped: list = []
    sources = cfg.get("sources", {})
    if sources.get("openrouter", {}).get("enabled", True):
        try:
            from scrapers.openrouter import OpenRouterScraper
            scraped.extend(OpenRouterScraper().scrape())
        except Exception as e:
            print(f"[抓取] OpenRouter 失败: {e}")
    if sources.get("siliconflow", {}).get("enabled", True):
        try:
            from scrapers.siliconflow import SiliconFlowScraper
            scraped.extend(SiliconFlowScraper().scrape())
        except Exception as e:
            print(f"[抓取] 硅基流动失败: {e}")
    return scraped


def main():
    parser = argparse.ArgumentParser(description="FreeEgg Radar")
    parser.add_argument("--no-fetch", action="store_true", help="不执行网络抓取，仅本地数据")
    parser.add_argument("--upload", action="store_true", help="生成后上传到对象存储")
    parser.add_argument("--dry-run", action="store_true", help="本地生成预览，不打印多余输出")
    args = parser.parse_args()

    cfg = load_config()

    seeds = load_seeds(ROOT / "data" / "seeds.json")
    print(f"[种子库] {len(seeds)} 条初始数据")

    scraped = [] if args.no_fetch else run_fetch(cfg)
    print(f"[自动抓取] {len(scraped)} 条新数据")

    eggs = merge_and_score(seeds, scraped, cfg.get("score_weights", {}))
    stats = export_site_data(eggs, ROOT / "site" / "data")

    print(f"[生成] 有效 {stats['total']} 条（金{stats['gold']} 银{stats['silver']} 铜{stats['copper']}）· 过期 {stats['expired']} 条")

    if args.upload:
        provider = cfg.get("upload", {}).get("provider", "none")
        prefix = cfg.get("upload", {}).get("prefix", "")
        if provider == "qiniu":
            from uploaders.qiniu import upload_site
            upload_site(ROOT / "site", prefix)
        elif provider == "cos":
            from uploaders.cos import upload_site
            upload_site(ROOT / "site", prefix)
        else:
            print("[上传] provider=none，跳过")

    if not args.dry_run:
        print("[完成] 站点数据已更新：site/data/eggs.json")


if __name__ == "__main__":
    main()

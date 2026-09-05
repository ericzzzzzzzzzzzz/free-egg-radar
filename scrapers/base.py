"""抓取器基类：统一接口，带频率控制与合规约束"""

import time
import requests
from typing import List

from core.models import Egg

DEFAULT_HEADERS = {
    "User-Agent": "FreeEggRadar/1.0 (+https://freeegg.top style aggregator; low-frequency public info collector)",
    "Accept": "text/html,application/json,*/*;q=0.8",
}


class BaseScraper:
    name = "base"
    interval_seconds = 2  # 两次请求最小间隔，遵守低频率原则

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _get(self, url: str, timeout: int = 25, **kwargs) -> requests.Response:
        time.sleep(self.interval_seconds)  # 频率控制：不冲击目标站点
        return self.session.get(url, timeout=timeout, **kwargs)

    def scrape(self) -> List[Egg]:
        raise NotImplementedError

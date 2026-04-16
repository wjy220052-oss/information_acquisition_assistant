"""Source adapters package"""

from .v2ex import V2EXAdapter
from .sspai import SspaiAdapter
from .rsshub_zhihu import RSSHubZhihuAdapter
from .rsshub_douban import RSSHubDoubanAdapter
from .ruanyf_weekly import RuanyfWeeklyAdapter
from .solidot import SolidotAdapter

__all__ = [
    "V2EXAdapter",
    "SspaiAdapter",
    "RSSHubZhihuAdapter",
    "RSSHubDoubanAdapter",
    "RuanyfWeeklyAdapter",
    "SolidotAdapter",
]

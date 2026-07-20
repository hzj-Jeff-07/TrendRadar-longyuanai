# coding=utf-8
"""
高级数据分析工具

提供热度趋势分析、平台对比、关键词共现、情感分析等高级分析功能。
原单文件 analytics.py 按主题拆分为 mixin 模块，本包对外接口不变：

    from mcp_server.tools.analytics import AnalyticsTools, calculate_news_weight
"""

from ...services.data_service import DataService
from .weights import calculate_news_weight, _get_weight_config
from .reports import ReportsMixin
from .trend import TrendAnalysisMixin
from .platform import PlatformAnalysisMixin
from .content import ContentAnalysisMixin
from .aggregate import AggregationMixin

__all__ = ["AnalyticsTools", "calculate_news_weight"]


class AnalyticsTools(
    ReportsMixin,
    TrendAnalysisMixin,
    PlatformAnalysisMixin,
    ContentAnalysisMixin,
    AggregationMixin,
):
    """高级数据分析工具类"""

    def __init__(self, project_root: str = None):
        """
        初始化分析工具

        Args:
            project_root: 项目根目录
        """
        self.data_service = DataService(project_root)

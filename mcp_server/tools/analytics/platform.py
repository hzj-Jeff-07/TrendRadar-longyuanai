# coding=utf-8
"""平台对比工具（AnalyticsTools 的 PlatformAnalysisMixin）"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union


from ...utils.validators import (
    validate_keyword,
    validate_date_range
)
from ...utils.errors import MCPError, DataNotFoundError


class PlatformAnalysisMixin:
    """平台对比方法集合，依赖宿主类提供 self.data_service"""

    def compare_platforms(
        self,
        topic: Optional[str] = None,
        date_range: Optional[Union[Dict[str, str], str]] = None
    ) -> Dict:
        """
        平台对比分析 - 对比不同平台对同一话题的关注度

        Args:
            topic: 话题关键词（可选，不指定则对比整体活跃度）
            date_range: 日期范围，格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

        Returns:
            平台对比分析结果

        Examples:
            用户询问示例：
            - "对比一下各个平台对'人工智能'话题的关注度"
            - "看看知乎和微博哪个平台更关注科技新闻"
            - "分析各平台今天的热点分布"

            代码调用示例：
            >>> # 对比各平台（假设今天是 2025-11-17）
            >>> result = tools.compare_platforms(
            ...     topic="人工智能",
            ...     date_range={"start": "2025-11-08", "end": "2025-11-17"}
            ... )
            >>> print(result['platform_stats'])
        """
        try:
            # 参数验证
            if topic:
                topic = validate_keyword(topic)
            date_range_tuple = validate_date_range(date_range)

            # 确定日期范围
            if date_range_tuple:
                start_date, end_date = date_range_tuple
            else:
                start_date = end_date = datetime.now()

            # 收集各平台数据
            platform_stats = defaultdict(lambda: {
                "total_news": 0,
                "topic_mentions": 0,
                "unique_titles": set(),
                "top_keywords": Counter()
            })

            # 遍历日期范围
            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        for title in titles.keys():
                            platform_stats[platform_name]["total_news"] += 1
                            platform_stats[platform_name]["unique_titles"].add(title)

                            # 如果指定了话题，统计包含话题的新闻
                            if topic and topic.lower() in title.lower():
                                platform_stats[platform_name]["topic_mentions"] += 1

                            # 提取关键词（简单分词）
                            keywords = self._extract_keywords(title)
                            platform_stats[platform_name]["top_keywords"].update(keywords)

                except DataNotFoundError:
                    pass

                current_date += timedelta(days=1)

            # 转换为可序列化的格式
            result_stats = {}
            for platform, stats in platform_stats.items():
                coverage_rate = 0
                if stats["total_news"] > 0:
                    coverage_rate = (stats["topic_mentions"] / stats["total_news"]) * 100

                result_stats[platform] = {
                    "total_news": stats["total_news"],
                    "topic_mentions": stats["topic_mentions"],
                    "unique_titles": len(stats["unique_titles"]),
                    "coverage_rate": round(coverage_rate, 2),
                    "top_keywords": [
                        {"keyword": k, "count": v}
                        for k, v in stats["top_keywords"].most_common(5)
                    ]
                }

            # 找出各平台独有的热点
            unique_topics = self._find_unique_topics(platform_stats)

            return {
                "success": True,
                "topic": topic,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                },
                "platform_stats": result_stats,
                "unique_topics": unique_topics,
                "total_platforms": len(result_stats)
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def get_platform_activity_stats(
        self,
        date_range: Optional[Union[Dict[str, str], str]] = None
    ) -> Dict:
        """
        平台活跃度统计 - 统计各平台的发布频率和活跃时间段

        Args:
            date_range: 日期范围（可选）

        Returns:
            平台活跃度统计结果

        Examples:
            用户询问示例：
            - "统计各平台今天的活跃度"
            - "看看哪个平台更新最频繁"
            - "分析各平台的发布时间规律"

            代码调用示例：
            >>> # 查看各平台活跃度（假设今天是 2025-11-17）
            >>> result = tools.get_platform_activity_stats(
            ...     date_range={"start": "2025-11-08", "end": "2025-11-17"}
            ... )
            >>> print(result['platform_activity'])
        """
        try:
            # 参数验证
            date_range_tuple = validate_date_range(date_range)

            # 确定日期范围
            if date_range_tuple:
                start_date, end_date = date_range_tuple
            else:
                start_date = end_date = datetime.now()

            # 统计各平台活跃度
            platform_activity = defaultdict(lambda: {
                "total_updates": 0,
                "days_active": set(),
                "news_count": 0,
                "hourly_distribution": Counter()
            })

            # 遍历日期范围
            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, id_to_name, timestamps = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        platform_activity[platform_name]["news_count"] += len(titles)
                        platform_activity[platform_name]["days_active"].add(current_date.strftime("%Y-%m-%d"))

                        # 统计更新次数（基于文件数量）
                        platform_activity[platform_name]["total_updates"] += len(timestamps)

                        # 统计时间分布（基于文件名中的时间）
                        for filename in timestamps.keys():
                            # 解析文件名中的小时（格式：HHMM.txt）
                            match = re.match(r'(\d{2})(\d{2})\.txt', filename)
                            if match:
                                hour = int(match.group(1))
                                platform_activity[platform_name]["hourly_distribution"][hour] += 1

                except DataNotFoundError:
                    pass

                current_date += timedelta(days=1)

            # 转换为可序列化的格式
            result_activity = {}
            for platform, stats in platform_activity.items():
                days_count = len(stats["days_active"])
                avg_news_per_day = stats["news_count"] / days_count if days_count > 0 else 0

                # 找出最活跃的时间段
                most_active_hours = stats["hourly_distribution"].most_common(3)

                result_activity[platform] = {
                    "total_updates": stats["total_updates"],
                    "news_count": stats["news_count"],
                    "days_active": days_count,
                    "avg_news_per_day": round(avg_news_per_day, 2),
                    "most_active_hours": [
                        {"hour": f"{hour:02d}:00", "count": count}
                        for hour, count in most_active_hours
                    ],
                    "activity_score": round(stats["news_count"] / max(days_count, 1), 2)
                }

            # 按活跃度排序
            sorted_platforms = sorted(
                result_activity.items(),
                key=lambda x: x[1]["activity_score"],
                reverse=True
            )

            return {
                "success": True,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                },
                "platform_activity": dict(sorted_platforms),
                "most_active_platform": sorted_platforms[0][0] if sorted_platforms else None,
                "total_platforms": len(result_activity)
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def _find_unique_topics(self, platform_stats: Dict) -> Dict[str, List[str]]:
        """
        找出各平台独有的热点话题

        Args:
            platform_stats: 平台统计数据

        Returns:
            各平台独有话题字典
        """
        unique_topics = {}

        # 获取每个平台的TOP关键词
        platform_keywords = {}
        for platform, stats in platform_stats.items():
            top_keywords = set([kw for kw, _ in stats["top_keywords"].most_common(10)])
            platform_keywords[platform] = top_keywords

        # 找出独有关键词
        for platform, keywords in platform_keywords.items():
            # 找出其他平台的所有关键词
            other_keywords = set()
            for other_platform, other_kws in platform_keywords.items():
                if other_platform != platform:
                    other_keywords.update(other_kws)

            # 找出独有的
            unique = keywords - other_keywords
            if unique:
                unique_topics[platform] = list(unique)[:5]  # 最多5个

        return unique_topics

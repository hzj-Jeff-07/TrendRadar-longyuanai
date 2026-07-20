# coding=utf-8
"""趋势分析工具（AnalyticsTools 的 TrendAnalysisMixin）"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Union


from ...utils.validators import (
    validate_limit,
    validate_keyword,
    validate_threshold
)
from ...utils.errors import MCPError, InvalidParameterError, DataNotFoundError


class TrendAnalysisMixin:
    """趋势分析方法集合，依赖宿主类提供 self.data_service"""

    def analyze_topic_trend_unified(
        self,
        topic: str,
        analysis_type: str = "trend",
        date_range: Optional[Union[Dict[str, str], str]] = None,
        granularity: str = "day",
        threshold: float = 3.0,
        time_window: int = 24,
        lookahead_hours: int = 6,
        confidence_threshold: float = 0.7
    ) -> Dict:
        """
        统一话题趋势分析工具 - 整合多种趋势分析模式

        Args:
            topic: 话题关键词（必需）
            analysis_type: 分析类型，可选值：
                - "trend": 热度趋势分析（追踪话题的热度变化）
                - "lifecycle": 生命周期分析（从出现到消失的完整周期）
                - "viral": 异常热度检测（识别突然爆火的话题）
                - "predict": 话题预测（预测未来可能的热点）
            date_range: 日期范围（trend和lifecycle模式），可选
                       - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       - **默认**: 不指定时默认分析最近7天
            granularity: 时间粒度（trend模式），默认"day"（hour/day）
            threshold: 热度突增倍数阈值（viral模式），默认3.0
            time_window: 检测时间窗口小时数（viral模式），默认24
            lookahead_hours: 预测未来小时数（predict模式），默认6
            confidence_threshold: 置信度阈值（predict模式），默认0.7

        Returns:
            趋势分析结果字典

        Examples (假设今天是 2025-11-17):
            - 用户："分析AI最近7天的趋势" → analyze_topic_trend_unified(topic="人工智能", analysis_type="trend", date_range={"start": "2025-11-11", "end": "2025-11-17"})
            - 用户："看看特斯拉本月的热度" → analyze_topic_trend_unified(topic="特斯拉", analysis_type="lifecycle", date_range={"start": "2025-11-01", "end": "2025-11-17"})
            - analyze_topic_trend_unified(topic="比特币", analysis_type="viral", threshold=3.0)
            - analyze_topic_trend_unified(topic="ChatGPT", analysis_type="predict", lookahead_hours=6)
        """
        try:
            # 参数验证
            topic = validate_keyword(topic)

            if analysis_type not in ["trend", "lifecycle", "viral", "predict"]:
                raise InvalidParameterError(
                    f"无效的分析类型: {analysis_type}",
                    suggestion="支持的类型: trend, lifecycle, viral, predict"
                )

            # 根据分析类型调用相应方法
            if analysis_type == "trend":
                return self.get_topic_trend_analysis(
                    topic=topic,
                    date_range=date_range,
                    granularity=granularity
                )
            elif analysis_type == "lifecycle":
                return self.analyze_topic_lifecycle(
                    topic=topic,
                    date_range=date_range
                )
            elif analysis_type == "viral":
                # viral模式不需要topic参数，使用通用检测
                return self.detect_viral_topics(
                    threshold=threshold,
                    time_window=time_window
                )
            else:  # predict
                # predict模式不需要topic参数，使用通用预测
                return self.predict_trending_topics(
                    lookahead_hours=lookahead_hours,
                    confidence_threshold=confidence_threshold
                )

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

    def get_topic_trend_analysis(
        self,
        topic: str,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        granularity: str = "day"
    ) -> Dict:
        """
        热度趋势分析 - 追踪特定话题的热度变化趋势

        Args:
            topic: 话题关键词
            date_range: 日期范围（可选）
                       - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       - **默认**: 不指定时默认分析最近7天
            granularity: 时间粒度，仅支持 day（天）

        Returns:
            趋势分析结果字典

        Examples:
            用户询问示例：
            - "帮我分析一下'人工智能'这个话题最近一周的热度趋势"
            - "查看'比特币'过去一周的热度变化"
            - "看看'iPhone'最近7天的趋势如何"
            - "分析'特斯拉'最近一个月的热度趋势"
            - "查看'ChatGPT'2024年12月的趋势变化"

            代码调用示例：
            >>> tools = AnalyticsTools()
            >>> # 分析7天趋势（假设今天是 2025-11-17）
            >>> result = tools.get_topic_trend_analysis(
            ...     topic="人工智能",
            ...     date_range={"start": "2025-11-11", "end": "2025-11-17"},
            ...     granularity="day"
            ... )
            >>> # 分析历史月份趋势
            >>> result = tools.get_topic_trend_analysis(
            ...     topic="特斯拉",
            ...     date_range={"start": "2024-12-01", "end": "2024-12-31"},
            ...     granularity="day"
            ... )
            >>> print(result['trend_data'])
        """
        try:
            # 验证参数
            topic = validate_keyword(topic)

            # 验证粒度参数（只支持day）
            if granularity != "day":
                from ..utils.errors import InvalidParameterError
                raise InvalidParameterError(
                    f"不支持的粒度参数: {granularity}",
                    suggestion="当前仅支持 'day' 粒度，因为底层数据按天聚合"
                )

            # 处理日期范围（不指定时默认最近7天）
            if date_range:
                from ..utils.validators import validate_date_range
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                # 默认最近7天
                end_date = datetime.now()
                start_date = end_date - timedelta(days=6)

            # 收集趋势数据
            trend_data = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    # 统计该时间点的话题出现次数
                    count = 0
                    matched_titles = []

                    for _, titles in all_titles.items():
                        for title in titles.keys():
                            if topic.lower() in title.lower():
                                count += 1
                                matched_titles.append(title)

                    trend_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": count,
                        "sample_titles": matched_titles[:3]  # 只保留前3个样本
                    })

                except DataNotFoundError:
                    trend_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": 0,
                        "sample_titles": []
                    })

                # 按天增加时间
                current_date += timedelta(days=1)

            # 计算趋势指标
            counts = [item["count"] for item in trend_data]
            total_days = (end_date - start_date).days + 1

            if len(counts) >= 2:
                # 计算涨跌幅度
                first_non_zero = next((c for c in counts if c > 0), 0)
                last_count = counts[-1]

                if first_non_zero > 0:
                    change_rate = ((last_count - first_non_zero) / first_non_zero) * 100
                else:
                    change_rate = 0

                # 找到峰值时间
                max_count = max(counts)
                peak_index = counts.index(max_count)
                peak_time = trend_data[peak_index]["date"]
            else:
                change_rate = 0
                peak_time = None
                max_count = 0

            return {
                "success": True,
                "summary": {
                    "description": f"话题「{topic}」的热度趋势分析",
                    "topic": topic,
                    "date_range": {
                        "start": start_date.strftime("%Y-%m-%d"),
                        "end": end_date.strftime("%Y-%m-%d"),
                        "total_days": total_days
                    },
                    "granularity": granularity,
                    "total_mentions": sum(counts),
                    "average_mentions": round(sum(counts) / len(counts), 2) if counts else 0,
                    "peak_count": max_count,
                    "peak_time": peak_time,
                    "change_rate": round(change_rate, 2),
                    "trend_direction": "上升" if change_rate > 10 else "下降" if change_rate < -10 else "稳定"
                },
                "data": trend_data
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

    def analyze_topic_lifecycle(
        self,
        topic: str,
        date_range: Optional[Union[Dict[str, str], str]] = None
    ) -> Dict:
        """
        话题生命周期分析 - 追踪话题从出现到消失的完整周期

        Args:
            topic: 话题关键词
            date_range: 日期范围（可选）
                       - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       - **默认**: 不指定时默认分析最近7天

        Returns:
            话题生命周期分析结果

        Examples:
            用户询问示例：
            - "分析'人工智能'这个话题的生命周期"
            - "看看'iPhone'话题是昙花一现还是持续热点"
            - "追踪'比特币'话题的热度变化"

            代码调用示例：
            >>> # 分析话题生命周期（假设今天是 2025-11-17）
            >>> result = tools.analyze_topic_lifecycle(
            ...     topic="人工智能",
            ...     date_range={"start": "2025-10-19", "end": "2025-11-17"}
            ... )
            >>> print(result['lifecycle_stage'])
        """
        try:
            # 参数验证
            topic = validate_keyword(topic)

            # 处理日期范围（不指定时默认最近7天）
            if date_range:
                from ..utils.validators import validate_date_range
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                # 默认最近7天
                end_date = datetime.now()
                start_date = end_date - timedelta(days=6)

            # 收集话题历史数据
            lifecycle_data = []
            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    # 统计该日的话题出现次数
                    count = 0
                    for _, titles in all_titles.items():
                        for title in titles.keys():
                            if topic.lower() in title.lower():
                                count += 1

                    lifecycle_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": count
                    })

                except DataNotFoundError:
                    lifecycle_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": 0
                    })

                current_date += timedelta(days=1)

            # 计算分析天数
            total_days = (end_date - start_date).days + 1

            # 分析生命周期阶段
            counts = [item["count"] for item in lifecycle_data]

            if not any(counts):
                time_desc = f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"
                raise DataNotFoundError(
                    f"在 {time_desc} 内未找到话题 '{topic}'",
                    suggestion="请尝试其他话题或扩大时间范围"
                )

            # 找到首次出现和最后出现
            first_appearance = next((item["date"] for item in lifecycle_data if item["count"] > 0), None)
            last_appearance = next((item["date"] for item in reversed(lifecycle_data) if item["count"] > 0), None)

            # 计算峰值
            max_count = max(counts)
            peak_index = counts.index(max_count)
            peak_date = lifecycle_data[peak_index]["date"]

            # 计算平均值和标准差（简单实现）
            non_zero_counts = [c for c in counts if c > 0]
            avg_count = sum(non_zero_counts) / len(non_zero_counts) if non_zero_counts else 0

            # 判断生命周期阶段
            recent_counts = counts[-3:]  # 最近3天
            early_counts = counts[:3]    # 前3天

            if sum(recent_counts) > sum(early_counts):
                lifecycle_stage = "上升期"
            elif sum(recent_counts) < sum(early_counts) * 0.5:
                lifecycle_stage = "衰退期"
            elif max_count in recent_counts:
                lifecycle_stage = "爆发期"
            else:
                lifecycle_stage = "稳定期"

            # 分类：昙花一现 vs 持续热点
            active_days = sum(1 for c in counts if c > 0)

            if active_days <= 2 and max_count > avg_count * 2:
                topic_type = "昙花一现"
            elif active_days >= total_days * 0.6:
                topic_type = "持续热点"
            else:
                topic_type = "周期性热点"

            return {
                "success": True,
                "topic": topic,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d"),
                    "total_days": total_days
                },
                "lifecycle_data": lifecycle_data,
                "analysis": {
                    "first_appearance": first_appearance,
                    "last_appearance": last_appearance,
                    "peak_date": peak_date,
                    "peak_count": max_count,
                    "active_days": active_days,
                    "avg_daily_mentions": round(avg_count, 2),
                    "lifecycle_stage": lifecycle_stage,
                    "topic_type": topic_type
                }
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

    def detect_viral_topics(
        self,
        threshold: float = 3.0,
        time_window: int = 24
    ) -> Dict:
        """
        异常热度检测 - 自动识别突然爆火的话题

        Args:
            threshold: 热度突增倍数阈值
            time_window: 检测时间窗口（小时）

        Returns:
            爆火话题列表

        Examples:
            用户询问示例：
            - "检测今天有哪些突然爆火的话题"
            - "看看有没有热度异常的新闻"
            - "预警可能的重大事件"

            代码调用示例：
            >>> tools = AnalyticsTools()
            >>> result = tools.detect_viral_topics(
            ...     threshold=3.0,
            ...     time_window=24
            ... )
            >>> print(result['viral_topics'])
        """
        try:
            # 参数验证
            threshold = validate_threshold(threshold, default=3.0, min_value=1.0, max_value=100.0)
            time_window = validate_limit(time_window, default=24, max_limit=72)

            # 读取当前和之前的数据
            current_all_titles, _, _ = self.data_service.parser.read_all_titles_for_date()

            # 读取昨天的数据作为基准
            yesterday = datetime.now() - timedelta(days=1)
            try:
                previous_all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                    date=yesterday
                )
            except DataNotFoundError:
                previous_all_titles = {}

            # 统计当前的关键词频率
            current_keywords = Counter()
            current_keyword_titles = defaultdict(list)

            for _, titles in current_all_titles.items():
                for title in titles.keys():
                    keywords = self._extract_keywords(title)
                    current_keywords.update(keywords)

                    for kw in keywords:
                        current_keyword_titles[kw].append(title)

            # 统计之前的关键词频率
            previous_keywords = Counter()

            for _, titles in previous_all_titles.items():
                for title in titles.keys():
                    keywords = self._extract_keywords(title)
                    previous_keywords.update(keywords)

            # 检测异常热度
            viral_topics = []

            for keyword, current_count in current_keywords.items():
                previous_count = previous_keywords.get(keyword, 0)

                # 计算增长倍数
                if previous_count == 0:
                    # 新出现的话题
                    if current_count >= 5:  # 至少出现5次才认为是爆火
                        growth_rate = float('inf')
                        is_viral = True
                    else:
                        continue
                else:
                    growth_rate = current_count / previous_count
                    is_viral = growth_rate >= threshold

                if is_viral:
                    viral_topics.append({
                        "keyword": keyword,
                        "current_count": current_count,
                        "previous_count": previous_count,
                        "growth_rate": round(growth_rate, 2) if growth_rate != float('inf') else "新话题",
                        "sample_titles": current_keyword_titles[keyword][:3],
                        "alert_level": "高" if growth_rate > threshold * 2 else "中"
                    })

            # 按增长率排序
            viral_topics.sort(
                key=lambda x: x["current_count"] if x["growth_rate"] == "新话题" else x["growth_rate"],
                reverse=True
            )

            if not viral_topics:
                return {
                    "success": True,
                    "summary": {
                        "description": "异常热度检测结果",
                        "total": 0,
                        "threshold": threshold,
                        "time_window": time_window
                    },
                    "data": [],
                    "message": f"未检测到热度增长超过 {threshold} 倍的话题"
                }

            return {
                "success": True,
                "summary": {
                    "description": "异常热度检测结果",
                    "total": len(viral_topics),
                    "threshold": threshold,
                    "time_window": time_window,
                    "detection_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "data": viral_topics
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

    def predict_trending_topics(
        self,
        lookahead_hours: int = 6,
        confidence_threshold: float = 0.7
    ) -> Dict:
        """
        话题预测 - 基于历史数据预测未来可能的热点

        Args:
            lookahead_hours: 预测未来多少小时
            confidence_threshold: 置信度阈值

        Returns:
            预测的潜力话题列表

        Examples:
            用户询问示例：
            - "预测接下来6小时可能的热点话题"
            - "有哪些话题可能会火起来"
            - "早期发现潜力话题"

            代码调用示例：
            >>> tools = AnalyticsTools()
            >>> result = tools.predict_trending_topics(
            ...     lookahead_hours=6,
            ...     confidence_threshold=0.7
            ... )
            >>> print(result['predicted_topics'])
        """
        try:
            # 参数验证
            lookahead_hours = validate_limit(lookahead_hours, default=6, max_limit=48)
            confidence_threshold = validate_threshold(
                confidence_threshold,
                default=0.7,
                min_value=0.0,
                max_value=1.0,
                param_name="confidence_threshold"
            )

            # 收集最近3天的数据用于预测
            keyword_trends = defaultdict(list)

            for days_ago in range(3, 0, -1):
                date = datetime.now() - timedelta(days=days_ago)

                try:
                    all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                        date=date
                    )

                    # 统计关键词
                    keywords_count = Counter()
                    for _, titles in all_titles.items():
                        for title in titles.keys():
                            keywords = self._extract_keywords(title)
                            keywords_count.update(keywords)

                    # 记录每个关键词的历史数据
                    for keyword, count in keywords_count.items():
                        keyword_trends[keyword].append(count)

                except DataNotFoundError:
                    pass

            # 添加今天的数据
            try:
                all_titles, _, _ = self.data_service.parser.read_all_titles_for_date()

                keywords_count = Counter()
                keyword_titles = defaultdict(list)

                for _, titles in all_titles.items():
                    for title in titles.keys():
                        keywords = self._extract_keywords(title)
                        keywords_count.update(keywords)

                        for kw in keywords:
                            keyword_titles[kw].append(title)

                for keyword, count in keywords_count.items():
                    keyword_trends[keyword].append(count)

            except DataNotFoundError:
                raise DataNotFoundError(
                    "未找到今天的数据",
                    suggestion="请等待爬虫任务完成"
                )

            # 预测潜力话题
            predicted_topics = []

            for keyword, trend_data in keyword_trends.items():
                if len(trend_data) < 2:
                    continue

                # 简单的线性趋势预测
                # 计算增长率
                recent_value = trend_data[-1]
                previous_value = trend_data[-2] if len(trend_data) >= 2 else 0

                if previous_value == 0:
                    if recent_value >= 3:
                        growth_rate = 1.0
                    else:
                        continue
                else:
                    growth_rate = (recent_value - previous_value) / previous_value

                # 判断是否是上升趋势
                if growth_rate > 0.3:  # 增长超过30%
                    # 计算置信度（基于趋势的稳定性）
                    if len(trend_data) >= 3:
                        # 检查是否连续增长
                        is_consistent = all(
                            trend_data[i] <= trend_data[i+1]
                            for i in range(len(trend_data)-1)
                        )
                        confidence = 0.9 if is_consistent else 0.7
                    else:
                        confidence = 0.6

                    if confidence >= confidence_threshold:
                        predicted_topics.append({
                            "keyword": keyword,
                            "current_count": recent_value,
                            "growth_rate": round(growth_rate * 100, 2),
                            "confidence": round(confidence, 2),
                            "trend_data": trend_data,
                            "prediction": "上升趋势，可能成为热点",
                            "sample_titles": keyword_titles.get(keyword, [])[:3]
                        })

            # 按置信度和增长率排序
            predicted_topics.sort(
                key=lambda x: (x["confidence"], x["growth_rate"]),
                reverse=True
            )

            return {
                "success": True,
                "summary": {
                    "description": "热点话题预测结果",
                    "total": len(predicted_topics),
                    "returned": min(20, len(predicted_topics)),
                    "lookahead_hours": lookahead_hours,
                    "confidence_threshold": confidence_threshold,
                    "prediction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "data": predicted_topics[:20],  # 返回TOP 20
                "note": "预测基于历史趋势，实际结果可能有偏差"
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

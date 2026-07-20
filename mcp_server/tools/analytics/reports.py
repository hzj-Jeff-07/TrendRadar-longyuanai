# coding=utf-8
"""报告与洞察工具（AnalyticsTools 的 ReportsMixin）"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Union


from ...utils.validators import (
    validate_date_range
)
from ...utils.errors import MCPError, InvalidParameterError, DataNotFoundError


class ReportsMixin:
    """报告与洞察方法集合，依赖宿主类提供 self.data_service"""

    def analyze_data_insights_unified(
        self,
        insight_type: str = "platform_compare",
        topic: Optional[str] = None,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        min_frequency: int = 3,
        top_n: int = 20
    ) -> Dict:
        """
        统一数据洞察分析工具 - 整合多种数据分析模式

        Args:
            insight_type: 洞察类型，可选值：
                - "platform_compare": 平台对比分析（对比不同平台对话题的关注度）
                - "platform_activity": 平台活跃度统计（统计各平台发布频率和活跃时间）
                - "keyword_cooccur": 关键词共现分析（分析关键词同时出现的模式）
            topic: 话题关键词（可选，platform_compare模式适用）
            date_range: 日期范围，格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            min_frequency: 最小共现频次（keyword_cooccur模式），默认3
            top_n: 返回TOP N结果（keyword_cooccur模式），默认20

        Returns:
            数据洞察分析结果字典

        Examples:
            - analyze_data_insights_unified(insight_type="platform_compare", topic="人工智能")
            - analyze_data_insights_unified(insight_type="platform_activity", date_range={...})
            - analyze_data_insights_unified(insight_type="keyword_cooccur", min_frequency=5)
        """
        try:
            # 参数验证
            if insight_type not in ["platform_compare", "platform_activity", "keyword_cooccur"]:
                raise InvalidParameterError(
                    f"无效的洞察类型: {insight_type}",
                    suggestion="支持的类型: platform_compare, platform_activity, keyword_cooccur"
                )

            # 根据洞察类型调用相应方法
            if insight_type == "platform_compare":
                return self.compare_platforms(
                    topic=topic,
                    date_range=date_range
                )
            elif insight_type == "platform_activity":
                return self.get_platform_activity_stats(
                    date_range=date_range
                )
            else:  # keyword_cooccur
                return self.analyze_keyword_cooccurrence(
                    min_frequency=min_frequency,
                    top_n=top_n
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

    def generate_summary_report(
        self,
        report_type: str = "daily",
        date_range: Optional[Union[Dict[str, str], str]] = None
    ) -> Dict:
        """
        每日/每周摘要生成器 - 自动生成热点摘要报告

        Args:
            report_type: 报告类型（daily/weekly）
            date_range: 自定义日期范围（可选）

        Returns:
            Markdown格式的摘要报告

        Examples:
            用户询问示例：
            - "生成今天的新闻摘要报告"
            - "给我一份本周的热点总结"
            - "生成过去7天的新闻分析报告"

            代码调用示例：
            >>> tools = AnalyticsTools()
            >>> result = tools.generate_summary_report(
            ...     report_type="daily"
            ... )
            >>> print(result['markdown_report'])
        """
        try:
            # 参数验证
            if report_type not in ["daily", "weekly"]:
                raise InvalidParameterError(
                    f"无效的报告类型: {report_type}",
                    suggestion="支持的类型: daily, weekly"
                )

            # 确定日期范围
            if date_range:
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                if report_type == "daily":
                    start_date = end_date = datetime.now()
                else:  # weekly
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=6)

            # 收集数据
            all_keywords = Counter()
            all_platforms_news = defaultdict(int)
            all_titles_list = []

            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)
                        all_platforms_news[platform_name] += len(titles)

                        for title in titles.keys():
                            all_titles_list.append({
                                "title": title,
                                "platform": platform_name,
                                "date": current_date.strftime("%Y-%m-%d")
                            })

                            # 提取关键词
                            keywords = self._extract_keywords(title)
                            all_keywords.update(keywords)

                except DataNotFoundError:
                    pass

                current_date += timedelta(days=1)

            # 生成报告
            report_title = f"{'每日' if report_type == 'daily' else '每周'}新闻热点摘要"
            date_str = f"{start_date.strftime('%Y-%m-%d')}" if report_type == "daily" else f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"

            # 构建Markdown报告
            markdown = f"""# {report_title}

**报告日期**: {date_str}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 数据概览

- **总新闻数**: {len(all_titles_list)}
- **覆盖平台**: {len(all_platforms_news)}
- **热门关键词数**: {len(all_keywords)}

## 🔥 TOP 10 热门话题

"""

            # 添加TOP 10关键词
            for i, (keyword, count) in enumerate(all_keywords.most_common(10), 1):
                markdown += f"{i}. **{keyword}** - 出现 {count} 次\n"

            # 平台分析
            markdown += "\n## 📱 平台活跃度\n\n"
            sorted_platforms = sorted(all_platforms_news.items(), key=lambda x: x[1], reverse=True)

            for platform, count in sorted_platforms:
                markdown += f"- **{platform}**: {count} 条新闻\n"

            # 趋势变化（如果是周报）
            if report_type == "weekly":
                markdown += "\n## 📈 趋势分析\n\n"
                markdown += "本周热度持续的话题（样本数据）：\n\n"

                # 简单的趋势分析
                top_keywords = [kw for kw, _ in all_keywords.most_common(5)]
                for keyword in top_keywords:
                    markdown += f"- **{keyword}**: 持续热门\n"

            # 添加样本新闻（按权重选择，确保确定性）
            markdown += "\n## 📰 精选新闻样本\n\n"

            # 确定性选取：按标题的权重排序，取前5条
            # 这样相同输入总是返回相同结果
            if all_titles_list:
                # 计算每条新闻的权重分数（基于关键词出现次数）
                news_with_scores = []
                for news in all_titles_list:
                    # 简单权重：统计包含TOP关键词的次数
                    score = 0
                    title_lower = news['title'].lower()
                    for keyword, count in all_keywords.most_common(10):
                        if keyword.lower() in title_lower:
                            score += count
                    news_with_scores.append((news, score))

                # 按权重降序排序，权重相同则按标题字母顺序（确保确定性）
                news_with_scores.sort(key=lambda x: (-x[1], x[0]['title']))

                # 取前5条
                sample_news = [item[0] for item in news_with_scores[:5]]

                for news in sample_news:
                    markdown += f"- [{news['platform']}] {news['title']}\n"

            markdown += "\n---\n\n*本报告由 TrendRadar MCP 自动生成*\n"

            return {
                "success": True,
                "report_type": report_type,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                },
                "markdown_report": markdown,
                "statistics": {
                    "total_news": len(all_titles_list),
                    "platforms_count": len(all_platforms_news),
                    "keywords_count": len(all_keywords),
                    "top_keyword": all_keywords.most_common(1)[0] if all_keywords else None
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

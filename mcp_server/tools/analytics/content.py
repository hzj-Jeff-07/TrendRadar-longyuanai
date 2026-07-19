# coding=utf-8
"""内容分析工具（AnalyticsTools 的 ContentAnalysisMixin）"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from difflib import SequenceMatcher


from ...utils.validators import (
    validate_platforms,
    validate_limit,
    validate_keyword,
    validate_top_n,
    validate_date_range,
    validate_threshold
)
from ...utils.errors import MCPError, InvalidParameterError, DataNotFoundError
from .weights import calculate_news_weight


class ContentAnalysisMixin:
    """内容分析方法集合，依赖宿主类提供 self.data_service"""

    def analyze_keyword_cooccurrence(
        self,
        min_frequency: int = 3,
        top_n: int = 20
    ) -> Dict:
        """
        关键词共现分析 - 分析哪些关键词经常同时出现

        Args:
            min_frequency: 最小共现频次
            top_n: 返回TOP N关键词对

        Returns:
            关键词共现分析结果

        Examples:
            用户询问示例：
            - "分析一下哪些关键词经常一起出现"
            - "看看'人工智能'经常和哪些词一起出现"
            - "找出今天新闻中的关键词关联"

            代码调用示例：
            >>> tools = AnalyticsTools()
            >>> result = tools.analyze_keyword_cooccurrence(
            ...     min_frequency=5,
            ...     top_n=15
            ... )
            >>> print(result['cooccurrence_pairs'])
        """
        try:
            # 参数验证
            min_frequency = validate_limit(min_frequency, default=3, max_limit=100)
            top_n = validate_top_n(top_n, default=20)

            # 读取今天的数据
            all_titles, _, _ = self.data_service.parser.read_all_titles_for_date()

            # 关键词共现统计
            cooccurrence = Counter()
            keyword_titles = defaultdict(list)

            for platform_id, titles in all_titles.items():
                for title in titles.keys():
                    # 提取关键词
                    keywords = self._extract_keywords(title)

                    # 记录每个关键词出现的标题
                    for kw in keywords:
                        keyword_titles[kw].append(title)

                    # 计算两两共现
                    if len(keywords) >= 2:
                        for i, kw1 in enumerate(keywords):
                            for kw2 in keywords[i+1:]:
                                # 统一排序，避免重复
                                pair = tuple(sorted([kw1, kw2]))
                                cooccurrence[pair] += 1

            # 过滤低频共现
            filtered_pairs = [
                (pair, count) for pair, count in cooccurrence.items()
                if count >= min_frequency
            ]

            # 排序并取TOP N
            top_pairs = sorted(filtered_pairs, key=lambda x: x[1], reverse=True)[:top_n]

            # 构建结果
            result_pairs = []
            for (kw1, kw2), count in top_pairs:
                # 找出同时包含两个关键词的标题样本
                titles_with_both = [
                    title for title in keyword_titles[kw1]
                    if kw2 in self._extract_keywords(title)
                ]

                result_pairs.append({
                    "keyword1": kw1,
                    "keyword2": kw2,
                    "cooccurrence_count": count,
                    "sample_titles": titles_with_both[:3]
                })

            return {
                "success": True,
                "summary": {
                    "description": "关键词共现分析结果",
                    "total": len(result_pairs),
                    "min_frequency": min_frequency,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "data": result_pairs
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

    def analyze_sentiment(
        self,
        topic: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        limit: int = 50,
        sort_by_weight: bool = True,
        include_url: bool = False
    ) -> Dict:
        """
        情感倾向分析 - 生成用于 AI 情感分析的结构化提示词

        本工具收集新闻数据并生成优化的 AI 提示词，你可以将其发送给 AI 进行深度情感分析。

        Args:
            topic: 话题关键词（可选），只分析包含该关键词的新闻
            platforms: 平台过滤列表（可选），如 ['zhihu', 'weibo']
            date_range: 日期范围（可选），格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       不指定则默认查询今天的数据
            limit: 返回新闻数量限制，默认50，最大100
            sort_by_weight: 是否按权重排序，默认True（推荐）
            include_url: 是否包含URL链接，默认False（节省token）

        Returns:
            包含 AI 提示词和新闻数据的结构化结果

        Examples:
            用户询问示例：
            - "分析一下今天新闻的情感倾向"
            - "看看'特斯拉'相关新闻是正面还是负面的"
            - "分析各平台对'人工智能'的情感态度"
            - "看看'特斯拉'相关新闻是正面还是负面的，请选择一周内的前10条新闻来分析"

            代码调用示例：
            >>> tools = AnalyticsTools()
            >>> # 分析今天的特斯拉新闻，返回前10条
            >>> result = tools.analyze_sentiment(
            ...     topic="特斯拉",
            ...     limit=10
            ... )
            >>> # 分析一周内的特斯拉新闻（假设今天是 2025-11-17）
            >>> result = tools.analyze_sentiment(
            ...     topic="特斯拉",
            ...     date_range={"start": "2025-11-11", "end": "2025-11-17"},
            ...     limit=10
            ... )
            >>> print(result['ai_prompt'])  # 获取生成的提示词
        """
        try:
            # 参数验证
            if topic:
                topic = validate_keyword(topic)
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)

            # 处理日期范围
            if date_range:
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                # 默认今天
                start_date = end_date = datetime.now()

            # 收集新闻数据（支持多天）
            all_news_items = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date,
                        platform_ids=platforms
                    )

                    # 收集该日期的新闻
                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)
                        for title, info in titles.items():
                            # 如果指定了话题，只收集包含话题的标题
                            if topic and topic.lower() not in title.lower():
                                continue

                            news_item = {
                                "platform": platform_name,
                                "title": title,
                                "ranks": info.get("ranks", []),
                                "count": len(info.get("ranks", [])),
                                "date": current_date.strftime("%Y-%m-%d")
                            }

                            # 条件性添加 URL 字段
                            if include_url:
                                news_item["url"] = info.get("url", "")
                                news_item["mobileUrl"] = info.get("mobileUrl", "")

                            all_news_items.append(news_item)

                except DataNotFoundError:
                    # 该日期没有数据，继续下一天
                    pass

                # 下一天
                current_date += timedelta(days=1)

            if not all_news_items:
                time_desc = "今天" if start_date == end_date else f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"
                raise DataNotFoundError(
                    f"未找到相关新闻（{time_desc}）",
                    suggestion="请尝试其他话题、日期范围或平台"
                )

            # 去重（同一标题只保留一次）
            unique_news = {}
            for item in all_news_items:
                key = f"{item['platform']}::{item['title']}"
                if key not in unique_news:
                    unique_news[key] = item
                else:
                    # 合并 ranks（如果同一新闻在多天出现）
                    existing = unique_news[key]
                    existing["ranks"].extend(item["ranks"])
                    existing["count"] = len(existing["ranks"])

            deduplicated_news = list(unique_news.values())

            # 按权重排序（如果启用）
            if sort_by_weight:
                deduplicated_news.sort(
                    key=lambda x: calculate_news_weight(x),
                    reverse=True
                )

            # 限制返回数量
            selected_news = deduplicated_news[:limit]

            # 生成 AI 提示词
            ai_prompt = self._create_sentiment_analysis_prompt(
                news_data=selected_news,
                topic=topic
            )

            # 构建时间范围描述
            if start_date == end_date:
                time_range_desc = start_date.strftime("%Y-%m-%d")
            else:
                time_range_desc = f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"

            result = {
                "success": True,
                "method": "ai_prompt_generation",
                "summary": {
                    "description": "情感分析数据和AI提示词",
                    "total_found": len(deduplicated_news),
                    "returned": len(selected_news),
                    "requested_limit": limit,
                    "duplicates_removed": len(all_news_items) - len(deduplicated_news),
                    "topic": topic,
                    "time_range": time_range_desc,
                    "platforms": list(set(item["platform"] for item in selected_news)),
                    "sorted_by_weight": sort_by_weight
                },
                "ai_prompt": ai_prompt,
                "data": selected_news,
                "usage_note": "请将 ai_prompt 字段的内容发送给 AI 进行情感分析"
            }

            # 如果返回数量少于请求数量，增加提示
            if len(selected_news) < limit and len(deduplicated_news) >= limit:
                result["note"] = "返回数量少于请求数量是因为去重逻辑（同一标题在不同平台只保留一次）"
            elif len(deduplicated_news) < limit:
                result["note"] = f"在指定时间范围内仅找到 {len(deduplicated_news)} 条匹配的新闻"

            return result

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

    def _create_sentiment_analysis_prompt(
        self,
        news_data: List[Dict],
        topic: Optional[str]
    ) -> str:
        """
        创建情感分析的 AI 提示词

        Args:
            news_data: 新闻数据列表（已排序和限制数量）
            topic: 话题关键词

        Returns:
            格式化的 AI 提示词
        """
        # 按平台分组
        platform_news = defaultdict(list)
        for item in news_data:
            platform_news[item["platform"]].append({
                "title": item["title"],
                "date": item.get("date", "")
            })

        # 构建提示词
        prompt_parts = []

        # 1. 任务说明
        if topic:
            prompt_parts.append(f"请分析以下关于「{topic}」的新闻标题的情感倾向。")
        else:
            prompt_parts.append("请分析以下新闻标题的情感倾向。")

        prompt_parts.append("")
        prompt_parts.append("分析要求：")
        prompt_parts.append("1. 识别每条新闻的情感倾向（正面/负面/中性）")
        prompt_parts.append("2. 统计各情感类别的数量和百分比")
        prompt_parts.append("3. 分析不同平台的情感差异")
        prompt_parts.append("4. 总结整体情感趋势")
        prompt_parts.append("5. 列举典型的正面和负面新闻样本")
        prompt_parts.append("")

        # 2. 数据概览
        prompt_parts.append("数据概览：")
        prompt_parts.append(f"- 总新闻数：{len(news_data)}")
        prompt_parts.append(f"- 覆盖平台：{len(platform_news)}")

        # 时间范围
        dates = set(item.get("date", "") for item in news_data if item.get("date"))
        if dates:
            date_list = sorted(dates)
            if len(date_list) == 1:
                prompt_parts.append(f"- 时间范围：{date_list[0]}")
            else:
                prompt_parts.append(f"- 时间范围：{date_list[0]} 至 {date_list[-1]}")

        prompt_parts.append("")

        # 3. 按平台展示新闻
        prompt_parts.append("新闻列表（按平台分类，已按重要性排序）：")
        prompt_parts.append("")

        for platform, items in sorted(platform_news.items()):
            prompt_parts.append(f"【{platform}】({len(items)} 条)")
            for i, item in enumerate(items, 1):
                title = item["title"]
                date_str = f" [{item['date']}]" if item.get("date") else ""
                prompt_parts.append(f"{i}. {title}{date_str}")
            prompt_parts.append("")

        # 4. 输出格式说明
        prompt_parts.append("请按以下格式输出分析结果：")
        prompt_parts.append("")
        prompt_parts.append("## 情感分布统计")
        prompt_parts.append("- 正面：XX条 (XX%)")
        prompt_parts.append("- 负面：XX条 (XX%)")
        prompt_parts.append("- 中性：XX条 (XX%)")
        prompt_parts.append("")
        prompt_parts.append("## 平台情感对比")
        prompt_parts.append("[各平台的情感倾向差异]")
        prompt_parts.append("")
        prompt_parts.append("## 整体情感趋势")
        prompt_parts.append("[总体分析和关键发现]")
        prompt_parts.append("")
        prompt_parts.append("## 典型样本")
        prompt_parts.append("正面新闻样本：")
        prompt_parts.append("[列举3-5条]")
        prompt_parts.append("")
        prompt_parts.append("负面新闻样本：")
        prompt_parts.append("[列举3-5条]")

        return "\n".join(prompt_parts)

    def find_similar_news(
        self,
        reference_title: str,
        threshold: float = 0.6,
        limit: int = 50,
        include_url: bool = False
    ) -> Dict:
        """
        相似新闻查找 - 基于标题相似度查找相关新闻

        Args:
            reference_title: 参考标题
            threshold: 相似度阈值（0-1之间）
            limit: 返回条数限制，默认50
            include_url: 是否包含URL链接，默认False（节省token）

        Returns:
            相似新闻列表

        Examples:
            用户询问示例：
            - "找出和'特斯拉降价'相似的新闻"
            - "查找关于iPhone发布的类似报道"
            - "看看有没有和这条新闻相似的报道"

            代码调用示例：
            >>> tools = AnalyticsTools()
            >>> result = tools.find_similar_news(
            ...     reference_title="特斯拉宣布降价",
            ...     threshold=0.6,
            ...     limit=10
            ... )
            >>> print(result['similar_news'])
        """
        try:
            # 参数验证
            reference_title = validate_keyword(reference_title)
            threshold = validate_threshold(threshold, default=0.6, min_value=0.0, max_value=1.0)
            limit = validate_limit(limit, default=50)

            # 读取数据
            all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date()

            # 计算相似度
            similar_items = []

            for platform_id, titles in all_titles.items():
                platform_name = id_to_name.get(platform_id, platform_id)

                for title, info in titles.items():
                    if title == reference_title:
                        continue

                    # 计算相似度
                    similarity = self._calculate_similarity(reference_title, title)

                    if similarity >= threshold:
                        news_item = {
                            "title": title,
                            "platform": platform_id,
                            "platform_name": platform_name,
                            "similarity": round(similarity, 3),
                            "rank": info["ranks"][0] if info["ranks"] else 0
                        }

                        # 条件性添加 URL 字段
                        if include_url:
                            news_item["url"] = info.get("url", "")

                        similar_items.append(news_item)

            # 按相似度排序
            similar_items.sort(key=lambda x: x["similarity"], reverse=True)

            # 限制数量
            result_items = similar_items[:limit]

            if not result_items:
                raise DataNotFoundError(
                    f"未找到相似度超过 {threshold} 的新闻",
                    suggestion="请降低相似度阈值或尝试其他标题"
                )

            result = {
                "success": True,
                "summary": {
                    "description": "相似新闻搜索结果",
                    "total_found": len(similar_items),
                    "returned": len(result_items),
                    "requested_limit": limit,
                    "threshold": threshold,
                    "reference_title": reference_title
                },
                "data": result_items
            }

            if len(similar_items) < limit:
                result["note"] = f"相似度阈值 {threshold} 下仅找到 {len(similar_items)} 条相似新闻"

            return result

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

    def search_by_entity(
        self,
        entity: str,
        entity_type: Optional[str] = None,
        limit: int = 50,
        sort_by_weight: bool = True
    ) -> Dict:
        """
        实体识别搜索 - 搜索包含特定人物/地点/机构的新闻

        Args:
            entity: 实体名称
            entity_type: 实体类型（person/location/organization），可选
            limit: 返回条数限制，默认50，最大200
            sort_by_weight: 是否按权重排序，默认True

        Returns:
            实体相关新闻列表

        Examples:
            用户询问示例：
            - "搜索马斯克相关的新闻"
            - "查找关于特斯拉公司的报道，返回前20条"
            - "看看北京有什么新闻"

            代码调用示例：
            >>> tools = AnalyticsTools()
            >>> result = tools.search_by_entity(
            ...     entity="马斯克",
            ...     entity_type="person",
            ...     limit=20
            ... )
            >>> print(result['related_news'])
        """
        try:
            # 参数验证
            entity = validate_keyword(entity)
            limit = validate_limit(limit, default=50)

            if entity_type and entity_type not in ["person", "location", "organization"]:
                raise InvalidParameterError(
                    f"无效的实体类型: {entity_type}",
                    suggestion="支持的类型: person, location, organization"
                )

            # 读取数据
            all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date()

            # 搜索包含实体的新闻
            related_news = []
            entity_context = Counter()  # 统计实体周边的词

            for platform_id, titles in all_titles.items():
                platform_name = id_to_name.get(platform_id, platform_id)

                for title, info in titles.items():
                    if entity in title:
                        url = info.get("url", "")
                        mobile_url = info.get("mobileUrl", "")
                        ranks = info.get("ranks", [])
                        count = len(ranks)

                        related_news.append({
                            "title": title,
                            "platform": platform_id,
                            "platform_name": platform_name,
                            "url": url,
                            "mobileUrl": mobile_url,
                            "ranks": ranks,
                            "count": count,
                            "rank": ranks[0] if ranks else 999
                        })

                        # 提取实体周边的关键词
                        keywords = self._extract_keywords(title)
                        entity_context.update(keywords)

            if not related_news:
                raise DataNotFoundError(
                    f"未找到包含实体 '{entity}' 的新闻",
                    suggestion="请尝试其他实体名称"
                )

            # 移除实体本身
            if entity in entity_context:
                del entity_context[entity]

            # 按权重排序（如果启用）
            if sort_by_weight:
                related_news.sort(
                    key=lambda x: calculate_news_weight(x),
                    reverse=True
                )
            else:
                # 按排名排序
                related_news.sort(key=lambda x: x["rank"])

            # 限制返回数量
            result_news = related_news[:limit]

            return {
                "success": True,
                "summary": {
                    "description": f"实体「{entity}」相关新闻",
                    "entity": entity,
                    "entity_type": entity_type or "auto",
                    "total_found": len(related_news),
                    "returned": len(result_news),
                    "sorted_by_weight": sort_by_weight
                },
                "data": result_news,
                "related_keywords": [
                    {"keyword": k, "count": v}
                    for k, v in entity_context.most_common(10)
                ]
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

    def _extract_keywords(self, title: str, min_length: int = 2) -> List[str]:
        """
        从标题中提取关键词（简单实现）

        Args:
            title: 标题文本
            min_length: 最小关键词长度

        Returns:
            关键词列表
        """
        # 移除URL和特殊字符
        title = re.sub(r'http[s]?://\S+', '', title)
        title = re.sub(r'[^\w\s]', ' ', title)

        # 简单分词（按空格和常见分隔符）
        words = re.split(r'[\s，。！？、]+', title)

        # 过滤停用词和短词
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}

        keywords = [
            word.strip() for word in words
            if word.strip() and len(word.strip()) >= min_length and word.strip() not in stopwords
        ]

        return keywords

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            相似度分数（0-1之间）
        """
        # 使用 SequenceMatcher 计算相似度
        return SequenceMatcher(None, text1, text2).ratio()

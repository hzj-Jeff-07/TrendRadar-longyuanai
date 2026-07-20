# coding=utf-8
"""trendradar.storage.local 本地 SQLite 存储往返测试

覆盖数据库读写、去重合并、新增检测、抓取次数、过期清理等核心路径。
每个测试使用独立 tmp_path，互不影响。
"""

import pytest

from trendradar.storage.base import NewsData, NewsItem, RSSData, RSSItem
from trendradar.storage.local import LocalStorageBackend

DATE = "2026-01-15"


@pytest.fixture
def backend(tmp_path):
    return LocalStorageBackend(
        data_dir=str(tmp_path / "output"),
        enable_txt=False,
        enable_html=False,
        timezone="Asia/Shanghai",
    )


def make_news_data(date=DATE, crawl_time="08:00", titles=None):
    titles = titles or [("华为发布新品", "weibo", 1)]
    items = {}
    for title, source_id, rank in titles:
        items.setdefault(source_id, []).append(
            NewsItem(
                title=title,
                source_id=source_id,
                rank=rank,
                ranks=[rank],
                url=f"https://example.com/{title}",
                crawl_time=crawl_time,
            )
        )
    return NewsData(
        date=date,
        crawl_time=crawl_time,
        items=items,
        id_to_name={"weibo": "微博", "zhihu": "知乎"},
    )


def make_rss_data(date=DATE, crawl_time="08:00", titles=None):
    titles = titles or [("大模型综述", "tech-blog")]
    items = {}
    for title, feed_id in titles:
        items.setdefault(feed_id, []).append(
            RSSItem(
                title=title,
                feed_id=feed_id,
                url=f"https://blog.example.com/{title}",
                guid=title,
                published_at="2026-01-14T20:00:00+00:00",
                crawl_time=crawl_time,
            )
        )
    return RSSData(date=date, crawl_time=crawl_time, items=items, id_to_name={"tech-blog": "Tech"})


class TestNewsRoundTrip:
    def test_save_and_read_back(self, backend):
        assert backend.save_news_data(make_news_data()) is True
        loaded = backend.get_today_all_data(date=DATE)
        assert loaded is not None
        assert loaded.get_total_count() == 1
        assert "weibo" in loaded.items
        assert loaded.items["weibo"][0].title == "华为发布新品"

    def test_empty_date_returns_none_or_empty(self, backend):
        loaded = backend.get_today_all_data(date="2020-01-01")
        assert loaded is None or loaded.get_total_count() == 0

    def test_multiple_crawls_merge_ranks(self, backend):
        # 同一标题两次抓取，排名历史应合并
        backend.save_news_data(make_news_data(crawl_time="08:00", titles=[("华为发布新品", "weibo", 1)]))
        backend.save_news_data(make_news_data(crawl_time="09:00", titles=[("华为发布新品", "weibo", 3)]))
        loaded = backend.get_today_all_data(date=DATE)
        item = loaded.items["weibo"][0]
        # 两次排名都被记录
        assert 1 in item.ranks and 3 in item.ranks
        assert item.count >= 2


class TestFirstCrawlAndTimes:
    def test_is_first_crawl_today(self, backend):
        # 无记录时为首次
        assert backend.is_first_crawl_today(date=DATE) is True
        # 仅一条抓取记录仍视为首次（语义：count <= 1）
        backend.save_news_data(make_news_data(crawl_time="08:00"))
        assert backend.is_first_crawl_today(date=DATE) is True
        # 第二次抓取后不再是首次
        backend.save_news_data(make_news_data(crawl_time="09:00"))
        assert backend.is_first_crawl_today(date=DATE) is False

    def test_get_crawl_times_accumulates(self, backend):
        backend.save_news_data(make_news_data(crawl_time="08:00"))
        backend.save_news_data(make_news_data(crawl_time="09:00"))
        times = backend.get_crawl_times(date=DATE)
        assert len(times) >= 2


class TestNewTitleDetection:
    def test_detect_new_titles_on_second_crawl(self, backend):
        backend.save_news_data(make_news_data(crawl_time="08:00", titles=[("旧闻", "weibo", 1)]))
        current = make_news_data(
            crawl_time="09:00",
            titles=[("旧闻", "weibo", 1), ("新爆点", "weibo", 2)],
        )
        new_titles = backend.detect_new_titles(current)
        # "新爆点" 应被识别为新增，"旧闻" 不应
        flat = str(new_titles)
        assert "新爆点" in flat
        assert "旧闻" not in flat


class TestRSSRoundTrip:
    def test_save_and_read_back(self, backend):
        assert backend.save_rss_data(make_rss_data()) is True
        loaded = backend.get_rss_data(date=DATE)
        assert loaded is not None
        assert loaded.get_total_count() == 1
        assert loaded.items["tech-blog"][0].title == "大模型综述"

    def test_detect_new_rss_items(self, backend):
        backend.save_rss_data(make_rss_data(crawl_time="08:00", titles=[("旧文", "tech-blog")]))
        current = make_rss_data(
            crawl_time="09:00",
            titles=[("旧文", "tech-blog"), ("新文", "tech-blog")],
        )
        new_items = backend.detect_new_rss_items(current)
        flat = str(new_items)
        assert "新文" in flat


class TestCleanup:
    def test_old_data_removed_by_retention(self, backend):
        old_date = "2020-01-01"
        backend.save_news_data(make_news_data(date=old_date))
        backend.save_news_data(make_news_data(date=DATE))

        # 保留最近 1 天，2020 年数据应被清理
        deleted = backend.cleanup_old_data(retention_days=1)
        assert deleted >= 1
        assert backend.get_today_all_data(date=old_date) is None

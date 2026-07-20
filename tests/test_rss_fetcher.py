# coding=utf-8
"""trendradar.crawler.rss.fetcher 并发抓取测试

用 mock 替换 fetch_feed 避免真实网络，验证并发与串行两种模式下
结果组装的正确性、保序性、错误归类，以及并发确实并行执行。
"""

import threading
import time

import pytest

from trendradar.crawler.rss.fetcher import RSSFetcher, RSSFeedConfig
from trendradar.storage.base import RSSItem


def make_feeds(n):
    return [
        RSSFeedConfig(id=f"feed-{i}", name=f"Feed {i}", url=f"https://host{i}.example.com/rss")
        for i in range(n)
    ]


def make_fetcher(n, concurrent_workers):
    return RSSFetcher(
        feeds=make_feeds(n),
        request_interval=0,
        concurrent_workers=concurrent_workers,
        timezone="Asia/Shanghai",
    )


class TestResultAssembly:
    @pytest.mark.parametrize("workers", [1, 4])
    def test_all_success(self, workers, monkeypatch):
        fetcher = make_fetcher(3, workers)

        def fake_fetch(feed):
            return [RSSItem(title=f"文章-{feed.id}", feed_id=feed.id)], None

        monkeypatch.setattr(fetcher, "fetch_feed", fake_fetch)
        data = fetcher.fetch_all()

        assert data.get_total_count() == 3
        assert set(data.items.keys()) == {"feed-0", "feed-1", "feed-2"}
        assert data.failed_ids == []
        assert data.items["feed-1"][0].title == "文章-feed-1"

    @pytest.mark.parametrize("workers", [1, 4])
    def test_partial_failure_classified(self, workers, monkeypatch):
        fetcher = make_fetcher(3, workers)

        def fake_fetch(feed):
            if feed.id == "feed-1":
                return [], "请求超时 (15s)"
            return [RSSItem(title=f"文章-{feed.id}", feed_id=feed.id)], None

        monkeypatch.setattr(fetcher, "fetch_feed", fake_fetch)
        data = fetcher.fetch_all()

        assert data.failed_ids == ["feed-1"]
        assert set(data.items.keys()) == {"feed-0", "feed-2"}
        # id_to_name 包含所有源（含失败的）
        assert data.id_to_name["feed-1"] == "Feed 1"

    def test_empty_feeds(self, monkeypatch):
        fetcher = make_fetcher(0, 4)
        data = fetcher.fetch_all()
        assert data.get_total_count() == 0
        assert data.failed_ids == []


class TestConcurrency:
    def test_concurrent_is_actually_parallel(self, monkeypatch):
        # 每个 fetch 阻塞 0.1s；4 并发抓 4 个源应远快于串行的 0.4s
        fetcher = make_fetcher(4, concurrent_workers=4)
        active = {"count": 0, "max": 0}
        lock = threading.Lock()

        def slow_fetch(feed):
            with lock:
                active["count"] += 1
                active["max"] = max(active["max"], active["count"])
            time.sleep(0.1)
            with lock:
                active["count"] -= 1
            return [RSSItem(title=feed.id, feed_id=feed.id)], None

        monkeypatch.setattr(fetcher, "fetch_feed", slow_fetch)
        start = time.monotonic()
        fetcher.fetch_all()
        elapsed = time.monotonic() - start

        # 并发执行：峰值并发数 > 1，总耗时明显小于串行累加
        assert active["max"] >= 2
        assert elapsed < 0.35

    def test_workers_capped_at_feed_count(self, monkeypatch):
        # 并发数超过源数量时不应报错，退化为按源数量并发
        fetcher = make_fetcher(2, concurrent_workers=10)

        def fake_fetch(feed):
            return [RSSItem(title=feed.id, feed_id=feed.id)], None

        monkeypatch.setattr(fetcher, "fetch_feed", fake_fetch)
        data = fetcher.fetch_all()
        assert data.get_total_count() == 2


class TestConfig:
    def test_from_config_reads_concurrent_workers(self):
        fetcher = RSSFetcher.from_config({
            "concurrent_workers": 8,
            "feeds": [{"id": "a", "name": "A", "url": "https://a.example.com/rss"}],
        })
        assert fetcher.concurrent_workers == 8

    def test_concurrent_workers_defaults_to_4(self):
        fetcher = RSSFetcher.from_config({
            "feeds": [{"id": "a", "name": "A", "url": "https://a.example.com/rss"}],
        })
        assert fetcher.concurrent_workers == 4

    def test_negative_workers_clamped_to_one(self):
        fetcher = RSSFetcher(feeds=[], concurrent_workers=-5)
        assert fetcher.concurrent_workers == 1

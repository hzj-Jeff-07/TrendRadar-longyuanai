# coding=utf-8
"""trendradar.report.html 渲染回归测试

用固定输入渲染完整 HTML 报告，与基准文件（golden file）逐字节比较，
为重构 html.py（拆分静态资产、提升嵌套函数）提供回归保护。

基准文件更新方式：删除 tests/fixtures/report_golden.html 后运行本测试，
会自动重新生成（重新生成的那次运行会跳过比较）。
"""

from datetime import datetime
from pathlib import Path

import pytest

from trendradar.report.html import render_html_content

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_FILE = FIXTURES_DIR / "report_golden.html"


def fixed_time() -> datetime:
    return datetime(2026, 1, 15, 8, 30, 0)


def build_report_data():
    """构造覆盖主要渲染路径的报告数据"""
    title_common = {
        "time_display": "08-00 ~ 08-30",
        "count": 3,
        "rank_threshold": 10,
        "is_new": False,
    }
    return {
        "stats": [
            {
                "word": "华为",
                "count": 2,
                "titles": [
                    {
                        "title": "华为发布新款折叠屏手机",
                        "source_name": "微博",
                        "ranks": [1, 2],
                        "rank_timeline": [{"time": "08-00", "rank": 1}],
                        "url": "https://example.com/news/1",
                        "mobile_url": "https://m.example.com/news/1",
                        "matched_keyword": "华为",
                        **title_common,
                    },
                    {
                        "title": "华为鸿蒙系统更新",
                        "source_name": "知乎",
                        "ranks": [5],
                        "url": "https://example.com/news/2",
                        "mobile_url": "",
                        "is_new": True,
                        "matched_keyword": "华为",
                        "time_display": "08-30",
                        "count": 1,
                        "rank_threshold": 10,
                    },
                ],
            },
            {
                "word": "特斯拉",
                "count": 1,
                "titles": [
                    {
                        "title": "特斯拉股价大涨 <script>alert(1)</script>",
                        "source_name": "百度",
                        "ranks": [3],
                        "url": "https://example.com/news/3",
                        "mobile_url": "",
                        "matched_keyword": "特斯拉",
                        **title_common,
                    },
                ],
            },
        ],
        "new_titles": [
            {
                "source_name": "微博",
                "titles": [
                    {
                        "title": "华为鸿蒙系统更新",
                        "ranks": [5],
                        "url": "https://example.com/news/2",
                        "mobile_url": "",
                    }
                ],
            }
        ],
        "failed_ids": ["broken-platform"],
        "total_new_count": 1,
        "hotlist_total": 120,
        "platform_total": 5,
        "rss_source_total": 3,
        "rss_source_failed": 1,
        "rss_total_count": 42,
        "rss_matched_count": 7,
    }


def build_rss_items():
    return [
        {
            "word": "AI",
            "count": 1,
            "titles": [
                {
                    "title": "大模型月度综述",
                    "source_name": "Tech Blog",
                    "url": "https://blog.example.com/llm",
                    "published_at": "2026-01-14T20:00:00+00:00",
                    "author": "作者甲",
                }
            ],
        }
    ]


def build_standalone_data():
    return {
        "platforms": [
            {
                "name": "V2EX",
                "items": [
                    {
                        "title": "独立区平台条目",
                        "rank": 1,
                        "ranks": [1],
                        "url": "https://v2ex.com/t/1",
                        "first_time": "08-00",
                        "last_time": "08-30",
                        "count": 2,
                    }
                ],
            }
        ],
        "rss_feeds": [
            {
                "name": "Hacker News",
                "items": [
                    {
                        "title": "Show HN: Something",
                        "url": "https://news.ycombinator.com/item?id=1",
                        "published_at": "2026-01-15T00:00:00+00:00",
                        "author": "hn_user",
                    }
                ],
            }
        ],
    }


def render_fixture() -> str:
    return render_html_content(
        build_report_data(),
        total_titles=3,
        mode="daily",
        update_info={"current_version": "6.10.0", "remote_version": "6.11.0"},
        get_time_func=fixed_time,
        rss_items=build_rss_items(),
        rss_new_items=build_rss_items(),
        standalone_data=build_standalone_data(),
        ai_analysis=None,
        show_new_section=True,
    )


class TestRenderHtmlContent:
    def test_matches_golden_file(self):
        html = render_fixture()
        if not GOLDEN_FILE.exists():
            FIXTURES_DIR.mkdir(exist_ok=True)
            GOLDEN_FILE.write_text(html, encoding="utf-8")
            pytest.skip("已生成基准文件，请重新运行测试进行比较")
        assert html == GOLDEN_FILE.read_text(encoding="utf-8"), (
            "HTML 输出与基准文件不一致。若是有意修改渲染结果，"
            "删除 tests/fixtures/report_golden.html 后重跑测试即可重新生成基准。"
        )

    def test_basic_structure(self):
        html = render_fixture()
        assert "<!DOCTYPE html>" in html
        assert "热点新闻分析" in html
        assert "华为发布新款折叠屏手机" in html
        # XSS 防护：脚本标签必须被转义
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_minimal_input(self):
        html = render_html_content(
            {"stats": [], "new_titles": [], "failed_ids": [], "total_new_count": 0},
            total_titles=0,
            get_time_func=fixed_time,
        )
        assert "<!DOCTYPE html>" in html

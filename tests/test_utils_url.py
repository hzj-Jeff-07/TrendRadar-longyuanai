# coding=utf-8
"""trendradar.utils.url 单元测试"""

from trendradar.utils.url import normalize_url


class TestNormalizeUrl:
    def test_weibo_dynamic_params_removed(self):
        url = "https://s.weibo.com/weibo?q=test&band_rank=6&Refer=top"
        assert normalize_url(url, "weibo") == "https://s.weibo.com/weibo?q=test"

    def test_weibo_params_kept_for_other_platform(self):
        # band_rank 只对 weibo 平台移除
        url = "https://example.com/page?band_rank=6"
        assert "band_rank=6" in normalize_url(url, "zhihu")

    def test_utm_params_removed(self):
        url = "https://example.com/page?id=1&utm_source=twitter&utm_medium=social"
        assert normalize_url(url, "") == "https://example.com/page?id=1"

    def test_tracking_params_case_insensitive(self):
        url = "https://example.com/page?id=1&UTM_SOURCE=x"
        assert normalize_url(url, "") == "https://example.com/page?id=1"

    def test_no_query_unchanged(self):
        url = "https://example.com/path/to/page"
        assert normalize_url(url, "") == url

    def test_params_sorted_alphabetically(self):
        url = "https://example.com/?b=2&a=1"
        assert normalize_url(url, "") == "https://example.com/?a=1&b=2"

    def test_all_params_removed_drops_query_and_fragment(self):
        url = "https://example.com/page?utm_source=x#section"
        assert normalize_url(url, "") == "https://example.com/page"

    def test_fragment_removed_when_query_present(self):
        url = "https://example.com/page?id=1#section"
        assert normalize_url(url, "") == "https://example.com/page?id=1"

    def test_empty_url(self):
        assert normalize_url("", "") == ""

    def test_blank_values_kept(self):
        url = "https://example.com/page?q="
        assert normalize_url(url, "") == "https://example.com/page?q="

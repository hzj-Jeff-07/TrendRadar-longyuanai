# coding=utf-8
"""trendradar.crawler.fetcher 域名安全校验单元测试"""

from trendradar.crawler.fetcher import DataFetcher


class TestCheckDomainSafety:
    def test_exact_domain_passes(self):
        items = [{"url": "https://baidu.com/s?wd=1", "mobileUrl": ""}]
        assert DataFetcher._check_domain_safety(items, "baidu.com") is None

    def test_subdomain_passes(self):
        items = [{"url": "https://www.baidu.com/s?wd=1"}]
        assert DataFetcher._check_domain_safety(items, "baidu.com") is None

    def test_http_rejected(self):
        items = [{"url": "http://baidu.com/s?wd=1"}]
        assert DataFetcher._check_domain_safety(items, "baidu.com") is not None

    def test_wrong_domain_rejected(self):
        items = [{"url": "https://evil.com/page"}]
        assert DataFetcher._check_domain_safety(items, "baidu.com") is not None

    def test_userinfo_trick_rejected(self):
        # https://baidu.com@evil.com 的真实主机是 evil.com
        items = [{"url": "https://baidu.com@evil.com/page"}]
        assert DataFetcher._check_domain_safety(items, "baidu.com") is not None

    def test_suffix_trick_rejected(self):
        # evilbaidu.com 不是 baidu.com 的子域名
        items = [{"url": "https://evilbaidu.com/page"}]
        assert DataFetcher._check_domain_safety(items, "baidu.com") is not None

    def test_mobile_url_also_checked(self):
        items = [{"url": "https://baidu.com/x", "mobileUrl": "https://evil.com/x"}]
        assert DataFetcher._check_domain_safety(items, "baidu.com") is not None

    def test_empty_expected_domain_skips_check(self):
        items = [{"url": "http://anything.com/x"}]
        assert DataFetcher._check_domain_safety(items, "") is None

    def test_empty_url_fields_skipped(self):
        items = [{"url": "", "mobileUrl": ""}]
        assert DataFetcher._check_domain_safety(items, "baidu.com") is None

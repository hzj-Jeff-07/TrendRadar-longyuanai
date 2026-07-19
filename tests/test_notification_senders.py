# coding=utf-8
"""trendradar.notification.senders 公共发送辅助函数单元测试"""

from trendradar.notification.senders import (
    _make_proxies,
    _prepare_batches,
    _send_batches,
    _send_batches_reversed,
)


class TestMakeProxies:
    def test_none_when_no_proxy(self):
        assert _make_proxies(None) is None
        assert _make_proxies("") is None

    def test_both_schemes_set(self):
        proxies = _make_proxies("http://127.0.0.1:7890")
        assert proxies == {
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890",
        }


class TestPrepareBatches:
    def test_passes_args_and_reserves_header_space(self):
        captured = {}

        def fake_split(report_data, format_type, update_info, **kwargs):
            captured["format_type"] = format_type
            captured["max_bytes"] = kwargs["max_bytes"]
            captured["report_type"] = kwargs["report_type"]
            return ["content"]

        batches = _prepare_batches(
            "feishu", {"stats": []}, "全天汇总", None, "daily",
            29000, fake_split, None, None, None, None,
        )
        assert batches == ["content"]
        assert captured["format_type"] == "feishu"
        # 预留了批次头部空间
        assert captured["max_bytes"] < 29000
        assert captured["report_type"] == "全天汇总"

    def test_custom_split_and_header_format(self):
        captured = {}

        def fake_split(report_data, format_type, update_info, **kwargs):
            captured["format_type"] = format_type
            return ["content"]

        _prepare_batches(
            "wework", {}, "测试", None, "daily",
            4000, fake_split, None, None, None, None,
            header_format="wework_text",
        )
        # 分批格式使用 channel，头部格式独立指定
        assert captured["format_type"] == "wework"

    def test_explicit_header_reserve(self):
        captured = {}

        def fake_split(report_data, format_type, update_info, **kwargs):
            captured["max_bytes"] = kwargs["max_bytes"]
            return ["content"]

        _prepare_batches(
            "wework", {}, "测试", None, "daily",
            4000, fake_split, None, None, None, None,
            header_reserve=200,
        )
        assert captured["max_bytes"] == 3800


class TestSendBatches:
    def test_all_success(self):
        sent = []

        def send_one(content):
            sent.append(content)
            return True, None

        assert _send_batches(["a", "b"], "测试", "全天汇总", 0, send_one) is True
        assert sent == ["a", "b"]

    def test_fail_fast_stops_remaining(self):
        sent = []

        def send_one(content):
            sent.append(content)
            return (content != "b"), "错误：模拟失败"

        assert _send_batches(["a", "b", "c"], "测试", "全天汇总", 0, send_one) is False
        # b 失败后 c 不再发送
        assert sent == ["a", "b"]

    def test_exception_returns_false(self):
        def send_one(content):
            raise ConnectionError("网络异常")

        assert _send_batches(["a"], "测试", "全天汇总", 0, send_one) is False

    def test_transform_applied_before_send(self):
        sent = []

        def send_one(content):
            sent.append(content)
            return True, None

        _send_batches(["abc"], "测试", "全天汇总", 0, send_one, transform=str.upper)
        assert sent == ["ABC"]


class TestSendBatchesReversed:
    def test_sends_in_reverse_order_with_correct_numbering(self):
        sent = []

        def send_one(content, actual_num):
            sent.append((content, actual_num))
            return True

        assert _send_batches_reversed(["a", "b", "c"], "测试", "全天汇总", 0, send_one) is True
        # 反向发送，但批次编号仍是用户视角
        assert sent == [("c", 3), ("b", 2), ("a", 1)]

    def test_partial_success_returns_true(self):
        def send_one(content, actual_num):
            return content != "b"

        assert _send_batches_reversed(["a", "b"], "测试", "全天汇总", 0, send_one) is True

    def test_all_failed_returns_false(self):
        def send_one(content, actual_num):
            return False

        assert _send_batches_reversed(["a", "b"], "测试", "全天汇总", 0, send_one) is False

    def test_exception_does_not_abort_remaining(self):
        sent = []

        def send_one(content, actual_num):
            sent.append(content)
            if content == "b":
                raise ConnectionError("网络异常")
            return True

        assert _send_batches_reversed(["a", "b"], "测试", "全天汇总", 0, send_one) is True
        # b（先发）抛异常后 a 仍然发送
        assert sent == ["b", "a"]

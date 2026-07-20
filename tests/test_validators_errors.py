# coding=utf-8
"""mcp_server 校验器异常行为测试

固化异常审计成果：校验失败抛出领域异常 InvalidParameterError，
且通过 `from None` / `from e` 显式管理异常链（避免 B904 类丢链）。
"""

import json

import pytest

from mcp_server.utils.errors import InvalidParameterError
from mcp_server.utils.validators import (
    _parse_string_to_float,
    _parse_string_to_int,
)


class TestParseStringToInt:
    def test_valid_int(self):
        assert _parse_string_to_int("42") == 42

    def test_float_string_truncated(self):
        assert _parse_string_to_int("3.9") == 3

    def test_invalid_raises_domain_error(self):
        with pytest.raises(InvalidParameterError) as exc_info:
            _parse_string_to_int("abc", "limit")
        # 消息包含参数名，异常链已显式断开（from None）
        assert "limit" in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True


class TestParseStringToFloat:
    def test_valid_float(self):
        assert _parse_string_to_float("0.6") == 0.6

    def test_invalid_raises_domain_error(self):
        with pytest.raises(InvalidParameterError) as exc_info:
            _parse_string_to_float("xyz", "threshold")
        assert "threshold" in str(exc_info.value)
        assert exc_info.value.__cause__ is None


class TestDateRangeErrorChain:
    def test_bad_json_preserves_cause(self):
        from mcp_server.utils.validators import validate_date_range

        with pytest.raises(InvalidParameterError) as exc_info:
            # 以 { } 包裹但内容非法 JSON，命中 JSON 解析分支
            validate_date_range('{"start": bad}')
        # JSON 解析失败场景保留原始异常链（from e）便于排查
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

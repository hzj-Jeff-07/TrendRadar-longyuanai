# coding=utf-8
"""trendradar.utils.time 单元测试"""

from datetime import datetime, timedelta, timezone

from trendradar.utils.time import (
    calculate_days_old,
    convert_time_for_display,
    format_date_folder,
    format_iso_time_friendly,
    get_configured_time,
    is_within_days,
)


class TestConvertTimeForDisplay:
    def test_converts_hyphen_to_colon(self):
        assert convert_time_for_display("15-30") == "15:30"

    def test_keeps_colon_format(self):
        assert convert_time_for_display("15:30") == "15:30"

    def test_keeps_invalid_length(self):
        assert convert_time_for_display("1-30") == "1-30"

    def test_empty_string(self):
        assert convert_time_for_display("") == ""


class TestFormatDateFolder:
    def test_explicit_date_passthrough(self):
        assert format_date_folder("2025-12-09") == "2025-12-09"

    def test_default_uses_current_date(self):
        result = format_date_folder(timezone="Asia/Shanghai")
        # ISO 格式 YYYY-MM-DD
        datetime.strptime(result, "%Y-%m-%d")


class TestGetConfiguredTime:
    def test_returns_tz_aware(self):
        dt = get_configured_time("Asia/Shanghai")
        assert dt.tzinfo is not None

    def test_unknown_timezone_falls_back(self):
        dt = get_configured_time("Not/AZone")
        assert dt.tzinfo is not None


class TestFormatIsoTimeFriendly:
    def test_utc_offset_converted_to_shanghai(self):
        assert (
            format_iso_time_friendly("2025-12-29T00:20:00+00:00", "Asia/Shanghai")
            == "12-29 08:20"
        )

    def test_z_suffix_converted(self):
        assert (
            format_iso_time_friendly("2025-12-29T00:20:00Z", "Asia/Shanghai")
            == "12-29 08:20"
        )

    def test_naive_time_assumed_utc(self):
        assert (
            format_iso_time_friendly("2025-12-29T00:20:00", "Asia/Shanghai")
            == "12-29 08:20"
        )

    def test_time_only_output(self):
        assert (
            format_iso_time_friendly(
                "2025-12-29T00:20:00+00:00", "Asia/Shanghai", include_date=False
            )
            == "08:20"
        )

    def test_empty_input(self):
        assert format_iso_time_friendly("") == ""

    def test_unparseable_returns_simplified(self):
        # 无法解析但含 T 分隔符时，退化为 MM-DD HH:MM 截取
        assert format_iso_time_friendly("2025-12-29Tbadtime") == "12-29 badti"


class TestIsWithinDays:
    def test_recent_time_is_kept(self):
        recent = datetime.now(timezone.utc).isoformat()
        assert is_within_days(recent, 3) is True

    def test_old_time_is_filtered(self):
        assert is_within_days("2020-01-01T00:00:00+00:00", 3) is False

    def test_zero_max_days_disables_filter(self):
        assert is_within_days("2020-01-01T00:00:00+00:00", 0) is True

    def test_empty_time_is_kept(self):
        assert is_within_days("", 3) is True

    def test_unparseable_time_is_kept(self):
        assert is_within_days("not-a-time", 3) is True


class TestCalculateDaysOld:
    def test_empty_returns_none(self):
        assert calculate_days_old("") is None

    def test_unparseable_returns_none(self):
        assert calculate_days_old("garbage") is None

    def test_one_day_ago(self):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        days = calculate_days_old(yesterday)
        assert days is not None
        assert 0.9 < days < 1.1

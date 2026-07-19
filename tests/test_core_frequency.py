# coding=utf-8
"""trendradar.core.frequency 单元测试"""

import pytest

from trendradar.core.frequency import (
    _parse_word,
    _word_matches,
    load_frequency_words,
    matches_word_groups,
)


def load_from_text(tmp_path, text):
    """把频率词文本写入临时文件后加载"""
    f = tmp_path / "frequency_words.txt"
    f.write_text(text, encoding="utf-8")
    return load_frequency_words(str(f))


class TestParseWord:
    def test_plain_word(self):
        result = _parse_word("华为")
        assert result["word"] == "华为"
        assert result["is_regex"] is False
        assert result["display_name"] is None

    def test_regex_word(self):
        result = _parse_word("/京东|刘强东/")
        assert result["is_regex"] is True
        assert result["pattern"].search("京东物流上市")

    def test_display_name(self):
        result = _parse_word("/京东|刘强东/ => 京东")
        assert result["is_regex"] is True
        assert result["display_name"] == "京东"

    def test_invalid_regex_falls_back_to_plain(self):
        result = _parse_word("/[未闭合/")
        assert result["is_regex"] is False

    def test_empty_display_name_ignored(self):
        result = _parse_word("华为 =>")
        assert result["word"] == "华为"
        assert result["display_name"] is None


class TestWordMatches:
    def test_legacy_string_config(self):
        assert _word_matches("华为", "华为发布新手机") is True
        assert _word_matches("华为", "苹果发布新手机") is False

    def test_dict_substring(self):
        assert _word_matches(_parse_word("AI"), "openai 发布新模型".lower()) is True

    def test_dict_regex(self):
        config = _parse_word("/gpt-\\d+/")
        assert _word_matches(config, "gpt-5 发布") is True
        assert _word_matches(config, "gpt 发布") is False


class TestLoadFrequencyWords:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_frequency_words("/nonexistent/path.txt")

    def test_basic_groups(self, tmp_path):
        groups, filters, global_filters = load_from_text(tmp_path, "华为\n鸿蒙\n\n比亚迪")
        assert len(groups) == 2
        assert groups[0]["group_key"] == "华为 鸿蒙"
        assert filters == []
        assert global_filters == []

    def test_required_filter_and_max_count(self, tmp_path):
        groups, filters, _ = load_from_text(tmp_path, "+特斯拉\n股价\n!召回\n@5")
        assert len(groups) == 1
        group = groups[0]
        assert group["required"][0]["word"] == "特斯拉"
        assert group["normal"][0]["word"] == "股价"
        assert group["max_count"] == 5
        assert filters[0]["word"] == "召回"

    def test_global_filter_section(self, tmp_path):
        text = "[GLOBAL_FILTER]\n广告\n推广\n\n[WORD_GROUPS]\n华为"
        groups, _, global_filters = load_from_text(tmp_path, text)
        assert global_filters == ["广告", "推广"]
        assert len(groups) == 1

    def test_group_alias(self, tmp_path):
        groups, _, _ = load_from_text(tmp_path, "[科技巨头]\n华为\n苹果")
        assert groups[0]["display_name"] == "科技巨头"

    def test_comment_lines_ignored(self, tmp_path):
        groups, _, _ = load_from_text(tmp_path, "# 注释\n华为")
        assert len(groups) == 1
        assert groups[0]["group_key"] == "华为"

    def test_invalid_max_count_ignored(self, tmp_path):
        groups, _, _ = load_from_text(tmp_path, "华为\n@abc\n@-1")
        assert groups[0]["max_count"] == 0


class TestMatchesWordGroups:
    def make_groups(self, tmp_path, text):
        return load_from_text(tmp_path, text)

    def test_empty_groups_match_all(self):
        assert matches_word_groups("任意标题", [], []) is True

    def test_empty_title_never_matches(self):
        assert matches_word_groups("", [], []) is False
        assert matches_word_groups(None, [], []) is False

    def test_normal_word_match(self, tmp_path):
        groups, filters, gf = self.make_groups(tmp_path, "华为")
        assert matches_word_groups("华为发布新品", groups, filters, gf) is True
        assert matches_word_groups("苹果发布新品", groups, filters, gf) is False

    def test_required_words_all_needed(self, tmp_path):
        groups, filters, gf = self.make_groups(tmp_path, "+特斯拉\n+股价")
        assert matches_word_groups("特斯拉股价大涨", groups, filters, gf) is True
        assert matches_word_groups("特斯拉发布新车", groups, filters, gf) is False

    def test_filter_word_excludes(self, tmp_path):
        groups, filters, gf = self.make_groups(tmp_path, "特斯拉\n!召回")
        assert matches_word_groups("特斯拉召回部分车辆", groups, filters, gf) is False
        assert matches_word_groups("特斯拉销量创新高", groups, filters, gf) is True

    def test_global_filter_highest_priority(self, tmp_path):
        text = "[GLOBAL_FILTER]\n广告\n\n[WORD_GROUPS]\n华为"
        groups, filters, gf = self.make_groups(tmp_path, text)
        assert matches_word_groups("华为广告投放", groups, filters, gf) is False

    def test_case_insensitive(self, tmp_path):
        groups, filters, gf = self.make_groups(tmp_path, "OpenAI")
        assert matches_word_groups("OPENAI 发布新模型", groups, filters, gf) is True

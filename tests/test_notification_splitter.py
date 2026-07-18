# coding=utf-8
"""trendradar.notification.splitter 分批辅助函数单元测试"""

from trendradar.notification.splitter import (
    _safe_append_batch,
    _split_content_by_lines,
)


class TestSplitContentByLines:
    def test_short_content_single_batch(self):
        batches = _split_content_by_lines("line1\nline2", "\n[footer]", 4000, "")
        assert len(batches) == 1
        assert batches[0] == "line1\nline2\n\n[footer]"

    def test_long_content_split_within_limit(self):
        content = "\n".join(f"line-{i:03d}" for i in range(100)) + "\n"
        footer = "\n[footer]"
        max_bytes = 200
        batches = _split_content_by_lines(content, footer, max_bytes, "[header]\n")

        assert len(batches) > 1
        for batch in batches:
            assert len(batch.encode("utf-8")) <= max_bytes
            assert batch.endswith(footer)

    def test_no_content_lost(self):
        lines = [f"line-{i:03d}" for i in range(50)]
        content = "\n".join(lines) + "\n"
        batches = _split_content_by_lines(content, "\n[f]", 150, "")
        merged = "".join(batches)
        for line in lines:
            assert line in merged

    def test_continuation_batches_have_header(self):
        content = "\n".join(f"line-{i:03d}" for i in range(50)) + "\n"
        batches = _split_content_by_lines(content, "\n[f]", 150, "[续]\n")
        assert len(batches) > 1
        for batch in batches[1:]:
            assert batch.startswith("[续]\n")


class TestSafeAppendBatch:
    def test_under_limit_appends_single(self):
        batches = []
        _safe_append_batch(batches, "short content", "\n[f]", 4000)
        assert batches == ["short content\n[f]"]

    def test_over_limit_splits(self):
        batches = []
        content = "\n".join(f"line-{i:03d}" for i in range(100)) + "\n"
        _safe_append_batch(batches, content, "\n[f]", 200)
        assert len(batches) > 1
        for batch in batches:
            assert len(batch.encode("utf-8")) <= 200

    def test_single_oversized_line_truncated(self):
        batches = []
        _safe_append_batch(batches, "x" * 500, "\n[f]", 100)
        assert len(batches) == 1
        assert len(batches[0].encode("utf-8")) <= 100

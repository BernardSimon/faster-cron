"""
测试 CronBase._match_field 和 _expand_field 的边界情况
"""

from __future__ import annotations

import datetime

from faster_cron.base import CronBase


class TestMatchField:
    """CronBase._match_field 边界情况测试"""

    def test_star_matches_anything(self):
        assert CronBase._match_field("*", 0) is True
        assert CronBase._match_field("*", 59) is True

    def test_star_slash_step(self):
        """*/5 应匹配 0, 5, 10, ..., 55"""
        for v in range(60):
            expected = v % 5 == 0
            assert CronBase._match_field("*/5", v) is expected, f"*/5 vs {v}"

    def test_range_with_step(self):
        """1-10/2 应匹配 1, 3, 5, 7, 9"""
        matched = [v for v in range(11) if CronBase._match_field("1-10/2", v)]
        assert matched == [1, 3, 5, 7, 9]

    def test_fixed_point_step(self):
        """5/10 应匹配 5, 15, 25, 35, 45, 55"""
        matched = [v for v in range(60) if CronBase._match_field("5/10", v)]
        assert matched == [5, 15, 25, 35, 45, 55]

    def test_comma_list(self):
        """1,3,5 应仅匹配 1, 3, 5"""
        for v in range(10):
            expected = v in (1, 3, 5)
            assert CronBase._match_field("1,3,5", v) is expected

    def test_comma_with_ranges(self):
        """1-3,7-9 应匹配 1,2,3,7,8,9"""
        matched = [v for v in range(10) if CronBase._match_field("1-3,7-9", v)]
        assert matched == [1, 2, 3, 7, 8, 9]

    def test_weekday_7_maps_to_0(self):
        """Cron 中 7 = Sunday，应映射到 0"""
        assert CronBase._match_field("7", 0) is True
        assert CronBase._match_field("7", 1) is False

    def test_exact_value(self):
        assert CronBase._match_field("42", 42) is True
        assert CronBase._match_field("42", 43) is False

    def test_range_pattern(self):
        """10-20 应匹配 [10, 20]"""
        assert CronBase._match_field("10-20", 10) is True
        assert CronBase._match_field("10-20", 15) is True
        assert CronBase._match_field("10-20", 20) is True
        assert CronBase._match_field("10-20", 9) is False
        assert CronBase._match_field("10-20", 21) is False

    def test_invalid_field_returns_false(self):
        assert CronBase._match_field("abc", 0) is False
        assert CronBase._match_field("abc", 5) is False

    def test_negative_step_handled_gracefully(self):
        """负数步长不应崩溃"""
        # 这可能返回 False，但不应抛异常
        result = CronBase._match_field("*/-1", 0)
        assert isinstance(result, bool)


class TestExpandField:
    """CronBase._expand_field 测试"""

    def test_star_expands_full_range(self):
        assert CronBase._expand_field("*", 0, 59) == list(range(60))
        assert CronBase._expand_field("*", 1, 12) == list(range(1, 13))

    def test_step_pattern(self):
        assert CronBase._expand_field("*/5", 0, 59) == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

    def test_range_with_step(self):
        assert CronBase._expand_field("1-10/2", 0, 59) == [1, 3, 5, 7, 9]

    def test_comma_list(self):
        assert CronBase._expand_field("1,3,5", 0, 59) == [1, 3, 5]

    def test_exact_value(self):
        assert CronBase._expand_field("42", 0, 59) == [42]

    def test_weekday_7_maps_to_0(self):
        result = CronBase._expand_field("7", 0, 7)
        assert 0 in result

    def test_empty_result_for_invalid(self):
        result = CronBase._expand_field("abc", 0, 59)
        assert result == []


class TestIsTimeMatch:
    """CronBase.is_time_match 边界情况测试"""

    def test_day_weekday_both_restricted_uses_or(self):
        """当 day 和 weekday 都有限制时，使用 OR 关系"""
        # 2026-06-08 is Monday (weekday=1 in cron), day=8
        dt = datetime.datetime(2026, 6, 8, 9, 0, 0)
        # 匹配 day=8 OR weekday=1
        assert CronBase.is_time_match("0 0 9 8 * 1", dt) is True
        # 只匹配 day=9（不匹配），但 weekday=1（匹配） -> OR = True
        assert CronBase.is_time_match("0 0 9 9 * 1", dt) is True

    def test_day_star_weekday_restricted_uses_and(self):
        """当 day=* 且 weekday 有限制时，使用 AND 关系"""
        # 2026-06-08 is Monday
        dt = datetime.datetime(2026, 6, 8, 9, 0, 0)
        assert CronBase.is_time_match("0 0 9 * * 1", dt) is True
        # Tuesday
        dt_tue = datetime.datetime(2026, 6, 9, 9, 0, 0)
        assert CronBase.is_time_match("0 0 9 * * 1", dt_tue) is False

    def test_six_field_with_seconds(self):
        """6字段表达式支持秒"""
        dt = datetime.datetime(2026, 6, 10, 12, 30, 5)
        assert CronBase.is_time_match("5 * * * * *", dt) is True
        assert CronBase.is_time_match("6 * * * * *", dt) is False

    def test_invalid_expression_returns_false(self):
        dt = datetime.datetime(2026, 6, 10, 12, 0, 0)
        assert CronBase.is_time_match("invalid", dt) is False
        assert CronBase.is_time_match("1 2 3", dt) is False
        assert CronBase.is_time_match("1 2 3 4 5 6 7", dt) is False

    def test_five_field_expression(self):
        """5字段：秒默认为 0"""
        dt = datetime.datetime(2026, 6, 10, 12, 30, 0)
        assert CronBase.is_time_match("30 12 * * *", dt) is True
        assert CronBase.is_time_match("31 12 * * *", dt) is False

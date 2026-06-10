"""
测试 _calculate_next_trigger 的字段约束跳跃算法
"""

from __future__ import annotations

import datetime

from faster_cron.base import CronBase


def test_next_trigger_every_minute():
    """5字段：每分钟触发（分钟字段为 *，秒默认为 0）"""
    from_time = datetime.datetime(2026, 6, 10, 12, 30, 0)
    result = CronBase.calculate_next_trigger("* * * * *", from_time)
    assert result == datetime.datetime(2026, 6, 10, 12, 31, 0)


def test_next_trigger_every_second():
    """6字段：每秒触发"""
    from_time = datetime.datetime(2026, 6, 10, 12, 30, 0)
    result = CronBase.calculate_next_trigger("* * * * * *", from_time)
    assert result == datetime.datetime(2026, 6, 10, 12, 30, 1)


def test_next_trigger_specific_weekday():
    """周一 9:30 触发"""
    # 2026-06-08 is Monday
    from_time = datetime.datetime(2026, 6, 8, 9, 0, 0)
    result = CronBase.calculate_next_trigger("30 9 * * 1", from_time)
    assert result == datetime.datetime(2026, 6, 8, 9, 30, 0)


def test_next_trigger_step_pattern():
    """每5秒触发"""
    from_time = datetime.datetime(2026, 6, 10, 12, 30, 3)
    result = CronBase.calculate_next_trigger("*/5 * * * * *", from_time)
    assert result == datetime.datetime(2026, 6, 10, 12, 30, 5)


def test_next_trigger_range_with_step():
    """1-10分钟区间内每2分钟触发"""
    from_time = datetime.datetime(2026, 6, 10, 12, 0, 0)
    result = CronBase.calculate_next_trigger("0 1-10/2 * * * *", from_time)
    assert result == datetime.datetime(2026, 6, 10, 12, 1, 0)


def test_next_trigger_complex_yearly():
    """每年1月1日 00:00:00 触发"""
    from_time = datetime.datetime(2026, 6, 10, 12, 0, 0)
    result = CronBase.calculate_next_trigger("0 0 0 1 1 *", from_time)
    assert result == datetime.datetime(2027, 1, 1, 0, 0, 0)


def test_next_trigger_five_field_expression():
    """5字段表达式（秒默认为0）"""
    from_time = datetime.datetime(2026, 6, 10, 12, 30, 30)
    result = CronBase.calculate_next_trigger("31 12 * * *", from_time)
    assert result == datetime.datetime(2026, 6, 10, 12, 31, 0)


def test_next_trigger_raises_on_invalid():
    """无效表达式应抛出 ValueError"""
    import pytest

    with pytest.raises(ValueError):
        CronBase.calculate_next_trigger("invalid", datetime.datetime.now())


def test_next_trigger_from_specific_time():
    """从指定时间开始计算"""
    from_time = datetime.datetime(2026, 12, 31, 23, 59, 59)
    result = CronBase.calculate_next_trigger("0 0 * * * *", from_time)
    assert result == datetime.datetime(2027, 1, 1, 0, 0, 0)


def test_next_trigger_comma_list_minutes():
    """逗号列表：第0和第30分钟触发"""
    from_time = datetime.datetime(2026, 6, 10, 12, 15, 0)
    result = CronBase.calculate_next_trigger("0 0,30 * * * *", from_time)
    assert result == datetime.datetime(2026, 6, 10, 12, 30, 0)


def test_next_trigger_crosses_month_boundary():
    """跨月边界"""
    from_time = datetime.datetime(2026, 6, 30, 23, 59, 59)
    result = CronBase.calculate_next_trigger("0 0 0 * * *", from_time)
    assert result == datetime.datetime(2026, 7, 1, 0, 0, 0)


def test_next_trigger_result_is_always_after_from_time():
    """结果必须严格在 from_time 之后"""
    from_time = datetime.datetime(2026, 6, 10, 12, 0, 0)
    # 当前时间正好匹配，结果应该是下一次
    result = CronBase.calculate_next_trigger("0 * * * * *", from_time)
    assert result > from_time

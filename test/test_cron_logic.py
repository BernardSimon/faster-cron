from datetime import datetime

from faster_cron.base import CronBase


def test_supports_five_field_expressions():
    assert CronBase.is_time_match("30 9 * * 1", datetime(2024, 1, 1, 9, 30, 0)) is True
    assert CronBase.is_time_match("30 9 * * 1", datetime(2024, 1, 1, 9, 30, 1)) is False


def test_supports_six_field_expressions():
    assert (
        CronBase.is_time_match("15 30 9 * * 1", datetime(2024, 1, 1, 9, 30, 15)) is True
    )
    assert (
        CronBase.is_time_match("15 30 9 * * 1", datetime(2024, 1, 1, 9, 30, 14))
        is False
    )


def test_day_and_weekday_follow_standard_or_logic():
    matched_day = datetime(2023, 10, 1, 0, 0, 0)  # Sunday and the 1st
    assert CronBase.is_time_match("0 0 1 * 5", matched_day) is True


def test_weekday_seven_maps_to_sunday():
    sunday = datetime(2024, 3, 17, 12, 0, 0)
    assert CronBase.is_time_match("0 12 * * 7", sunday) is True


def test_invalid_expression_returns_false():
    now = datetime.now()
    assert CronBase.is_time_match("invalid", now) is False
    assert CronBase.is_time_match("* * *", now) is False

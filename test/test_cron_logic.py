from faster_cron.base import CronBase
from datetime import datetime


def test_day_weekday_or_logic():
    # 场景：2023-10-01 是周日 (0)
    dt = datetime(2023, 10, 1)

    # 1. 匹配 1号 (Day)
    assert CronBase.is_time_match("0 0 1 * *", dt) == True
    # 2. 匹配 周日 (Weekday)
    assert CronBase.is_time_match("0 0 * * 0", dt) == True
    # 3. 匹配 1号 OR 周五 (5)。虽然 1号是周日不是周五，但因为 OR 关系，应该匹配成功
    assert CronBase.is_time_match("0 0 1 * 5", dt) == True
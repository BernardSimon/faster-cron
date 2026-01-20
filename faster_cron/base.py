import datetime


class CronBase:
    """提供 Cron 表达式解析的底层逻辑"""

    @staticmethod
    def is_time_match(expression: str, now: datetime.datetime) -> bool:
        parts = expression.split()
        if len(parts) == 5:
            # 分 时 日 月 周 -> 补齐秒为 0
            sec_part, min_part, hour_part, day_part, month_part, weekday_part = "0", *parts
        elif len(parts) == 6:
            sec_part, min_part, hour_part, day_part, month_part, weekday_part = parts
        else:
            return False

        return (
                CronBase._match_field(sec_part, now.second) and
                CronBase._match_field(min_part, now.minute) and
                CronBase._match_field(hour_part, now.hour) and
                CronBase._match_field(day_part, now.day) and
                CronBase._match_field(month_part, now.month) and
                CronBase._match_field(weekday_part, now.weekday())
        )

    @staticmethod
    def _match_field(pattern: str, value: int) -> bool:
        if pattern == "*": return True
        if "," in pattern: return any(CronBase._match_field(p, value) for p in pattern.split(","))
        if "/" in pattern:
            r, s = pattern.split("/")
            step = int(s)
            if r in ["*", ""]: return value % step == 0
            if "-" in r:
                start, end = map(int, r.split("-"))
                return start <= value <= end and (value - start) % step == 0
            return value >= int(r) and (value - int(r)) % step == 0
        if "-" in pattern:
            start, end = map(int, pattern.split("-"))
            return start <= value <= end
        return int(pattern) == value
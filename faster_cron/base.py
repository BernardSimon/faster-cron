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

        # 转换星期逻辑:
        # Python weekday: 0(Mon)-6(Sun)
        # 目标习惯: 0或7代表Sun, 1-6代表Mon-Sat
        # 简单转换: (now.weekday() + 1) % 7
        # 这样: Mon=1, Tue=2... Sat=6, Sun=0
        cron_weekday = (now.weekday() + 1) % 7

        try:
            return (
                    CronBase._match_field(sec_part, now.second) and
                    CronBase._match_field(min_part, now.minute) and
                    CronBase._match_field(hour_part, now.hour) and
                    CronBase._match_field(day_part, now.day) and
                    CronBase._match_field(month_part, now.month) and
                    CronBase._match_field(weekday_part, cron_weekday)
            )
        except (ValueError, TypeError):
            # 记录日志或直接返回 False，防止表达式错误导致整个调度线程挂掉
            return False

    @staticmethod
    def _match_field(pattern: str, value: int) -> bool:
        if pattern == "*": return True

        # 处理列表: "1,2,3"
        if "," in pattern:
            return any(CronBase._match_field(p, value) for p in pattern.split(","))

        # 处理步长: "*/5" 或 "10-20/2"
        if "/" in pattern:
            r, s = pattern.split("/")
            step = int(s)
            if r in ["*", ""]: return value % step == 0
            if "-" in r:
                start, end = map(int, r.split("-"))
                return start <= value <= end and (value - start) % step == 0
            return value >= int(r) and (value - int(r)) % step == 0

        # 处理范围: "10-20"
        if "-" in pattern:
            start, end = map(int, pattern.split("-"))
            return start <= value <= end

        # 处理精确数值: "5"
        # 兼容 Cron 的 0 和 7 都代表周日的习惯
        try:
            target_val = int(pattern)
            if target_val == 7: target_val = 0  # 将 7 统一转为 0
            return target_val == value
        except ValueError:
            return False
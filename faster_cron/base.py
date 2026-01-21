import datetime
import logging


class CronBase:
    """提供符合标准 Cron 规范的解析逻辑"""

    @staticmethod
    def is_time_match(expression: str, now: datetime.datetime) -> bool:
        """
        判断当前时间是否匹配 Cron 表达式
        逻辑参考标准 Unix Cron：当日期和星期同时被指定时，采用 OR 关系。
        """
        parts = expression.split()
        if len(parts) == 5:
            # 分 时 日 月 周 -> 补齐秒为 0
            sec_part, min_part, hour_part, day_part, month_part, weekday_part = "0", *parts
        elif len(parts) == 6:
            sec_part, min_part, hour_part, day_part, month_part, weekday_part = parts
        else:
            return False

        # 1. 转换星期逻辑 (Python 0=Mon, 6=Sun -> Cron 0或7=Sun, 1=Mon...)
        # 转换公式：(now.weekday() + 1) % 7 -> 结果 0=Sun, 1=Mon, ..., 6=Sat
        cron_weekday = (now.weekday() + 1) % 7

        try:
            # 2. 基础字段匹配
            sec_match = CronBase._match_field(sec_part, now.second)
            min_match = CronBase._match_field(min_part, now.minute)
            hour_match = CronBase._match_field(hour_part, now.hour)
            month_match = CronBase._match_field(month_part, now.month)

            day_matches = CronBase._match_field(day_part, now.day)
            weekday_matches = CronBase._match_field(weekday_part, cron_weekday)

            # 3. 处理 Day 和 Weekday 的特殊关系 (Standard Cron Logic)
            # 如果两个字段都有限制（不是 *），则为 OR 关系；否则为 AND 关系。
            day_is_star = (day_part == "*")
            weekday_is_star = (weekday_part == "*")

            if not day_is_star and not weekday_is_star:
                day_weekday_ok = (day_matches or weekday_matches)
            else:
                day_weekday_ok = (day_matches and weekday_matches)

            return (
                    sec_match and
                    min_match and
                    hour_match and
                    month_match and
                    day_weekday_ok
            )
        except Exception:
            # 如果表达式解析失败（如格式错误），返回 False 避免程序崩溃
            return False

    @staticmethod
    def _match_field(pattern: str, value: int) -> bool:
        """解析单个 Cron 字段"""
        if pattern == "*":
            return True

        # 处理列表: "1,2,3"
        if "," in pattern:
            return any(CronBase._match_field(p, value) for p in pattern.split(","))

        # 处理步长: "*/5" 或 "1-10/2"
        if "/" in pattern:
            r, s = pattern.split("/")
            step = int(s)
            if r in ["*", ""]:
                return value % step == 0
            if "-" in r:
                start, end = map(int, r.split("-"))
                return start <= value <= end and (value - start) % step == 0
            # 固定点开始的步长: "5/10"
            return value >= int(r) and (value - int(r)) % step == 0

        # 处理范围: "10-20"
        if "-" in pattern:
            start, end = map(int, pattern.split("-"))
            return start <= value <= end

        # 处理精确数值: "5"
        try:
            target_val = int(pattern)
            # 兼容性处理：Cron 中 7 经常作为周日的另一种写法
            if target_val == 7:
                target_val = 0
            return target_val == value
        except ValueError:
            return False
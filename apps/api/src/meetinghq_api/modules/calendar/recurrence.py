"""Deterministic recurrence expansion independent of persistence and HTTP."""

import calendar as month_calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from meetinghq_api.modules.calendar.models import RecurrenceFrequency


@dataclass(frozen=True, slots=True)
class RecurrenceSpec:
    frequency: RecurrenceFrequency
    interval: int = 1
    days_of_week: tuple[int, ...] = ()
    end_date: date | None = None
    occurrence_count: int | None = None
    exception_dates: frozenset[date] = field(default_factory=frozenset)
    skip_holidays: bool = False


class RecurrenceEngine:
    """Expand bounded recurrence rules without database or API dependencies."""

    def expand(
        self,
        start: datetime,
        spec: RecurrenceSpec,
        window_end: datetime,
        holidays: frozenset[date] = frozenset(),
    ) -> list[datetime]:
        if spec.interval < 1:
            raise ValueError("Recurrence interval must be positive")
        results: list[datetime] = []
        candidate = start
        examined = 0
        while candidate <= window_end and examined < 10000:
            examined += 1
            eligible = not spec.days_of_week or candidate.weekday() in spec.days_of_week
            excluded = candidate.date() in spec.exception_dates or (
                spec.skip_holidays and candidate.date() in holidays
            )
            if eligible and not excluded:
                results.append(candidate)
                if spec.occurrence_count and len(results) >= spec.occurrence_count:
                    break
            if spec.end_date and candidate.date() >= spec.end_date:
                break
            candidate = self._next(candidate, spec.frequency, spec.interval)
        return results

    @staticmethod
    def _next(value: datetime, frequency: RecurrenceFrequency, interval: int) -> datetime:
        if frequency in {RecurrenceFrequency.DAILY, RecurrenceFrequency.CUSTOM}:
            return value + timedelta(days=interval)
        if frequency == RecurrenceFrequency.WEEKLY:
            return value + timedelta(days=1 if interval == 1 else 7 * interval)
        if frequency == RecurrenceFrequency.YEARLY:
            try:
                return value.replace(year=value.year + interval)
            except ValueError:
                return value.replace(year=value.year + interval, day=28)
        month_index = value.month - 1 + interval
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, month_calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)

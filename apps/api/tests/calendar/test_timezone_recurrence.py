"""Timezone and recurrence engine tests."""

from datetime import UTC, date, datetime

from meetinghq_api.modules.calendar.models import RecurrenceFrequency
from meetinghq_api.modules.calendar.recurrence import RecurrenceEngine, RecurrenceSpec
from meetinghq_api.modules.calendar.timezone import TimezoneService


def test_timezone_service_handles_daylight_saving() -> None:
    service = TimezoneService()
    winter = service.to_utc(datetime(2026, 1, 15, 9), "America/Chicago")
    summer = service.to_utc(datetime(2026, 7, 15, 9), "America/Chicago")
    assert winter.hour == 15
    assert summer.hour == 14
    assert winter.tzinfo == UTC


def test_recurrence_skips_holidays_and_exceptions() -> None:
    start = datetime(2026, 8, 3, 9, tzinfo=UTC)
    values = RecurrenceEngine().expand(
        start,
        RecurrenceSpec(
            frequency=RecurrenceFrequency.DAILY,
            occurrence_count=3,
            exception_dates=frozenset({date(2026, 8, 4)}),
            skip_holidays=True,
        ),
        datetime(2026, 8, 10, tzinfo=UTC),
        frozenset({date(2026, 8, 5)}),
    )
    assert [item.date() for item in values] == [
        date(2026, 8, 3),
        date(2026, 8, 6),
        date(2026, 8, 7),
    ]

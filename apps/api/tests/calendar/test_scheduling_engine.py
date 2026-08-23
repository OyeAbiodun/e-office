"""Pure scheduling engine tests."""

from datetime import UTC, datetime, time, timedelta

from meetinghq_api.modules.calendar.scheduling import (
    SchedulingEngine,
    SchedulingPolicy,
    TimeRange,
)


def moment(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 3, hour, minute, tzinfo=UTC)


def test_conflict_and_buffer_detection() -> None:
    engine = SchedulingEngine()
    result = engine.validate(
        TimeRange(moment(10), moment(11)),
        [TimeRange(moment(10, 30), moment(11, 30))],
    )
    assert not result.valid
    assert len(result.conflicts) == 1

    buffered = engine.validate(
        TimeRange(moment(9), moment(10)),
        [TimeRange(moment(10, 10), moment(11))],
        SchedulingPolicy(buffer_after=timedelta(minutes=15)),
    )
    assert not buffered.valid


def test_suggestions_respect_working_hours_and_busy_ranges() -> None:
    slots = SchedulingEngine().suggest(
        TimeRange(moment(8), moment(12)),
        timedelta(minutes=30),
        [TimeRange(moment(9), moment(10))],
        (time(8), time(18)),
        limit=4,
        step=timedelta(minutes=30),
    )
    assert [slot.start.hour for slot in slots] == [8, 8, 10, 10]

"""Generic deterministic scheduling engine for people and resources."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta


@dataclass(frozen=True, slots=True)
class TimeRange:
    start: datetime
    end: datetime

    def overlaps(self, other: "TimeRange", buffer: timedelta = timedelta()) -> bool:
        return self.start < other.end + buffer and self.end > other.start - buffer


@dataclass(frozen=True, slots=True)
class SchedulingPolicy:
    minimum_duration: timedelta = timedelta(minutes=15)
    maximum_duration: timedelta = timedelta(hours=12)
    buffer_before: timedelta = timedelta()
    buffer_after: timedelta = timedelta()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    conflicts: tuple[TimeRange, ...] = ()
    reasons: tuple[str, ...] = ()


class SchedulingEngine:
    """Pure scheduling decisions reusable by future AI and meeting modules."""

    def validate(
        self,
        candidate: TimeRange,
        busy: list[TimeRange],
        policy: SchedulingPolicy | None = None,
        working_hours: tuple[time, time] | None = None,
    ) -> ValidationResult:
        policy = policy or SchedulingPolicy()
        reasons: list[str] = []
        if candidate.end <= candidate.start:
            reasons.append("End time must be after start time")
        duration = candidate.end - candidate.start
        if duration < policy.minimum_duration or duration > policy.maximum_duration:
            reasons.append("Duration is outside the allowed range")
        if working_hours and (
            candidate.start.timetz().replace(tzinfo=None) < working_hours[0]
            or candidate.end.timetz().replace(tzinfo=None) > working_hours[1]
        ):
            reasons.append("Time is outside working hours")
        buffer = max(policy.buffer_before, policy.buffer_after)
        conflicts = tuple(block for block in busy if candidate.overlaps(block, buffer))
        if conflicts:
            reasons.append("Time conflicts with an existing booking")
        return ValidationResult(not reasons, conflicts, tuple(reasons))

    def suggest(
        self,
        search_window: TimeRange,
        duration: timedelta,
        busy: list[TimeRange],
        working_hours: tuple[time, time],
        limit: int = 10,
        step: timedelta = timedelta(minutes=15),
        policy: SchedulingPolicy | None = None,
    ) -> list[TimeRange]:
        policy = policy or SchedulingPolicy()
        suggestions: list[TimeRange] = []
        cursor = search_window.start
        while cursor + duration <= search_window.end and len(suggestions) < limit:
            candidate = TimeRange(cursor, cursor + duration)
            if self.validate(candidate, busy, policy, working_hours).valid:
                suggestions.append(candidate)
            cursor += step
        return suggestions

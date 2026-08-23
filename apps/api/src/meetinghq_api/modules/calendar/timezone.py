"""Centralized, DST-aware timezone service."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from meetinghq_api.shared.exceptions import ValidationError


class TimezoneService:
    @staticmethod
    def validate(timezone: str) -> str:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as error:
            raise ValidationError(f"Unknown timezone: {timezone}") from error
        return timezone

    def to_utc(self, value: datetime, timezone: str) -> datetime:
        zone = ZoneInfo(self.validate(timezone))
        localized = value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)
        return localized.astimezone(UTC)

    def from_utc(self, value: datetime, timezone: str) -> datetime:
        zone = ZoneInfo(self.validate(timezone))
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.astimezone(zone)

    def convert(self, value: datetime, source: str, destination: str) -> datetime:
        return self.from_utc(self.to_utc(value, source), destination)

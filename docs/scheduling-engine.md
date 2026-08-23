# Scheduling Engine

`SchedulingEngine` is a pure, deterministic service with no HTTP, SQLAlchemy, UI, or
provider dependencies. It accepts generic time ranges, busy ranges, working hours,
duration constraints, and buffers. The same contract schedules people and resources and
can be consumed by a future AI assistant without modification.

Conflict detection uses half-open ranges: an appointment ending exactly when another
starts does not conflict unless a buffer requires separation. Suggestions scan a bounded
window at a deterministic interval and return the first valid slots.

`SchedulingService` verifies tenant ownership, loads event, busy-block, and reservation
ranges, normalizes time through `TimezoneService`, and delegates to the pure engine.

`RecurrenceEngine` separately expands daily, weekly, monthly, yearly, and custom rules
with bounded windows, occurrence counts, end dates, exception dates, and holiday skipping.

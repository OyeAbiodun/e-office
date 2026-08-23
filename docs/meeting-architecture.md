# Meeting Architecture

`Meeting` is the aggregate root for planning, attendance, agendas, notes, decisions, and action items. The module follows the platform's API → service → repository → persistence boundary.

Scheduling remains owned by Calendar. Meeting creation and rescheduling call `SchedulingService` for availability, calendar conflicts, resource conflicts, timezone normalization, and business-hour policy. Calendar events are created through `CalendarService`; meetings do not reproduce scheduling rules.

All mutations write an immutable audit record and a transactional domain event. Events are persisted internally and projected to the activity stream. No external broker or cross-module direct business calls are introduced.

Action items intentionally carry portable assignment, priority, due-date, status, and completion fields so they can become platform tasks later. Template agendas and agenda rows remain structured for future organization customization and AI consumers.

Tenant boundaries are enforced by organization-scoped repositories and authenticated RBAC dependencies. Meeting responses never resolve records across organizations.

## Aggregate data

- `meetings`: lifecycle, scheduling reference, organizer, workspace, location, and visibility.
- `meeting_attendees`: invitee role, RSVP, join, and leave state.
- `meeting_agendas`: ordered, timed, presenter-owned topics.
- `meeting_decisions`: durable structured outcomes.
- `meeting_action_items`: assignable follow-up work.
- `meeting_notes`: authored collaboration notes.
- `meeting_templates`: organization-owned defaults and structured agendas.

## Domain events

The module publishes `MeetingCreated`, `MeetingUpdated`, `MeetingCancelled`, `MeetingRescheduled`, `MeetingStarted`, `MeetingCompleted`, `AttendeeInvited`, `AttendeeAccepted`, `AttendeeDeclined`, `AgendaUpdated`, `DecisionCreated`, and `ActionItemCreated`.

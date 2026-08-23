# Meeting API

All endpoints are under `/api/v1`, require a bearer token, use organization-scoped RBAC, and return the standard MeetingHQ response envelope.

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/meetings` | List or schedule meetings |
| GET, PATCH | `/meetings/{id}` | Read or edit a meeting |
| POST | `/meetings/{id}/transition` | Start, complete, confirm, cancel, or archive |
| POST | `/meetings/{id}/reschedule` | Scheduling-validated reschedule |
| POST | `/meetings/{id}/duplicate` | Create a copy one week later |
| GET | `/meetings/{id}/history` | Domain-event history |
| POST | `/meetings/{id}/attendees` | Invite an attendee |
| PUT | `/meetings/{id}/rsvp` | Accept, decline, tentatively accept, join, or leave |
| POST, DELETE | `/meetings/{id}/agenda` | Manage agenda items |
| PUT | `/meetings/{id}/agenda/order` | Persist drag-and-drop ordering |
| POST, DELETE | `/meetings/{id}/decisions` | Manage decisions |
| POST, DELETE | `/meetings/{id}/actions` | Manage action items |
| POST, DELETE | `/meetings/{id}/notes` | Manage notes |
| GET | `/meetings/dashboard` | Today, upcoming, recent, RSVP, and action summaries |
| GET, POST | `/meeting-templates` | List and create organization templates |

Create requests include `workspace_id`, title, start/end datetimes, timezone, optional attendees, room, template, location, visibility, and meeting URL. The server creates or selects the workspace meeting calendar and validates the requested slot.

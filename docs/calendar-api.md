# Calendar API

Create a calendar:

```http
POST /api/v1/calendars
Authorization: Bearer <token>
Content-Type: application/json

{"name":"Operations","type":"workspace","workspace_id":"<uuid>","timezone":"America/Chicago"}
```

Validate a proposed time:

```http
POST /api/v1/scheduling/validate
Authorization: Bearer <token>
Content-Type: application/json

{"calendar_ids":["<uuid>"],"start_datetime":"2026-08-03T09:00:00","end_datetime":"2026-08-03T09:30:00","timezone":"America/Chicago","buffer_minutes":15}
```

Validation and suggestions never mutate state. Reservations use the same deterministic
resource conflict rules.

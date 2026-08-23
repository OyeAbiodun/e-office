# Meeting Lifecycle

MeetingHQ validates every state change:

```text
Draft → Scheduled → Confirmed → In Progress → Completed → Archived
  └────────────── cancellation from any active state ─────→ Cancelled → Archived
```

- **Draft** is planning state before a calendar commitment.
- **Scheduled** has a validated calendar event.
- **Confirmed** indicates organizer confirmation.
- **In progress** enables live attendance and collaboration capture.
- **Completed** records a finished meeting and its outcomes.
- **Cancelled** cancels the linked calendar event.
- **Archived** is terminal historical state.

Invalid transitions return a validation error and do not mutate the aggregate. Completed and cancelled meetings can only be archived. Archived meetings cannot transition.

Rescheduling is unavailable after cancellation, completion, or archival. A reschedule cancels the old calendar event, validates the replacement through the Scheduling Engine, creates the replacement event, and publishes `MeetingRescheduled`.

# Calendar Platform

The calendar module is a tenant-scoped platform service for personal, team, workspace,
organization, and resource calendars. It owns events, availability rules, holidays, busy
blocks, resource calendars, and reservations.

All timestamps are normalized to UTC before persistence. The originating IANA timezone is
retained for display and recurrence semantics. Business modules must use
`TimezoneService`; direct timezone conversion outside that boundary is prohibited.

Calendar mutations publish durable domain events and security-relevant operations append
audit records. External synchronization is outside Milestone 04; Google, Outlook, Apple,
and ICS contracts are provider ports only.

The `/api/v1` surface includes calendars and events, availability, busy blocks, holidays,
resources, reservations, scheduling validation, and slot suggestions. Every response
uses the shared response envelope and protected operations use centralized RBAC.

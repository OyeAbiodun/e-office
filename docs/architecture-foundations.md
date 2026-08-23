# Architecture Foundations

MeetingHQ modules are organized into API, application service, domain contract, and
persistence adapter layers. Route handlers validate transport concerns and call services;
services own business decisions; repositories isolate SQLAlchemy queries.

## Domain events

Business modules publish immutable `DomainEvent` facts through the
`DomainEventPublisher` port. The current transactional adapter persists every event in
`domain_events` and projects user-facing activity in the same database transaction.
Future Notifications, AI, Reports, Billing, and Analytics subscribers can be registered
at the composition boundary without importing one business module into another.

## API contracts and pagination

Every JSON endpoint returns `success`, `message`, `data`, and `meta`. Failures additionally
return a safe `error` object with a stable code. OpenAPI and documentation resources remain
unwrapped.

The shared pagination package supports offset pages for administration views and opaque,
compound cursor pages for high-volume timelines. Callers cannot mix both strategies.

## Deletion and audit

Entities requiring deletion use `SoftDeleteMixin`, which records `deleted_at` and
`deleted_by` and supplies `restore()`. Permanent deletion is not a default business action.

`audit_logs` is an append-only security/compliance record and has no update or delete API.
It is intentionally separate from `activity_events`, which powers timelines and dashboard
experiences.

## Configuration

`ConfigurationRegistry` is the single lookup boundary for runtime settings. Environment
settings remain safe defaults; persisted, namespaced entries allow a future Super Admin
module to manage feature flags, providers, limits, and branding without scattered reads.

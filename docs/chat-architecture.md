# Chat Architecture

Chat is a MeetingHQ platform service, not an isolated messenger. Conversations are tenant-scoped aggregates that support direct messages, private groups, team channels, workspace channels, and organization announcements.

Three responsibilities remain independent:

- **Message storage** uses `ChatRepository` and compound `(conversation_id, created_at, id)` indexes with opaque cursor pagination.
- **Message delivery** uses the `MessageDelivery` port. REST and WebSocket flows currently use the in-process realtime hub; a distributed transport can replace it without changing chat business logic.
- **WebSocket transport** authenticates, subscribes, and dispatches commands to application services. It contains no persistence rules.

`ChatThread` is a first-class projection with a root message, reply count, latest reply, and update timestamp. Replies remain ordinary messages connected through `parent_message_id`, keeping one scalable message store.

Attachment records contain provider-owned storage keys and metadata only. Uploads remain outside this milestone and will use the existing `StorageProvider` abstraction.

Every material action produces an internal domain event. Compliance-relevant changes also create immutable audit records. The message body remains rich-text source suitable for future summaries without schema changes.

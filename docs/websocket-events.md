# WebSocket Events

## Client commands

| Event | Data |
|---|---|
| `message.send` | `body`, `message_type`, optional `parent_message_id`, attachment metadata |
| `message.read` | `message_id` |
| `typing` | `active: boolean` |

## Server events

| Event | Purpose |
|---|---|
| `message.ack` | Confirms durable message identity |
| `message.new` | New root message or thread reply |
| `message.edited` | Replaces rendered message content |
| `message.deleted` | Marks a message deleted |
| `message.read` | Read receipt update |
| `message.pinned` | Pinned-message update |
| `reaction.added`, `reaction.removed` | Extensible emoji reaction updates |
| `typing` | Ephemeral typing state |
| `presence.changed` | Online, away, busy, in-meeting, or offline state |

Clients should reconnect with bounded exponential backoff and reload messages with the REST cursor endpoint after reconnection. This reconciles any events missed while disconnected.

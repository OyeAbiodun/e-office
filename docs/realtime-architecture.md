# Realtime Architecture

Clients connect to:

```text
ws://HOST/api/v1/chat/ws/{conversation_id}?token={access_token}
```

The server validates the access token and conversation membership before accepting the socket. A connection marks the member online; disconnect marks the member offline. Explicit away, busy, and in-meeting states are available through the Presence API.

The current in-process hub maintains per-user and per-conversation subscriptions. Reconnection creates a new subscription without relying on old socket state. Durable messages, read receipts, reactions, threads, and pins remain in PostgreSQL; WebSockets are delivery acceleration rather than the source of truth.

For horizontal scaling, the `MessageDelivery` port can be backed by Redis Pub/Sub or a durable event stream. The application service and WebSocket command contracts remain unchanged.

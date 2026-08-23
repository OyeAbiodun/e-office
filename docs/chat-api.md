# Chat API

All REST endpoints are under `/api/v1`, require bearer authentication, enforce tenant membership and RBAC, and use the standard response envelope.

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/conversations` | List or create conversations and channels |
| GET, PATCH | `/conversations/{id}` | Conversation details and settings |
| POST | `/conversations/{id}/archive` | Archive a conversation |
| POST, DELETE | `/conversations/{id}/members` | Member management |
| GET, POST | `/conversations/{id}/messages` | Cursor history or send |
| PATCH, DELETE | `/messages/{id}` | Edit or soft-delete a message |
| POST, DELETE | `/messages/{id}/reactions` | Add or remove reactions |
| POST | `/messages/{id}/pin` | Pin a message |
| GET | `/conversations/{id}/pins` | Pinned-message directory |
| PUT | `/conversations/{id}/read` | Read receipt |
| GET, PUT | `/presence` | Organization presence or current state |
| GET | `/chat/dashboard` | Unread, recent, channel, and presence widgets |

Thread replies use `parent_message_id`. Supplying it to the message-list endpoint opens the thread timeline.

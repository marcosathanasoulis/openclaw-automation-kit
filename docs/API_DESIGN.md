# API Design (Planned)

## Endpoints
- `POST /runs`
- `GET /runs/{id}`
- `POST /schedules`
- `GET /scripts`
- `POST /hooks`

## Delivery model
Core engine emits normalized results. Connectors (WhatsApp/iMessage/Slack/etc.) consume webhook payloads.

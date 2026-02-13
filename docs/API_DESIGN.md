# API Design (Planned)

## Endpoints
- `POST /runs`
- `GET /runs/{id}`
- `POST /schedules`
- `GET /scripts`
- `POST /hooks`
- `POST /runs/{id}/resume` (for CAPTCHA/2FA human-loop responses)
- `GET /queue` (queued/running visibility)

## Delivery model
Core engine emits normalized results. Connectors (WhatsApp/iMessage/Slack/etc.) consume webhook payloads.

## Scheduling policy
- Queue-first execution
- Lock-based resource arbitration
- Default concurrency: 1 global run at a time

## Human-loop events
Recommended event types:
- `SECOND_FACTOR_REQUIRED`
- `CAPTCHA_REQUIRED`
- `RUN_COMPLETED`
- `RUN_FAILED`

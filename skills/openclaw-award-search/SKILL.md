---
name: openclaw-award-search
description: Use this skill for airline award-search tasks (United/Singapore/ANA) with mileage caps, route/date windows, and cabin filters. Requires user-owned credentials and 2FA challenge handling.
---

# OpenClaw Award Search

Use this skill when users ask for mileage-based award flight searches.

Examples:
- "Find business award seats from SFO to AMS or LIS under 120k miles in the next 30 days."
- "Search ANA economy from SFO to HND for 2 travelers."

## Preconditions

- Local repo installed with dependencies (`pip install -e .`).
- Credentials available in user-managed secret store (`credential_refs` only).
- Human-loop channel available for 2FA/CAPTCHA replies.

## Command to run

Use the built-in plain-English path:

```bash
python skills/openclaw-award-search/scripts/run_query.py --query "<user request>"
```

If credentials are needed, include refs:

```bash
python skills/openclaw-award-search/scripts/run_query.py \
  --query "<user request>" \
  --credential-refs '{"airline_username":"openclaw/united/username","airline_password":"openclaw/united/password"}'
```

Optional iMessage notification via BlueBubbles (dry run by default):

```bash
python skills/openclaw-award-search/scripts/run_query.py \
  --query "<user request>" \
  --credential-refs '{"airline_username":"openclaw/united/username","airline_password":"openclaw/united/password"}' \
  --notify-imessage "+14152268266"
```

Actually send:

```bash
python skills/openclaw-award-search/scripts/run_query.py \
  --query "<user request>" \
  --credential-refs '{"airline_username":"openclaw/united/username","airline_password":"openclaw/united/password"}' \
  --notify-imessage "+14152268266" \
  --send-notification
```

## Safety

- Never request or expose raw passwords.
- Use credential refs only.
- Require human confirmation at 2FA/CAPTCHA checkpoints.

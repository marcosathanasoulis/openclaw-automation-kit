# Starter Examples (Fast Onboarding)

These examples are meant to get a new user running quickly, even with manual credential setup and manual 2FA/CAPTCHA response.

## Example set

1. `united.award_search`
- Award travel scan using miles
- Best for learning date-window extraction

2. `singapore.award_search`
- Alternate airline flow with dynamic form behavior
- Good stress test for waits/selectors

3. `ana.award_search`
- Additional airline pattern and credential references

4. `github.signin_check` (added for onboarding)
- Login/2FA checkpoint demo pattern
- Good first script for human-loop wiring

## Recommended first run

Use plain English:

```bash
python -m openclaw_automation.cli run-query \
  --query "Search United award travel economy from SFO to SIN for 2 travelers in next 30 days under 120k miles" \
  --credential-refs '{"airline_username":"openclaw/united/username","airline_password":"openclaw/united/password"}'
```

Then wire messaging:
1. implement challenge webhook receiver
2. send challenge to iMessage or WhatsApp
3. submit user response to resume endpoint

See:
- `docs/MESSAGING_HUMAN_LOOP_SETUP.md`
- `docs/CAPTCHA_HUMAN_LOOP.md`

## What to expect today

Current runners in this repo are contract-valid starter implementations.  
They demonstrate:
- input contracts
- credential reference handling
- normalized output shape
- human-loop event patterns

For live production scraping, replace the placeholder extraction code with your OpenClaw browser steps.


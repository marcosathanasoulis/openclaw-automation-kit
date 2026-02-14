# site_text_watch

Public-site text monitor for required/forbidden phrases.

## Run

```bash
python -m openclaw_automation.cli run \
  --script-dir library/site_text_watch \
  --input '{"url":"https://status.openai.com","must_include":["status"],"must_not_include":["maintenance window"],"case_sensitive":false}'
```

## Notes

- No login/credentials required.
- Useful for quick monitoring checks and alert triggers.
- If a site presents anti-bot challenges, switch to a BrowserAgent script and human-loop flow.

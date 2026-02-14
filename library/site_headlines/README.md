# site_headlines

Public-site automation to fetch a URL and extract top heading lines (`h1/h2/h3`).

## Run

```bash
python -m openclaw_automation.cli run \
  --script-dir library/site_headlines \
  --input '{"url":"https://www.yahoo.com","max_items":8}'
```

## Notes

- No login/credentials required.
- If a site serves bot checks/challenges, this script returns a fetch error or empty headings.
- For challenge screenshots + human-loop handling, use BrowserAgent-driven scripts plus the messaging/webhook pattern.

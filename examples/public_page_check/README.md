# web.public_page_check

Zero-credential quickstart that fetches a public URL and returns:
- page title
- keyword count
- short highlights

## Run

```bash
python -m openclaw_automation.cli run \
  --script-dir examples/public_page_check \
  --input '{"url":"https://www.yahoo.com","keyword":"news"}'
```

## Notes

- This example is intentionally simple and works without browser login state.
- Use it to confirm install/CLI/network are healthy before trying credentialed scripts.

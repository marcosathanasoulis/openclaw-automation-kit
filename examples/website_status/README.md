# Website Status Check

This automation checks if a given website is online and responding with a 200 OK status.

## Input

- `url`: The URL of the website to check.

## Output

- `url`: The URL that was checked.
- `status`: "Online" if the website returned a 200 OK, "Offline" otherwise.
- `status_code`: The HTTP status code received.

## How to run

```bash
python -m openclaw_automation.cli run 
  --script-dir examples/website_status 
  --input '{"url":"https://www.google.com"}'
```

# News Headlines

This automation scrapes the top headlines from a news website.

## Input

- `url`: The URL of the news website to scrape.

## Output

- `headlines`: A list of headlines, each with a `title` and a `link`.

## How to run

```bash
python -m openclaw_automation.cli run \
  --script-dir examples/news_headlines \
  --input '{"url":"https://www.bbc.com/news"}'
```

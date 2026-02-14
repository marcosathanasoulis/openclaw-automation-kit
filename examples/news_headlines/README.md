# News Headlines

This automation gets the top headlines from a news source using the News API.

**This automation requires an API key from [News API](https://newsapi.org/). You will need to sign up for a free developer account to get one.**

## Input

- `source`: The news source to get headlines from (e.g., `bbc-news`, `cnn`). You can find a list of sources [here](https://newsapi.org/sources).
- `apiKey`: Your News API key.

## Output

- `headlines`: A list of headlines, each with a `title` and a `link`.

## How to run

You need to provide your News API key in the input.

```bash
python -m openclaw_automation.cli run \
  --script-dir examples/news_headlines \
  --input '{"source":"bbc-news", "apiKey": "YOUR_NEWS_API_KEY"}'
```

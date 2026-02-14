# Weather Check

This automation gets the current weather conditions for a specified location from a public weather website.

## Input

- `location`: The city or zip code for which to get weather information.

## Output

- `location`: The name of the location.
- `temperature`: The current temperature.
- `conditions`: A description of the current weather conditions.
- `feels_like`: The "feels like" temperature.

## How to run

```bash
python -m openclaw_automation.cli run \
  --script-dir examples/weather_check \
  --input '{"location":"New York"}'
```

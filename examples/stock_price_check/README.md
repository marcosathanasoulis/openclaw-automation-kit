# Stock Price Check

This automation checks the price of a stock using Yahoo Finance.

## Input

- `ticker`: The stock ticker symbol (e.g., `AAPL`, `GOOGL`).

## Output

- `ticker`: The stock ticker symbol.
- `price`: The current price of the stock.
- `change`: The change in the stock price.
- `change_percent`: The percentage change in the stock price.

## How to run

```bash
python -m openclaw_automation.cli run 
  --script-dir examples/stock_price_check 
  --input '{"ticker":"AAPL"}'
```

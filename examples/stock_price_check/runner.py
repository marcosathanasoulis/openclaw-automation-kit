
import json
import yfinance as yf

def run(context, inputs):
    """
    This is the entrypoint for the automation.
    """
    try:
        ticker_symbol = inputs['ticker']

        stock = yf.Ticker(ticker_symbol)
        info = stock.info

        price = info.get('currentPrice')
        if price is None:
            # Fallback for pre-market, post-market, etc.
            price = info.get('regularMarketPrice')

        if price is None:
            # If still not found, try to get the last closing price
            hist = stock.history(period="1d")
            if not hist.empty:
                price = hist['Close'][0]

        if price is None:
            raise ValueError("Could not determine the stock price.")
            
        previous_close = info.get('previousClose')
        change = round(price - previous_close, 2)
        change_percent = round((change / previous_close) * 100, 2)


        result = {
            "ticker": ticker_symbol,
            "price": price,
            "change": f"{change:+.2f}",
            "change_percent": f"{change_percent:+.2f}%"
        }
        return result

    except Exception as e:
        return {"error": str(e)}

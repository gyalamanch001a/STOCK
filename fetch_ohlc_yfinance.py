import yfinance as yf
from typing import Optional, Dict

def fetch_ohlc_yfinance(symbol: str, update_db: bool = True) -> Optional[Dict[str, float]]:
    """
    Fetch today's and previous day's OHLC data for a given symbol using yfinance.
    If update_db is True, update nasdaq_summary.csv with the fetched data.
    Returns a dict with keys: Today High, Today Low, Today Open, Today Close, Previous High, Previous Low, Previous Open, Previous Close, Date
    """
    import pandas as pd
    import os
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        log_path = os.path.join(os.path.dirname(__file__), "ohlc_api_debug.log")
        with open(log_path, "a") as logf:
            logf.write(f"Symbol: {symbol}\nHistory shape: {hist.shape}\nHistory: {hist}\n")
        if hist.shape[0] < 2:
            with open(log_path, "a") as logf:
                logf.write(f"Not enough data for {symbol}\n\n")
            return None
        today = hist.iloc[-1]
        prev = hist.iloc[-2]
        def fmt(val):
            return f"${val:,.2f}" if val is not None else ""
        ohlc_data = {
            'Today High': fmt(today['High']),
            'Today Low': fmt(today['Low']),
            'Today Open': fmt(today['Open']),
            'Today Close': fmt(today['Close']),
            'Previous High': fmt(prev['High']),
            'Previous Low': fmt(prev['Low']),
            'Previous Open': fmt(prev['Open']),
            'Previous Close': fmt(prev['Close']),
            'Date': str(today.name.date())
        }
        with open(log_path, "a") as logf:
            logf.write(f"OHLC Data: {ohlc_data}\n\n")
        if update_db:
            import time
            csv_path = os.path.join(os.path.dirname(__file__), "nasdaq_summary.csv")
            for attempt in range(5):
                try:
                    if os.path.exists(csv_path):
                        df = pd.read_csv(csv_path)
                        if "Symbol" in df.columns and symbol in df["Symbol"].values:
                            for k, v in ohlc_data.items():
                                df.loc[df["Symbol"] == symbol, k] = v
                        else:
                            row = {"Symbol": symbol}
                            row.update(ohlc_data)
                            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                        df.to_csv(csv_path, index=False)
                    else:
                        row = {"Symbol": symbol}
                        row.update(ohlc_data)
                        df = pd.DataFrame([row])
                        df.to_csv(csv_path, index=False)
                    break
                except PermissionError as e:
                    with open(log_path, "a") as logf:
                        logf.write(f"PermissionError on nasdaq_summary.csv: {e}\nRetrying...\n")
                    time.sleep(1)
                except Exception as e:
                    with open(log_path, "a") as logf:
                        logf.write(f"Other error on nasdaq_summary.csv: {e}\n")
                    break
        return ohlc_data
    except Exception as e:
        with open(log_path, "a") as logf:
            logf.write(f"Error fetching OHLC from yfinance for {symbol}: {e}\n\n")
        print(f"Error fetching OHLC from yfinance for {symbol}: {e}")
        return None

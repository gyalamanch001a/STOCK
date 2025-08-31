import requests
import pandas as pd
import time

# Input and output CSV files
INPUT_FILE = "tickers.csv"
OUTPUT_FILE = "nasdaq_summary.csv"

# Headers required by Nasdaq API (otherwise you'll often get blocked)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}

def fetch_summary(symbol: str):
    """
    Fetch summary data for a stock symbol from Nasdaq API.
    Returns a dict of useful fields or None if error.
    """
    url = f"https://api.nasdaq.com/api/quote/{symbol}/summary?assetclass=stocks"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            print(f"[{symbol}] HTTP {resp.status_code}")
            return None

        data = resp.json().get("data", {})
        summary = data.get("summaryData", {})

        # Flatten useful fields
        row = {"Symbol": symbol}
        for key, value in summary.items():
            row[key] = value.get("value") if isinstance(value, dict) else value

        return row
    except Exception as e:
        print(f"[{symbol}] Error: {e}")
        return None


def main():
    # Read tickers from CSV
    tickers_df = pd.read_csv(INPUT_FILE)

    results = []
    for symbol in tickers_df["Symbol"]:
        print(f"Fetching {symbol} ...")
        row = fetch_summary(symbol)
        if row:
            results.append(row)
        time.sleep(0.5)  # polite delay to avoid rate limits

    # Convert to DataFrame and save
    if results:
        out_df = pd.DataFrame(results)
        out_df.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Saved {len(out_df)} rows to {OUTPUT_FILE}")
    else:
        print("\n⚠️ No data fetched.")


if __name__ == "__main__":
    main()

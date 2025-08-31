from flask import Flask, render_template_string, request
import pandas as pd
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) )
from fetch_ohlc_yfinance import fetch_ohlc_yfinance

app = Flask(__name__)

CSV_FILE = "nasdaq_summary.csv"

from stock import fetch_summary

def fetch_yahoo_finance(symbol):
    # Use yfinance-based function only
    return fetch_ohlc_yfinance(symbol)

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nasdaq Summary Viewer</title>
    <style>
        body { font-family: Arial, sans-serif; }
        .container { display: flex; height: 90vh; }
        .tickers { width: 30%; border-right: 1px solid #ccc; overflow-y: auto; }
        .details { width: 70%; padding: 20px; }
        .ticker-item { padding: 10px; cursor: pointer; border-bottom: 1px solid #eee; }
        .ticker-item.selected { background: #e0e0ff; }
        .key { font-weight: bold; }
        .search-box { width: 90%; margin: 10px; padding: 8px; font-size: 1em; }
        .search-form { text-align: center; }
    </style>
    <script>
        function selectTicker(symbol) {
            window.location.href = '/?symbol=' + symbol;
        }
    </script>
</head>
<body>
    <h2>Nasdaq Summary Viewer</h2>
    <div class="container">
        <div class="tickers">
            <form class="search-form" method="get" action="/">
                <input class="search-box" type="text" name="search" placeholder="Search ticker..." value="{{ search or '' }}" />
                <button type="submit">Search</button>
            </form>
            {% for ticker in tickers %}
                <div class="ticker-item {% if ticker == selected %}selected{% endif %}" onclick="selectTicker('{{ ticker }}')">
                    {{ ticker }}
                </div>
            {% endfor %}
        </div>
        <div class="details">
            {% if details %}
                <h3>Details for {{ selected }}</h3>
                <form method="post" action="/fetch_ohlc">
                    <input type="hidden" name="symbol" value="{{ selected }}" />
                    <button type="submit">Fetch OHLC from Yahoo Finance</button>
                </form>
                <table style="border-collapse:collapse; width:60%; margin-bottom:20px;">
                    <tr style="background:#f0f0f0;"><th colspan="2">Key OHLC Data</th></tr>
                    {% for key in ["Today High", "Today Low", "Today Open", "Today Close", "Previous High", "Previous Low", "Previous Open", "Previous Close", "Date"] %}
                        {% if details[key] is not none and details[key] != '' %}
                            <tr><td class="key">{{ key }}</td><td>{{ details[key] }}</td></tr>
                        {% endif %}
                    {% endfor %}
                </table>
                <table>
                    {% for key, value in details.items() %}
                        {% if key not in ["Today High", "Today Low", "Today Open", "Today Close", "Previous High", "Previous Low", "Previous Open", "Previous Close", "Date"] %}
                            <tr><td class="key">{{ key }}</td><td>{{ value }}</td></tr>
                        {% endif %}
                    {% endfor %}
                </table>
            {% else %}
                <p>Select a ticker to view details.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''

@app.route("/")
def index():
    if not os.path.exists(CSV_FILE):
        return f"CSV file '{CSV_FILE}' not found. Please run stock.py first."
    df = pd.read_csv(CSV_FILE)
    tickers = df["Symbol"].tolist() if "Symbol" in df.columns else []
    search = request.args.get("search", "").strip().upper()
    selected = request.args.get("symbol", None)
    details = None

    def extract_key_data(row):
        key_data = {}
        for field in ["Today High", "Today Low", "Today Open", "Today Close", "Previous High", "Previous Low", "Previous Open", "Previous Close", "Date"]:
            key_data[field] = row.get(field)
        for k, v in row.items():
            if k not in key_data:
                key_data[k] = v
        return key_data

    # If search is present, always check/fetch Yahoo Finance data
    if search:
        if search not in tickers:
            new_row = fetch_summary(search) or {"Symbol": search}
            yahoo_data = fetch_yahoo_finance(search)
            if yahoo_data:
                new_row.update(yahoo_data)
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(CSV_FILE, index=False)
            # Reload DataFrame from CSV to ensure latest data
            df = pd.read_csv(CSV_FILE)
            tickers = df["Symbol"].tolist() if "Symbol" in df.columns else []
            selected = search
        else:
            # For existing ticker, update missing OHLC values
            details_row = df[df["Symbol"] == search]
            if not details_row.empty:
                row_dict = details_row.iloc[0].to_dict()
                missing_fields = [f for f in ["Today High", "Today Low", "Today Open", "Today Close", "Previous High", "Previous Low", "Previous Open", "Previous Close"] if row_dict.get(f) in [None, '', 'None'] or pd.isna(row_dict.get(f))]
                if missing_fields:
                    yahoo_data = fetch_yahoo_finance(search)
                    if yahoo_data:
                        for k, v in yahoo_data.items():
                            if v not in [None, '', 'None']:
                                df.loc[df["Symbol"] == search, k] = v
                        df.to_csv(CSV_FILE, index=False)
                        # Reload DataFrame from CSV to ensure latest data
                        df = pd.read_csv(CSV_FILE)
                    else:
                        details = {"Error": f"Yahoo Finance API did not return valid data for {search}. See yahoo_api_debug.log."}
            selected = search

    # If selected ticker is present, show details
    if selected and selected in tickers:
        details_row = df[df["Symbol"] == selected]
        if not details_row.empty:
            details = extract_key_data(details_row.iloc[0].to_dict())

    return render_template_string(TEMPLATE, tickers=tickers, selected=selected, details=details, search=search)

@app.route("/fetch_ohlc", methods=["POST"])
def fetch_ohlc():
    symbol = request.form.get("symbol")
    if not symbol:
        return "No symbol provided.", 400
    df = pd.read_csv(CSV_FILE)
    details_row = df[df["Symbol"] == symbol]
    if not details_row.empty:
        yahoo_data = fetch_yahoo_finance(symbol)
        if yahoo_data:
            for k, v in yahoo_data.items():
                if v not in [None, '', 'None']:
                    df.loc[df["Symbol"] == symbol, k] = v
            df.to_csv(CSV_FILE, index=False)
    # Reload DataFrame and render updated page
    df = pd.read_csv(CSV_FILE)
    tickers = df["Symbol"].tolist() if "Symbol" in df.columns else []
    details_row = df[df["Symbol"] == symbol]
    details = None
    if not details_row.empty:
        def extract_key_data(row):
            key_data = {}
            for field in ["Today High", "Today Low", "Today Open", "Today Close", "Previous High", "Previous Low", "Previous Open", "Previous Close", "Date"]:
                key_data[field] = row.get(field)
            for k, v in row.items():
                if k not in key_data:
                    key_data[k] = v
            return key_data
        details = extract_key_data(details_row.iloc[0].to_dict())
    return render_template_string(TEMPLATE, tickers=tickers, selected=symbol, details=details, search=symbol)

if __name__ == "__main__":
    app.run(debug=True)

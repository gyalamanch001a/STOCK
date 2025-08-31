from flask import Flask, render_template_string, request
import pandas as pd
import os

app = Flask(__name__)

CSV_FILE = "nasdaq_summary.csv"

# Import fetch_summary from stock.py
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from stock import fetch_summary

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
                <table>
                    {% for key, value in details.items() %}
                        <tr><td class="key">{{ key }}</td><td>{{ value }}</td></tr>
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
        # Extract today's and previous day's high, low, open, close, date
        key_data = {}
        today_date = pd.Timestamp.today().strftime('%Y-%m-%d')
        # Try to get today's data
        for field in ["high", "low", "open", "close"]:
            val = row.get(f"Today {field.capitalize()}") or row.get(f"{field.capitalize()}")
            key_data[f"Today {field.capitalize()}"] = val
        key_data["Date"] = today_date
        # Previous day
        for field in ["high", "low", "open", "close"]:
            val = row.get(f"Previous {field.capitalize()}") or row.get(f"Prev {field.capitalize()}")
            key_data[f"Previous {field.capitalize()}"] = val
        # Also show all other fields
        for k, v in row.items():
            if k not in key_data:
                key_data[k] = v
        return key_data

    # If search is present and not in tickers, fetch from API
    if search:
        if search not in tickers:
            new_row = fetch_summary(search)
            if new_row:
                # Add today's and previous day's fields if available
                today_date = pd.Timestamp.today().strftime('%Y-%m-%d')
                # Example: try to extract from summaryData
                for field in ["high", "low", "open", "close"]:
                    if field.capitalize() in new_row:
                        new_row[f"Today {field.capitalize()}"] = new_row[field.capitalize()]
                        new_row[f"Previous {field.capitalize()}"] = None
                new_row["Date"] = today_date
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(CSV_FILE, index=False)
                tickers.append(search)
                selected = search
                details = extract_key_data(new_row)
            else:
                details = {"Error": f"Could not fetch data for {search}"}
        else:
            selected = search

    # If selected ticker is present, show details
    if selected and selected in tickers:
        details_row = df[df["Symbol"] == selected]
        if not details_row.empty:
            details = extract_key_data(details_row.iloc[0].to_dict())

    return render_template_string(TEMPLATE, tickers=tickers, selected=selected, details=details, search=search)

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template_string, request
import pandas as pd
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fetch_ohlc_yfinance import fetch_ohlc_yfinance
from stock import fetch_summary
import subprocess

app = Flask(__name__)

CSV_FILE = "nasdaq_summary.csv"

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
        function runDayTradingAssistant() {
            fetch('/run_daytrading_assistant').then(r => r.json()).then(data => {
                let html = '<h3>Day Trading Recommendations</h3>';
                if (data.table && data.table.length > 0) {
                    html += '<table><thead><tr>';
                    for (let col of data.columns) {
                        html += `<th>${col}</th>`;
                    }
                    html += '</tr></thead><tbody>';
                    for (let row of data.table) {
                        html += '<tr>';
                        for (let col of data.columns) {
                            html += `<td>${row[col] || '-'}</td>`;
                        }
                        html += '</tr>';
                    }
                    html += '</tbody></table>';
                } else {
                    html += '<p>No recommendations found.</p>';
                }
                if (data.summary) {
                    html += `<div class="summary"><strong>Summary:</strong><br>${data.summary}</div>`;
                }
                document.getElementById('daytrading-panel').innerHTML = html;
                document.getElementById('daytrading-panel').style.display = 'block';
            });
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
                <div style="margin-top:60px;">
                    <form method="post" action="/fetch_ohlc">
                        <input type="hidden" name="symbol" value="{{ selected }}" />
                        <button type="submit">Fetch OHLC from Yahoo Finance</button>
                    </form>
                    <!-- Key OHLC Data table removed as requested -->
                    <div style="margin-top:30px;">
                        <table style="border-collapse:collapse; width:100%;">
                            <tr style="background:#e8e8e8;"><th colspan="4">All Details</th></tr>
                            {% set items = details.items()|list %}
                            {% for i in range(0, items|length, 2) %}
                                <tr>
                                    <td class="key">{{ items[i][0] }}</td><td>{{ items[i][1] }}</td>
                                    {% if i+1 < items|length %}
                                        <td class="key">{{ items[i+1][0] }}</td><td>{{ items[i+1][1] }}</td>
                                    {% else %}
                                        <td></td><td></td>
                                    {% endif %}
                                </tr>
                            {% endfor %}
                        </table>
                    </div>
                </div>
            {% else %}
                <p>Select a ticker to view details.</p>
            {% endif %}
        </div>
    </div>
    <button id="daytrading-btn" onclick="runDayTradingAssistant()" style="position:absolute;top:20px;right:40px;background:#ffd700;color:#222;border:none;padding:10px 20px;font-size:1.1em;border-radius:5px;cursor:pointer;z-index:1000;">Day Trading Assistant</button>
    <div id="daytrading-panel" style="display:none;position:absolute;top:60px;right:40px;background:#222;color:#ffd700;border-radius:10px;padding:20px;min-width:350px;z-index:1001;box-shadow:0 0 10px #888;"></div>
</body>
</html>
'''

def parse_gpt2_output(output):
    table_data = []
    summary = ""
    rows = output.split('\n- Ticker & Name:')
    for row in rows[1:]:
        fields = {}
        for key in [
            'Ticker & Name', 'Entry Price', 'Exit Price', 'Stop-Loss', 'Risk-Reward Ratio',
            'Indicators & Patterns', 'Sentiment & News', 'Liquidity & Volatility', 'Rationale', 'Short Selling Setup']:
            marker = f'- {key}:'
            if marker in row:
                value = row.split(marker)[1].split('\n')[0].strip()
                fields[key] = value
            else:
                fields[key] = ''
        table_data.append(fields)
    if 'Top 2–3 strongest trade opportunities for today' in output:
        summary = output.split('Top 2–3 strongest trade opportunities for today')[-1].strip()
    return table_data, summary

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

    if search:
        if search not in tickers:
            new_row = fetch_summary(search) or {"Symbol": search}
            ohlc_data = fetch_ohlc_yfinance(search)
            if ohlc_data:
                new_row.update(ohlc_data)
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(CSV_FILE, index=False)
            df = pd.read_csv(CSV_FILE)
            tickers = df["Symbol"].tolist() if "Symbol" in df.columns else []
            selected = search
        else:
            details_row = df[df["Symbol"] == search]
            if not details_row.empty:
                row_dict = details_row.iloc[0].to_dict()
                missing_fields = [f for f in ["Today High", "Today Low", "Today Open", "Today Close", "Previous High", "Previous Low", "Previous Open", "Previous Close"] if row_dict.get(f) in [None, '', 'None'] or pd.isna(row_dict.get(f))]
                if missing_fields:
                    ohlc_data = fetch_ohlc_yfinance(search)
                    if ohlc_data:
                        for k, v in ohlc_data.items():
                            if v not in [None, '', 'None']:
                                df.loc[df["Symbol"] == search, k] = v
                        df.to_csv(CSV_FILE, index=False)
                        df = pd.read_csv(CSV_FILE)
            selected = search

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
        ohlc_data = fetch_ohlc_yfinance(symbol)
        if ohlc_data:
            for k, v in ohlc_data.items():
                if v not in [None, '', 'None']:
                    df.loc[df["Symbol"] == symbol, k] = v
            df.to_csv(CSV_FILE, index=False)
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


@app.route('/run_daytrading_assistant')
def run_daytrading_assistant():
    # Run the local GPT-2 script
    subprocess.run([sys.executable, 'run_local_gpt2_prompt.py'])
    # Parse the CSV file
    csv_file = 'day_trading_recommendation.csv'
    import json
    import pandas as pd
    if not os.path.exists(csv_file):
        return json.dumps({'table': [], 'columns': [], 'summary': 'No CSV file found.'})
    df = pd.read_csv(csv_file)
    columns = df.columns.tolist()
    table = df.to_dict(orient='records')
    summary = ''
    if 'Summary' in df.columns:
        summary = df['Summary'].iloc[0]
    return json.dumps({'table': table, 'columns': columns, 'summary': summary})

if __name__ == "__main__":
    app.run(debug=True)

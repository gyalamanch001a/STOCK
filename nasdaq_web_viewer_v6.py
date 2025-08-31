from flask import Flask, render_template_string, request, jsonify, send_file
import pandas as pd
import os
import sys
import subprocess

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fetch_ohlc_yfinance import fetch_ohlc_yfinance  # noqa: E402
from stock import fetch_summary  # noqa: E402

app = Flask(__name__)

CSV_FILE = "nasdaq_summary.csv"
DT_CSV = "day_trading_recommendation.csv"


def _dt_csv_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DT_CSV)


def read_daytrading_csv():
    """Read the day trading CSV and return (columns, records, summary, mtime)."""
    csv_path = _dt_csv_path()
    if not os.path.exists(csv_path):
        return [], [], "", None
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return [], [], "", os.path.getmtime(csv_path)
    columns = df.columns.tolist()
    records = df.to_dict(orient="records")
    summary = df["Summary"].iloc[0] if "Summary" in df.columns and not df.empty else ""
    mtime = os.path.getmtime(csv_path)
    return columns, records, summary, mtime


TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nasdaq Summary Viewer v6</title>
    <style>
        :root {
            --panel-bg: #1f1f1f;
            --panel-fg: #f7d774;
            --panel-accent: #ffd700;
            --muted: #b8b8b8;
            --border: #333;
        }
        body { font-family: Arial, sans-serif; }
        .container { display: flex; height: 90vh; }
        .tickers { width: 30%; border-right: 1px solid #ccc; overflow-y: auto; }
        .details { width: 70%; padding: 20px; }
        .ticker-item { padding: 10px; cursor: pointer; border-bottom: 1px solid #eee; }
        .ticker-item.selected { background: #e0e0ff; }
        .key { font-weight: bold; }
        .search-box { width: 90%; margin: 10px; padding: 8px; font-size: 1em; }
        .search-form { text-align: center; }

        /* Day trading card embedded above the OHLC button */
        .dt-card {
            background: var(--panel-bg);
            color: var(--panel-fg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.25);
            margin-bottom: 16px;
        }
        .dt-card h3 { margin: 0 0 8px 0; color: var(--panel-accent); }
        #dt-controls { display:flex; gap:8px; align-items:center; margin: 6px 0 8px 0; }
        #dt-controls button { background: var(--panel-accent); color:#222; border:none; padding:6px 10px; border-radius:6px; cursor:pointer; font-weight:bold; }
        #dt-controls .muted { color: var(--muted); font-size: 0.9em; }
        #dt-controls label { display:flex; align-items:center; gap:6px; color: var(--muted); font-size:0.9em; }
        #dt-table { width:100%; border-collapse: collapse; font-size: 0.9em; }
        #dt-table th, #dt-table td { border: 1px solid var(--border); padding: 6px; vertical-align: top; color:#f0f0f0; }
        #dt-table th { position: sticky; top:0; background:#2a2a2a; z-index:1; }
        #dt-table tr:nth-child(even) { background:#242424; }
        #dt-table tr:nth-child(odd) { background:#1b1b1b; }
        .wrap { white-space: normal; word-break: break-word; }
        .pill { display:inline-block; background:#333; color:#eee; padding:2px 6px; border-radius:8px; font-size:0.8em; }
        .summary { margin-top: 8px; color:#eee; }
        .spinner { display:none; width:18px; height:18px; border:3px solid #ccc; border-top-color: #555; border-radius:50%; animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .hide { display:none; }
    </style>
    <script>
        const primaryCols = ["Ticker & Name","Entry Price","Exit Price","Stop-Loss","Risk-Reward Ratio"];
        let autoRefresh = false;
        let autoTimer = null;

        function selectTicker(symbol) {
            window.location.href = '/?symbol=' + symbol;
        }

        function setLoading(isLoading) {
            const el = document.getElementById('dt-spinner');
            if (el) el.style.display = isLoading ? 'inline-block' : 'none';
        }

        function formatTime(epoch) {
            if (!epoch) return 'unknown';
            const d = new Date(epoch * 1000);
            return d.toLocaleString();
        }

        async function fetchDaytradingData() {
            setLoading(true);
            try {
                const r = await fetch('/daytrading_data');
                const data = await r.json();
                renderDaytrading(data);
            } catch (e) {
                renderDaytrading({table:[], columns:[], summary:'Error loading data: ' + e, updated_at:null});
            } finally { setLoading(false); }
        }

        async function runDayTradingAssistant() {
            setLoading(true);
            try {
                const r = await fetch('/run_daytrading_assistant');
                // Summary intentionally omitted from UI
            } catch (e) {
                renderDaytrading({table:[], columns:[], summary:'Error running assistant: ' + e, updated_at:null});
            } finally { setLoading(false); }
        }

        function toggleAutoRefresh(cb) {
            autoRefresh = cb.checked;
            if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
            if (autoRefresh) {
                autoTimer = setInterval(fetchDaytradingData, 60000); // every 60s
            }
        }

        function buildTable(columns, rows) {
            // Select columns to display: primary first if present, then any remaining
            const present = new Set(columns);
            const displayCols = primaryCols.filter(c=>present.has(c)).concat(columns.filter(c=>!primaryCols.includes(c)));
            let thead = '<thead><tr>' + displayCols.map(c=>`<th>${c}</th>`).join('') + '</tr></thead>';
            let tbody = '<tbody>' + rows.map(r=>{
                return '<tr>' + displayCols.map(c=>`<td class="wrap">${(r[c] ?? '').toString().replace(/</g,'&lt;')}</td>`).join('') + '</tr>';
            }).join('') + '</tbody>';
            return '<table id="dt-table">' + thead + tbody + '</table>';
        }

        function renderDaytrading(data) {
            const info = document.getElementById('dt-info');
            const cont = document.getElementById('dt-content');
            const ts = data.updated_at ? `Updated: <span class="pill">${formatTime(data.updated_at)}</span>` : '';
            if (info) info.innerHTML = `${ts} <span class="pill">Rows: ${data.table ? data.table.length : 0}</span>`;
            if (cont) {
                if (data.table && data.table.length > 0) {
                    cont.innerHTML = buildTable(data.columns || [], data.table || []);
                } else {
                    cont.innerHTML = '<p class="muted">No recommendations found.</p>';
                }
            }
            const summary = document.getElementById('dt-summary');
            if (summary) summary.innerHTML = data.summary ? `<div class="summary"><strong>Summary:</strong><br>${data.summary}</div>` : '';
        }

        window.addEventListener('DOMContentLoaded', () => {
            fetchDaytradingData(); // load on start
        });
    </script>
</head>
<body>
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
            <div style="margin-top:20px;">
                <!-- Day Trading Assistant card shown always, summary omitted -->
                <div id="daytrading-card" class="dt-card">
                    <h3>Day Trading Assistant</h3>
                    <div id="dt-controls">
                        <button onclick="runDayTradingAssistant()">Run</button>
                        <button onclick="fetchDaytradingData()">Refresh</button>
                        <div class="spinner" id="dt-spinner"></div>
                        <label><input type="checkbox" onchange="toggleAutoRefresh(this)"> Auto-refresh</label>
                        <a href="/download_daytrading_csv" style="color:var(--panel-accent);text-decoration:none; margin-left:auto;">Download CSV</a>
                    </div>
                    <div id="dt-info" class="muted" style="margin-bottom:6px;"></div>
                    <div id="dt-content"></div>
                </div>
            </div>
            {% if details %}
                <div style="margin-top:20px;">
                    <form method="post" action="/fetch_ohlc">
                        <input type="hidden" name="symbol" value="{{ selected }}" />
                        <button type="submit">Fetch OHLC from Yahoo Finance</button>
                    </form>
                    <div style="margin-top:20px;">
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

    <!-- Note: Day Trading card is embedded within the details section above -->
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
        for field in [
            "Today High",
            "Today Low",
            "Today Open",
            "Today Close",
            "Previous High",
            "Previous Low",
            "Previous Open",
            "Previous Close",
            "Date",
        ]:
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
                missing_fields = [
                    f
                    for f in [
                        "Today High",
                        "Today Low",
                        "Today Open",
                        "Today Close",
                        "Previous High",
                        "Previous Low",
                        "Previous Open",
                        "Previous Close",
                    ]
                    if row_dict.get(f) in [None, "", "None"] or pd.isna(row_dict.get(f))
                ]
                if missing_fields:
                    ohlc_data = fetch_ohlc_yfinance(search)
                    if ohlc_data:
                        for k, v in ohlc_data.items():
                            if v not in [None, "", "None"]:
                                df.loc[df["Symbol"] == search, k] = v
                        df.to_csv(CSV_FILE, index=False)
                        df = pd.read_csv(CSV_FILE)
            selected = search

    if selected and selected in tickers:
        details_row = df[df["Symbol"] == selected]
        if not details_row.empty:
            details = extract_key_data(details_row.iloc[0].to_dict())

    return render_template_string(
        TEMPLATE, tickers=tickers, selected=selected, details=details, search=search
    )


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
                if v not in [None, "", "None"]:
                    df.loc[df["Symbol"] == symbol, k] = v
            df.to_csv(CSV_FILE, index=False)
    df = pd.read_csv(CSV_FILE)
    tickers = df["Symbol"].tolist() if "Symbol" in df.columns else []
    details_row = df[df["Symbol"] == symbol]
    details = None
    if not details_row.empty:
        def extract_key_data(row):
            key_data = {}
            for field in [
                "Today High",
                "Today Low",
                "Today Open",
                "Today Close",
                "Previous High",
                "Previous Low",
                "Previous Open",
                "Previous Close",
                "Date",
            ]:
                key_data[field] = row.get(field)
            for k, v in row.items():
                if k not in key_data:
                    key_data[k] = v
            return key_data
        details = extract_key_data(details_row.iloc[0].to_dict())
    return render_template_string(TEMPLATE, tickers=tickers, selected=symbol, details=details, search=symbol)


@app.route('/daytrading_data')
def daytrading_data():
    cols, rows, summary, mtime = read_daytrading_csv()
    updated_at = int(mtime) if mtime else None
    return jsonify({
        'columns': cols,
        'table': rows,
        'summary': summary,
        'updated_at': updated_at,
    })


@app.route('/run_daytrading_assistant')
def run_daytrading_assistant():
    # Run the local GPT-2 script to regenerate CSV
    subprocess.run([sys.executable, 'run_local_gpt2_prompt.py'])
    # Then return the latest data
    cols, rows, summary, mtime = read_daytrading_csv()
    updated_at = int(mtime) if mtime else None
    return jsonify({
        'columns': cols,
        'table': rows,
        'summary': summary,
        'updated_at': updated_at,
    })


@app.route('/download_daytrading_csv')
def download_daytrading_csv():
    path = _dt_csv_path()
    if not os.path.exists(path):
        return "CSV not found", 404
    # send_file will set appropriate headers for download
    return send_file(path, as_attachment=True, download_name=DT_CSV)


if __name__ == "__main__":
    app.run(debug=True)

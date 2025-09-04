import os
import sys
import subprocess
import threading
from flask import Flask, render_template_string, request, jsonify, send_file, redirect
import pandas as pd
from fetch_ohlc_yfinance import fetch_ohlc_yfinance  # noqa: E402
from stock import fetch_summary  # noqa: E402

app = Flask(__name__)

CSV_FILE = "nasdaq_summary.csv"
DT_CSV = "day_trading_recommendation.csv"

V6_TEMPLATE = '''
<nav style="background:#222;padding:12px 24px;display:flex;align-items:center;gap:32px;border-radius:8px 8px 0 0;">
<a href="/home" style="color:#ffd700;text-decoration:none;font-weight:bold;">Home</a>
<div style="position:relative;">
<span style="color:#ffd700;cursor:pointer;font-weight:bold;" onclick="document.getElementById('tools-dropdown').style.display='block'">Tools v</span>
<div style="position:absolute;top:24px;left:0;background:#333;border-radius:6px;box-shadow:0 2px 8px #0002;display:none;min-width:120px;z-index:10;" id="tools-dropdown" onmouseleave="this.style.display='none'">
<a href="/tools/nmapv" style="display:block;padding:8px 16px;color:#ffd700;text-decoration:none;">nmapv</a>
</div>
</div>
<a href="#about" style="color:#ffd700;text-decoration:none;font-weight:bold;">About</a>
</nav>
<body style="background:#1f1f1f;color:#ffd700;">
<div class="container" style="display:flex;max-width:1200px;margin:auto;">
    <div class="tickers" style="width:320px;min-width:220px;max-height:80vh;overflow-y:auto;border-right:1px solid #444;padding:24px 12px 24px 24px;">
        <h3 style="color:#ffd700;">Tickers</h3>
        <form class="search-form" method="get" action="/home" style="margin-bottom:16px;">
            <input id="search-box" class="search-box" type="text" name="search" placeholder="Search ticker..." value="{{ search or '' }}" style="padding:8px;width:90%;margin-bottom:8px;" />
            <button type="submit">Search</button>
        </form>
        <ul style="list-style:none;padding:0;margin:0;">
            {% for ticker in tickers %}
            <li style="margin-bottom:4px;">
                <button style="width:100%;padding:8px 12px;background:#333;color:#ffd700;border:none;border-radius:6px;cursor:pointer;text-align:left;{% if ticker == selected %}font-weight:bold;background:#222;{% endif %}" onclick="window.location.href='/home?symbol={{ ticker }}'">{{ ticker }}</button>
            </li>
            {% endfor %}
        </ul>
    </div>
    <div class="details" style="flex:1;padding:32px;">
        <h2>Nasdaq Dashboard (v6)</h2>
        <!-- Day Trading Assistant Card -->
            <div id="daytrading-card" class="dt-card" style="margin-bottom:24px;background:#fffbe6;color:#222;border:1px solid #ffd700;border-radius:10px;padding:12px;box-shadow:0 6px 18px rgba(0,0,0,0.10);">
                <h3 style="color:#d4a200;">Day Trading Assistant</h3>
                <div id="dt-controls" style="display:flex;gap:8px;align-items:center;margin:6px 0 8px 0;">
                    <button onclick="runDayTradingAssistant()" style="background:#ffd700;color:#222;border:none;padding:6px 10px;border-radius:6px;cursor:pointer;font-weight:bold;">Run</button>
                    <button onclick="fetchDaytradingData()" style="background:#ffd700;color:#222;border:none;padding:6px 10px;border-radius:6px;cursor:pointer;font-weight:bold;">Refresh</button>
                    <div class="spinner" id="dt-spinner" style="display:none;width:18px;height:18px;border:3px solid #ffd700;border-top-color:#d4a200;border-radius:50%;animation:spin 1s linear infinite;"></div>
                    <label style="display:flex;align-items:center;gap:6px;color:#222;font-size:0.9em;"><input type="checkbox" onchange="toggleAutoRefresh(this)"> Auto-refresh</label>
                    <a href="/download_daytrading_csv" style="color:#d4a200;text-decoration:none;margin-left:auto;">Download CSV</a>
                </div>
                <div id="dt-info" class="muted" style="margin-bottom:6px;color:#222;"></div>
                <div id="dt-content" style="color:#222;"></div>
                <button id="show-summary-btn" style="margin-top:12px;background:#ffd700;color:#222;border:none;padding:6px 10px;border-radius:6px;cursor:pointer;font-weight:bold;">Show Summary</button>
                <div id="summary-popup" style="display:none;position:fixed;top:20%;left:50%;transform:translate(-50%,0);background:#fffbe6;color:#222;border:2px solid #ffd700;padding:24px;border-radius:12px;z-index:1000;min-width:320px;max-width:600px;box-shadow:0 6px 24px #0005;">
                  <h3 style="color:#d4a200;">Day Trading Summary</h3>
                  <div id="summary-content"></div>
                  <button onclick="document.getElementById('summary-popup').style.display='none'" style="margin-top:16px;background:#ffd700;color:#222;border:none;padding:6px 10px;border-radius:6px;cursor:pointer;font-weight:bold;">Close</button>
                </div>
                <script>
        async function fetchDaytradingData() {
          const spinner = document.getElementById('dt-spinner');
          if (spinner) spinner.style.display = 'inline-block';
          try {
            const r = await fetch('/daytrading_data');
            const data = await r.json();
            renderDaytrading(data);
          } catch (e) {
            document.getElementById('dt-content').innerHTML = '<p style="color:#d00;">Error loading data: ' + e + '</p>';
          } finally {
            if (spinner) spinner.style.display = 'none';
          }
        }
        function renderDaytrading(data) {
          const info = document.getElementById('dt-info');
          const cont = document.getElementById('dt-content');
          const ts = data.updated_at ? `Updated: <span class="pill">${new Date(data.updated_at*1000).toLocaleString()}</span>` : '';
          if (info) info.innerHTML = `${ts} <span class="pill">Rows: ${data.table ? data.table.length : 0}</span>`;
          if (cont) {
            if (data.table && data.table.length > 0) {
              cont.innerHTML = buildTable(data.columns || [], data.table || []);
            } else {
              cont.innerHTML = '<p class="muted">No recommendations found.</p>';
            }
          }
        }
        function buildTable(columns, rows) {
          if (!columns || columns.length === 0) return '';
          // Remove 'Summary' column from display
          const displayCols = columns.filter(c => c !== 'Summary');
          let thead = '<thead><tr><th></th>' + displayCols.map(c=>`<th style=\"color:#d4a200;background:#222;\">${c}</th>`).join('') + '</tr></thead>';
          let tbody = '<tbody>' + rows.map((r, idx)=>{
            return '<tr>' + `<td><input type=\"radio\" name=\"dt-ticker\" value=\"${idx}\"></td>` + displayCols.map(c=>`<td style=\"color:#222;background:#fffbe6;\">${(r[c] ?? '').toString().replace(/</g,'&lt;')}</td>`).join('') + '</tr>';
          }).join('') + '</tbody>';
          return '<table id="dt-table" style="width:100%;border-collapse:collapse;">' + thead + tbody + '</table>';
        }
        window.addEventListener('DOMContentLoaded', fetchDaytradingData);
        document.getElementById('show-summary-btn').onclick = function() {
          const radios = document.getElementsByName('dt-ticker');
          let selectedIdx = null;
          for (const r of radios) { if (r.checked) selectedIdx = r.value; }
          if (selectedIdx === null) {
            document.getElementById('summary-content').innerHTML = '<p style="color:#d00;">Please select a ticker to view its summary.</p>';
            document.getElementById('summary-popup').style.display = 'block';
            return;
          }
          fetch('/daytrading_data').then(r=>r.json()).then(data=>{
            if (data.table && data.table[selectedIdx] && data.table[selectedIdx].Summary) {
              document.getElementById('summary-content').innerHTML = `<div style='white-space:pre-line;'>${data.table[selectedIdx].Summary}</div>`;
            } else {
              document.getElementById('summary-content').innerHTML = '<p>No summary available for this ticker.</p>';
            }
            document.getElementById('summary-popup').style.display = 'block';
          });
        };
            </script>
            </div>
        {% if not details %}
            <p>Select a ticker to view details.</p>
        {% endif %}
        {% if details %}
            <div style="margin-top:24px;background:#fffbe6;color:#222;padding:12px;border-radius:8px;border:1px solid #ffd700;">
                <form method="post" action="/fetch_ohlc">
                    <input type="hidden" name="symbol" value="{{ selected }}" />
                    <button type="submit" style="background:#ffd700;color:#222;border:none;padding:6px 10px;border-radius:6px;cursor:pointer;font-weight:bold;"> OHLC </button>
                </form>
                <div style="margin-top:20px;">
                    <table style="border-collapse:collapse;width:100%;background:#fff;">
                        <tr style="background:#ffd700;color:#222;"><th colspan="4">All Details</th></tr>
                        {% set items = details.items()|list %}
                        {% for i in range(0, items|length, 2) %}
                        <tr>
                            <td class="key" style="color:#d4a200;font-weight:bold;">{{ items[i][0] }}</td><td style="color:#222;">{{ items[i][1] }}</td>
                            {% if i+1 < items|length %}
                                <td class="key" style="color:#d4a200;font-weight:bold;">{{ items[i+1][0] }}</td><td style="color:#222;">{{ items[i+1][1] }}</td>
                            {% else %}
                                <td></td><td></td>
                            {% endif %}
                        </tr>
                        {% endfor %}
                    </table>
                </div>
            </div>
        {% endif %}
    </div>
</div>
'''

def get_v6_dashboard():
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
            "Today High", "Today Low", "Today Open", "Today Close",
            "Previous High", "Previous Low", "Previous Open", "Previous Close", "Date"
        ]:
            key_data[field] = row.get(field)
        for k, v in row.items():
            if k not in key_data:
                key_data[k] = v
        return key_data
    if search:
        if search not in tickers:
            # fallback: just show tickers
            pass
        else:
            details_row = df[df["Symbol"] == search]
            if not details_row.empty:
                row_dict = details_row.iloc[0].to_dict()
                details = extract_key_data(row_dict)
            selected = search
    if selected and selected in tickers:
        details_row = df[df["Symbol"] == selected]
        if not details_row.empty:
            details = extract_key_data(details_row.iloc[0].to_dict())
    # Minimal v6 template for Home
    return render_template_string(V6_TEMPLATE, tickers=tickers, selected=selected, details=details, search=search)

@app.route('/home')
def home():
    return get_v6_dashboard()

# --- V6 Functionality and Presentation ---
def _dt_csv_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DT_CSV)

def read_daytrading_csv():
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
            "Today High", "Today Low", "Today Open", "Today Close",
            "Previous High", "Previous Low", "Previous Open", "Previous Close", "Date"
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
                    f for f in [
                        "Today High", "Today Low", "Today Open", "Today Close",
                        "Previous High", "Previous Low", "Previous Open", "Previous Close"
                    ] if row_dict.get(f) in [None, "", "None"] or pd.isna(row_dict.get(f))
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
    return render_template_string(V6_TEMPLATE, tickers=tickers, selected=selected, details=details, search=search)

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
                "Today High", "Today Low", "Today Open", "Today Close",
                "Previous High", "Previous Low", "Previous Open", "Previous Close", "Date"
            ]:
                key_data[field] = row.get(field)
            for k, v in row.items():
                if k not in key_data:
                    key_data[k] = v
            return key_data
        details = extract_key_data(details_row.iloc[0].to_dict())
    return render_template_string(V6_TEMPLATE, tickers=tickers, selected=symbol, details=details, search=symbol)

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
    subprocess.run([sys.executable, 'run_local_gpt2_prompt.py'])
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
    return send_file(path, as_attachment=True, download_name=DT_CSV)

nmapv_proc = None

def _nmapv_log_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nmapv_run.log')

def _read_nmapv_log():
    path = _nmapv_log_path()
    if not os.path.exists(path): return ''
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()[-10000:]  # last 10k chars

def _run_nmapv():
    global nmapv_proc
    if nmapv_proc and nmapv_proc.poll() is None:
        return False
    log_path = _nmapv_log_path()
    with open(log_path, 'w', encoding='utf-8') as f:
        pass
    nmapv_proc = subprocess.Popen([
        sys.executable, 'nmapv.py', '--port', '1234', '--backlog', '10', '--rate-limit', '5', '--log-level', 'INFO'
    ], stdout=open(log_path, 'a'), stderr=subprocess.STDOUT)
    return True

def _stop_nmapv():
    global nmapv_proc
    if nmapv_proc and nmapv_proc.poll() is None:
        nmapv_proc.terminate()
        nmapv_proc.wait(timeout=5)
        nmapv_proc = None
        return True
    nmapv_proc = None
    return False

def _is_nmapv_running():
    global nmapv_proc
    return nmapv_proc and nmapv_proc.poll() is None

# --- Flask routes for nmapv tool ---
@app.route('/tools/nmapv')
def tools_nmapv():
    return render_template_string(NMAPV_TEMPLATE)

@app.route('/tools/nmapv/run', methods=['POST'])
def tools_nmapv_run():
    ok = _run_nmapv()
    return jsonify({'running': _is_nmapv_running()})

@app.route('/tools/nmapv/stop', methods=['POST'])
def tools_nmapv_stop():
    ok = _stop_nmapv()
    return jsonify({'stopped': ok})

# Route to serve nmapv log content
@app.route('/tools/nmapv/log')
def tools_nmapv_log():
    try:
        log_content = _read_nmapv_log()
    except Exception as e:
        log_content = f"Error reading log: {e}"
    return log_content, 200, {'Content-Type': 'text/plain; charset=utf-8'}

NMAPV_TEMPLATE = '''
    <nav style="background:#222;padding:12px 24px;display:flex;align-items:center;gap:32px;border-radius:8px 8px 0 0;">
        <a href="/home" style="color:#ffd700;text-decoration:none;font-weight:bold;">Home</a>
        <div style="position:relative;">
        <div style="position:absolute;top:24px;left:0;background:#333;border-radius:6px;box-shadow:0 2px 8px #0002;display:none;min-width:120px;z-index:10;" id="tools-dropdown">
            <a href="/tools/nmapv" style="display:block;padding:8px 16px;color:#ffd700;text-decoration:none;">nmapv</a>
        </div>
    </div>
    <a href="#about" style="color:#ffd700;text-decoration:none;">About</a>
</nav>
<div style="padding:32px;max-width:700px;margin:auto;">
    <h2>Nasdaq Dashboard (v6)</h2>
    <form method="get" action="/home">
        <input type="text" name="search" placeholder="Search ticker..." value="{{ search or '' }}" style="padding:8px;width:220px;" />
        <button type="submit">Search</button>
    </form>
    <h2>nmapv Tool</h2>
    <button id="run-btn" onclick="runNmapv()">Run nmapv</button>
    <button id="stop-btn" onclick="stopNmapv()" disabled>Stop nmapv</button>
    <div style="margin-top:24px;background:#222;color:#ffd700;padding:12px;border-radius:8px;min-height:120px;max-height:400px;overflow:auto;" id="nmapv-log"></div>
</div>
<script>
let nmapvRunning = false;
let logTimer = null;
function runNmapv(){
    fetch('/tools/nmapv/run',{method:'POST'}).then(r=>r.json()).then(d=>{
        nmapvRunning = d.running;
        document.getElementById('run-btn').disabled = nmapvRunning;
        document.getElementById('stop-btn').disabled = !nmapvRunning;
        logTimer = setInterval(()=>{
            fetch('/tools/nmapv/log').then(r=>r.text()).then(txt=>{
                document.getElementById('nmapv-log').innerText = txt;
                window.scrollTo(0,document.body.scrollHeight);
            });
        },1000);
    });
}
function stopNmapv(){
    fetch('/tools/nmapv/stop',{method:'POST'}).then(r=>r.json()).then(d=>{
        nmapvRunning = !d.stopped;
        document.getElementById('run-btn').disabled = nmapvRunning;
        document.getElementById('stop-btn').disabled = !nmapvRunning;
        clearInterval(logTimer);
    });
}
</script>
'''

if __name__ == "__main__":
    app.run(debug=True)

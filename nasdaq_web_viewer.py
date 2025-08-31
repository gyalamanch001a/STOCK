from flask import Flask, render_template_string, request
import pandas as pd
import os

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
    selected = request.args.get("symbol", tickers[0] if tickers else None)
    details = None
    if selected and selected in tickers:
        details_row = df[df["Symbol"] == selected]
        if not details_row.empty:
            details = details_row.iloc[0].to_dict()
    return render_template_string(TEMPLATE, tickers=tickers, selected=selected, details=details)

if __name__ == "__main__":
    app.run(debug=True)

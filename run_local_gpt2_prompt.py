import csv
import logging
import os
import re
from datetime import datetime
from typing import List, Dict, Tuple
from transformers import pipeline


LOG_FILE = "day_trading_assistant.log"
CSV_FILE = "day_trading_recommendation.csv"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler()
        ],
    )


def run_local_gpt2_prompt(prompt: str, max_new_tokens: int = 256) -> str:
    """Run a prompt using a local GPT-2 model and return the generated text."""
    logging.info("Loading GPT-2 pipeline…")
    generator = pipeline("text-generation", model="gpt2")
    logging.info("Generating text…")
    # Use generation settings that tend to be more coherent
    result = generator(
        prompt,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=0.8,
        top_p=0.95,
        pad_token_id=50256,
    )
    text = result[0]["generated_text"]
    logging.info("Generation complete. %d chars", len(text))
    return text


def parse_recommendations(text: str) -> Tuple[List[Dict[str, str]], str]:
    """Parse generated text into table rows and a summary string.

    The parser is tolerant to small format variations. It looks for fields like
    "Ticker & Name", "Entry Price", etc. If none found, returns an empty table
    and empty summary so the caller can fallback.
    """
    # Normalize bullets and whitespace
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    # Try to remove the prompt prefix if present
    # Heuristic: take only the text after the first "Output:" or after the first schema key
    start_idx = 0
    for marker in ["Output Format", "For each suggested stock today,", "- Ticker & Name:"]:
        i = norm.find(marker)
        if i != -1:
            start_idx = i
            break
    norm = norm[start_idx:]

    # Split into potential item blocks by looking for our first key marker
    blocks = re.split(r"\n\s*[-*]\s*Ticker\s*&\s*Name\s*:\s*", norm)
    rows: List[Dict[str, str]] = []
    if len(blocks) > 1:
        # First chunk is preamble; each next chunk starts after the key value on same line
        for chunk in blocks[1:]:
            # The first line up to newline is the value for Ticker & Name
            first_line, _, rest = chunk.partition("\n")
            item_text = "- Ticker & Name: " + (first_line.strip()) + "\n" + rest
            rows.append(_extract_fields(item_text))
    else:
        # Fallback: try to detect lightweight inline items using semicolons or lines
        candidate = _extract_fields(norm)
        if any(v for v in candidate.values()):
            rows.append(candidate)

    # Extract summary
    summary = ""
    m = re.search(r"Top\s+2[–-]3\s+strongest\s+trade\s+opportunities\s+for\s+today\*?[:\-]?\s*(.*)$",
                  norm, re.IGNORECASE | re.DOTALL)
    if m:
        summary = m.group(1).strip()

    return rows, summary


def _extract_fields(block_text: str) -> Dict[str, str]:
    keys = [
        "Ticker & Name",
        "Entry Price",
        "Exit Price",
        "Stop-Loss",
        "Risk-Reward Ratio",
        "Indicators & Patterns",
        "Sentiment & News",
        "Liquidity & Volatility",
        "Rationale",
        "Short Selling Setup",
    ]
    data: Dict[str, str] = {k: "" for k in keys}

    # Accept bullets -, *, or none; tolerate extra spaces
    for k in keys:
        m = re.search(rf"^[\-*\s]*{re.escape(k)}\s*:\s*(.+)$", block_text, re.IGNORECASE | re.MULTILINE)
        if m:
            data[k] = m.group(1).strip()
    return data


def write_csv(rows: List[Dict[str, str]], summary: str, out_path: str = CSV_FILE) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fieldnames = [
        "Ticker & Name","Entry Price","Exit Price","Stop-Loss","Risk-Reward Ratio",
        "Indicators & Patterns","Sentiment & News","Liquidity & Volatility","Rationale","Short Selling Setup","Summary"
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        if not rows:
            writer.writerow({"Summary": summary})
        else:
            for i, r in enumerate(rows):
                row = {k: r.get(k, "") for k in fieldnames}
                row["Summary"] = summary if i == 0 else ""
                writer.writerow(row)
    logging.info("Wrote %d rows to %s", max(1, len(rows)), out_path)
    return out_path


def build_prompt() -> str:
    # Keep user's structure but add a compact, explicit schema with one tiny example
    return (
        "You are my professional day trading assistant.\n"
        "Your goal is to output concrete intraday trade setups.\n\n"
        "Required output keys per idea (use exactly these labels):\n"
        "- Ticker & Name:\n- Entry Price:\n- Exit Price:\n- Stop-Loss:\n- Risk-Reward Ratio:\n"
        "- Indicators & Patterns:\n- Sentiment & News:\n- Liquidity & Volatility:\n- Rationale:\n- Short Selling Setup:\n\n"
        "Example (format only):\n"
        "- Ticker & Name: AAPL - Apple Inc.\n- Entry Price: 221.50 - 222.20\n- Exit Price: 224.80 - 225.50\n- Stop-Loss: 220.40\n- Risk-Reward Ratio: 1:3\n"
        "- Indicators & Patterns: Above VWAP; 20/50 SMA uptrend; RSI 58\n- Sentiment & News: Positive news flow; no earnings today\n- Liquidity & Volatility: >50M avg vol; intraday range >1.2%\n- Rationale: Pullback to VWAP in uptrend with momentum\n- Short Selling Setup: If breaks 220 with volume, target 218\n\n"
        "Now produce 2-3 ideas for today using the exact labels above.\n"
        "Finally, summarize the Top 2–3 strongest trade opportunities for today:"
    )


if __name__ == "__main__":
    setup_logging()
    logging.info("Starting Day Trading Assistant run…")

    prompt = build_prompt()
    generated = run_local_gpt2_prompt(prompt)
    # Print to stdout for interactive runs and logs
    print(generated)

    rows, summary = parse_recommendations(generated)
    if not rows:
        logging.warning("Parser found no structured rows; writing summary-only CSV.")
    out_path = write_csv(rows, summary, CSV_FILE)
    logging.info("Done. CSV at: %s", os.path.abspath(out_path))

# AI Financial Toolkit

An end-to-end research workflow for extracting structured fundamentals from SEC
10-Q filings, calculating quarter-over-quarter deltas, and layering on LLM-based
analysis of revenue, cash flow, and debt narratives. The repository combines
scripted data collection utilities with LangGraph-powered review agents so you
can build repeatable fundamental research pipelines.

## Contents

| File | Description |
| --- | --- |
| `facts.py` | Batch parser that loads cached SEC company facts and generates quarterly EPS, operating cash flow, and revenue JSON summaries for every ticker in `company_tickers.json`. |
| `facts_lookup.py` | Interactive helper that fetches a single ticker directly from the SEC XBRL API, producing the same EPS/Cash/Revenue summaries as `facts.py`. |
| `deltas.py` | Consumes the derived facts JSON and compares Q1 2025 vs Q4 2024 deltas for EPS, cash, revenue, and daily price aggregates using the Polygon `massive` REST client. Also filters out anomalous rows. |
| `orgvsinorg.py` | LangGraph workflow that ingests Item 2 from a 10-Q filing (either cached or freshly downloaded) and produces LLM-audited revenue and cash-flow assessments, saving validated JSON reports per filing date. |
| `toolsmod.py` | Utility helpers (EDGAR fetchers, cache readers) that power the LangGraph workflow. |

## Prerequisites

- Python 3.11+
- `pip` for dependency installation
- SEC-friendly User-Agent string (already embedded but customize if needed)
- API credentials:
  - [Polygon.io](https://polygon.io/) API key for `massive.RESTClient` (used in `deltas.py`)
  - OpenAI API key (`OPENAI_API_KEY`) for analysis models
  - Google Generative AI API key (`GOOGLE_API_KEY`) for the Gemini judge

Store the API keys in a `.env` file or export them as environment variables.

```
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Folder Structure & Outputs

```
output/
  <ticker>-facts-json/
    full_<ticker>.json      # Raw SEC facts payload (if cached)
    epsd_<ticker>.json      # Derived EPS quarterly data
    cash_<ticker>.json      # Derived operating cash flow data
    rev_<ticker>.json       # Derived revenue data
  <ticker>/<filing-date>/
    revenue_<date>.json     # LLM revenue analysis
    cashflow_<date>.json    # LLM cashflow analysis
    debt_<date>.json        # (reserved for future modules)
```

The `facts.py` and `facts_lookup.py` scripts populate the `*-facts-json`
directories, while `orgvsinorg.py` writes the per-filing analysis folders.

## Usage

### 1. Generate Derived Metrics (`facts.py`)

1. Ensure `output/<ticker>-facts-json/full_<ticker>.json` exists for each ticker
   you care about. (Populate by running `facts_lookup.py` manually or writing a
   fetcher that stores the raw SEC payloads.)
2. Run the batch parser:

   ```bash
   python facts.py
   ```

   The script iterates over every ticker in
   `https://www.sec.gov/files/company_tickers.json`, loads the cached `full_*.json`,
   extracts EPS, cash flow, and revenue sequences for 2022–2025, and writes
   normalized JSON summaries under `output/<ticker>-facts-json/`.

### 2. Spot-check a Single Ticker (`facts_lookup.py`)

Use this when you need to refresh one company’s facts:

```bash
python facts_lookup.py
# enter ticker: msft
```

The script pulls the live SEC XBRL feed, builds the quarterly metric JSON, and
writes it to `output/msft-facts-json/`.

### 3. Compute Financial Deltas (`deltas.py`)

1. Confirm the `output/<ticker>-facts-json/epsd_*.json`, `cash_*.json`, and
   `rev_*.json` files exist.
2. Provide a Polygon API key to the `RESTClient` initializer.
3. Run:

   ```bash
   python deltas.py
   ```

`deltas.py` loads the derived metrics, matches them to Polygon grouped daily
aggregates (e.g., 2025-02-28 vs 2025-05-30), and builds `delta_eps`, `delta_cash`,
`delta_rev`, and price change arrays. The helper `clean_rows` removes rows with
`NAN`, `None`, NaN floats, or values with absolute magnitude over 1e12 so the
output arrays are ready for plotting or modeling.

### 4. LLM Revenue & Cashflow Analysis (`orgvsinorg.py`)

The LangGraph workflow guides you through:

1. **Fetching Item 2** – choose between cached filings (`cache_fetcher`) or live
   EDGAR pulls (`edgar_fetcher`). Both return `[ticker, cik, filing_date]` plus
   the Item 2 text.
2. **Revenue Agent** – prompts the OpenAI model to produce a structured JSON
   summary (drivers, organic vs. inorganic streams) and stores it as
   `revenue_<date>.json` once the Gemini judge validates the output.
3. **Cashflow Agent** – mirrors the above for operating cash flow narratives.
4. **Judging & Persistence** – if a judge returns `pass`, the JSON is saved under
   `output/<ticker>/<filing-date>/`. `fail` responses print anomalies for manual
   review so you can re-run after adjusting prompts or data.

Run the workflow:

```bash
python orgvsinorg.py
```

You will be prompted for cache vs. live mode and, if the `.env` file is missing,
for API keys via the console.

## Extending the Toolkit

- Add more derived metrics (margins, debt) by following the `facts.py` pattern
  and writing additional `*-llm` / `gemini_judge_*` functions.
- Pipe the cleaned deltas into scikit-learn models or visualization notebooks.
- Automate the raw SEC download step (currently implied) so `facts.py` can run
  fully unattended.

## License

This project currently has no explicit license. Add one before distributing or
running in production.

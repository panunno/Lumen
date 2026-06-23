# Lumen

A personal, beginner-friendly investing dashboard built with Streamlit. Look up stocks,
ETFs, and mutual funds; grade them; track a portfolio and watchlist; backtest strategies;
and keep an eye on the bond market and the economy — all in one place.

> **Educational tool, not financial advice.** Everything in Lumen is computed from public
> data using simple rules. Signals and grades can be wrong, and data can be delayed. Always
> do your own research before investing.

---

## Running Lumen

1. Make sure the required libraries are installed (one time):
   ```
   pip install -r requirements.txt
   ```
2. Start the app from this folder:
   ```
   streamlit run app.py
   ```
   …or just double-click **`run_dashboard.bat`** on Windows.
3. Lumen opens in your browser. To stop it, press `Ctrl + C` in the terminal (or close the
   black window the .bat file opened).

If `streamlit` or `python` "isn't recognized," they may not be on your PATH — use the full
path to the Python interpreter, e.g. the `Scripts\streamlit.exe` inside your Python install.

---

## The pages

- **Overview** — your portfolio snapshot plus key market & economy signals at a glance.
- **Ticker Lookup** — fundamentals, a 1-year price chart with moving averages, risk stats,
  a Buy/Hold/Sell signal, and recent news for any stock or ETF.
- **Grade & Value** — an A–F scorecard (with the "why"), a discounted-cash-flow fair value,
  return scenarios, a Monte Carlo simulation, and analyst/earnings info.
- **Compare** — put 2–5 tickers side by side: full metrics table (best value highlighted),
  grade, signal, category breakdown, returns, a price race, and CSV export.
- **Discover** — surfaces under-the-radar stocks with a data-driven Buy/Sell signal.
- **Watchlist** — saved candidate tickers, auto-graded, with notes.
- **Alerts** — in-app rules (price, daily move %, signal) checked when you open or refresh.
- **Earnings** — upcoming earnings dates for your portfolio and watchlist tickers.
- **Portfolio Tracker** — your holdings, valued live, with allocation and diversification.
- **Backtester** — test moving-average or RSI strategies vs. buy & hold and a benchmark.
- **Bonds** — Treasury yield curve, the yield-curve spread, and common bond ETFs.
- **Mutual Funds** — fund fees, ratings, and returns.
- **Macro Data** — key economic indicators from the Federal Reserve (FRED).
- **Glossary** — plain-English definitions of every term used in Lumen.

---

## Your data

Lumen saves your records to plain CSV files in this folder:

- `portfolio.csv` — your holdings
- `watchlist.csv` — your watchlist
- `alerts.csv` — your alert rules

These hold **your personal data** and are excluded from Git by `.gitignore`. If you ever
share the folder directly, delete these files first. You can also back them up from inside
the app using the Download buttons on the Portfolio and Watchlist pages.

## Data sources

- **yfinance** (Yahoo Finance) — stock/ETF/fund prices and fundamentals (no API key).
- **FRED** (Federal Reserve) — macro indicators and Treasury yields, via public CSV (no key).

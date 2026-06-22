"""
=========================================================
SIMPLE STOCK/ETF DASHBOARD
=========================================================
This app has five pages, chosen from the menu on the left:
  1) TICKER LOOKUP - type a ticker and see fundamentals +
     a 1-year price chart with 50-day and 200-day moving averages
  2) PORTFOLIO TRACKER - enter your holdings (ticker, shares,
     cost basis) and see your current value, gain/loss, and
     how your money is split across positions
  3) SCREENER - compare several tickers side-by-side on the
     same fundamental and performance metrics
  4) BACKTESTER - test a simple moving-average crossover
     trading rule on historical data, see risk stats, and
     compare it to buy & hold and a benchmark of your choice
  5) MACRO DATA - key economic indicators (inflation,
     unemployment, interest rates, Treasury yield) from the
     Federal Reserve's public FRED database

Everything below is organized into clearly labeled sections.
"""

# ---------------------------------------------------------
# SECTION 1: IMPORTS
# These lines load the external libraries we need.
# - streamlit: builds the web page/dashboard
# - yfinance: downloads stock data for free from Yahoo Finance
# - pandas / numpy: organize the data and do the math
# - plotly.graph_objects / plotly.express: draw the interactive charts
# - os: lets us check whether a file (our saved portfolio) exists
# ---------------------------------------------------------
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
from datetime import datetime
from streamlit_option_menu import option_menu


# ---------------------------------------------------------
# SECTION 2: PAGE SETUP
# This sets the browser tab title and makes the page use the
# full width of the screen instead of a narrow column.
# ---------------------------------------------------------
st.set_page_config(
    page_title="Lumen",
    page_icon="favicon.png" if os.path.exists("favicon.png") else None,
    layout="wide",
)

# -------------------------------------------------------------
# "SLEEK DARK FINTECH" THEME (Concept A)
# Custom CSS turns Streamlit's default metrics into rounded
# cards, refines spacing/typography, and gives buttons and the
# sidebar a more premium feel. The accent color is one blue.
# -------------------------------------------------------------
ACCENT = "#5a8fc2"          # cooler muted steel-blue — subtle, professional
CARD_BG = "#11151d"         # deep, understated card surface
CARD_BORDER = "rgba(255,255,255,0.05)"

st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 2.6rem; padding-bottom: 3rem; }}

      /* Turn each metric into a rounded card */
      [data-testid="stMetric"] {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 14px 16px;
      }}
      [data-testid="stMetricValue"] {{ font-size: 1.45rem; font-weight: 500; }}
      [data-testid="stMetricLabel"] {{ opacity: 0.75; }}
      /* Make the up/down delta pop a little more */
      [data-testid="stMetricDelta"] {{ font-weight: 600; }}

      /* Data tables: same rounded, bordered card treatment */
      [data-testid="stDataFrame"], [data-testid="stTable"] {{
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        overflow: hidden;
      }}

      /* Headers & spacing */
      h1, h2, h3 {{ letter-spacing: 0.2px; }}
      h2 {{ margin-top: 0.6rem; }}
      h3 {{ margin-top: 0.3rem; }}
      hr {{ margin: 0.9rem 0 1.3rem 0; border-color: {CARD_BORDER}; }}

      /* Buttons: subtle accent */
      .stButton > button {{
        border-radius: 9px;
        border: 1px solid {CARD_BORDER};
        font-weight: 500;
      }}
      .stButton > button:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}

      /* Inputs a touch rounder */
      [data-baseweb="input"], [data-baseweb="select"] {{ border-radius: 9px; }}

      /* Sidebar a hair darker for separation */
      [data-testid="stSidebar"] {{ background: #0b0f16; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------
# (The branded header now lives in the sidebar — see below.)

# A single shared ticker remembered across pages (Ticker Lookup
# and Grade & Value reuse it), plus a timestamp for when data
# was last refreshed.
st.session_state.setdefault("shared_ticker", "AAPL")
st.session_state.setdefault("data_refreshed_at", datetime.now())

# The name of the file where we save your portfolio holdings.
# It lives in the same folder as this app, so it's easy to find.
PORTFOLIO_FILE = "portfolio.csv"

# These are the column names every portfolio table will use.
PORTFOLIO_COLUMNS = ["Ticker", "Shares", "Cost Basis Per Share"]

# The watchlist (candidate investments) is saved here.
WATCHLIST_FILE = "watchlist.csv"
WATCHLIST_COLUMNS = ["Ticker", "Notes"]

# Price/move/signal alert rules are saved here.
ALERTS_FILE = "alerts.csv"
ALERTS_COLUMNS = ["Ticker", "Condition", "Value"]
ALERT_CONDITIONS = ["Price above", "Price below", "Daily move % above", "Signal is"]


# -------------------------------------------------------------
# MULTI-USER MODE
# Locally, Lumen saves your data to CSV files and reloads it
# automatically (convenient for one person). When PUBLISHED for
# others, we DON'T want one visitor's data shown to the next, so
# each visitor's data lives only in their browser session and is
# kept via Download/Upload buttons.
#
# This is controlled by a Streamlit "secret" you set ONLY on the
# cloud: add a line  MULTIUSER = "true"  in the app's Secrets.
# With no secret (i.e. locally), it stays in single-user file mode.
# -------------------------------------------------------------
def _detect_multiuser():
    try:
        return str(st.secrets.get("MULTIUSER", "")).strip().lower() == "true"
    except Exception:
        return False


MULTIUSER = _detect_multiuser()

# A consistent color palette so every chart looks the same.
# Muted, understated tones to match the subtle dark theme.
COLOR_PRIMARY = "#5a8fc2"   # cool steel blue - main line (price, strategy)
COLOR_ACCENT = "#d9a05b"    # muted amber - 50-day MA / secondary line
COLOR_GREEN = "#5fae8a"     # muted green - 200-day MA / positive
COLOR_GRAY = "#8a909a"      # gray       - buy & hold reference line
COLOR_PURPLE = "#9b86c4"    # muted violet - benchmark line


# ---------------------------------------------------------
# SECTION 3: A HELPER THAT GIVES EVERY CHART THE DARK LOOK
# Instead of repeating the same styling on every chart, we
# define it once here and call it on each figure. It makes
# the chart background transparent (so it blends into the
# dark page) and sets readable text/grid colors.
# ---------------------------------------------------------
def style_chart(fig, height=500, yaxis_title="", xaxis_title="Date",
                y_dollar=False, y_percent=False):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",   # transparent outer background
        plot_bgcolor="rgba(0,0,0,0)",    # transparent plotting area
        height=height,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        font=dict(color="#e6e6e6"),
        # Unified hover: one tidy tooltip box for all series at a point.
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#11151d", bordercolor="rgba(255,255,255,0.12)",
                        font=dict(color="#e8eaed", size=12)),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.08)", showspikes=False)
    # Format the y-axis as dollars or percentages when asked.
    if y_dollar:
        fig.update_yaxes(tickprefix="$", tickformat=",.0f", gridcolor="rgba(255,255,255,0.08)")
    elif y_percent:
        fig.update_yaxes(ticksuffix="%", gridcolor="rgba(255,255,255,0.08)")
    else:
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
    return fig


# ---------------------------------------------------------
# SECTION 4: HELPER FUNCTION TO FETCH STOCK DATA
# This function does the actual work of talking to Yahoo Finance.
# It is wrapped in a "cache" so that if you look up the same
# ticker again soon, the app doesn't have to re-download
# everything (it loads faster).
#
# It returns three things:
#   - info: a dictionary of company facts (name, sector, etc.)
#   - history: a table of daily prices for the past year
#   - error: a message if something went wrong, otherwise None
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_stock_data(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period="1y")

        # If Yahoo Finance has no data for this ticker, treat it as invalid.
        if history.empty or not info or info.get("regularMarketPrice") is None:
            return None, None, (
                f"Couldn't find '{ticker}'. Double-check the ticker symbol — for example, "
                "AAPL (Apple), MSFT (Microsoft), or VOO (an ETF). Mutual funds go on the Mutual Funds page."
            )

        return info, history, None
    except Exception:
        return None, None, (
            f"Couldn't load data for '{ticker}' right now. This is usually a temporary network "
            "hiccup with Yahoo Finance — wait a moment and try again."
        )


# ---------------------------------------------------------
# SECTION 5: HELPER FUNCTION TO GET JUST THE CURRENT PRICE
# Used by the Portfolio Tracker page to value each holding.
# Kept separate (and cached for a shorter time) because the
# portfolio page only needs the latest price, not a full year
# of history.
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_current_price(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info.get("lastPrice")
        if price is None:
            # Fallback in case fast_info doesn't have it
            price = stock.history(period="1d")["Close"].iloc[-1]
        return float(price)
    except Exception:
        return None


# ---------------------------------------------------------
# MUTUAL FUND DATA HELPER
# Mutual funds don't have a normal "regularMarketPrice" the way
# stocks do, so we fetch them separately and validate on the
# price history instead. Returns (info, 5-year history, error).
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_fund_data(ticker: str):
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        history = tk.history(period="5y")
        if history.empty or not info:
            return None, None, (
                f"Couldn't find '{ticker}'. Check the fund symbol — most mutual funds are 5 letters "
                "ending in X, like VFIAX, FXAIX, or FCNTX."
            )
        return info, history, None
    except Exception:
        return None, None, (
            f"Couldn't load '{ticker}' right now. This is usually a temporary network hiccup — "
            "wait a moment and try again."
        )


# ---------------------------------------------------------
# RECENT NEWS HELPER
# Pulls recent headlines for a ticker. Newer yfinance nests the
# real fields under each item's "content" key, so we dig in and
# return a tidy list of {title, publisher, date, url}.
# ---------------------------------------------------------
@st.cache_data(ttl=1800)
def get_news(ticker: str, limit: int = 8):
    try:
        raw = yf.Ticker(ticker).news or []
        items = []
        for it in raw[:limit]:
            c = it.get("content", it)
            url_field = c.get("canonicalUrl") or c.get("clickThroughUrl") or {}
            url = url_field.get("url") if isinstance(url_field, dict) else c.get("link")
            provider = c.get("provider")
            publisher = provider.get("displayName") if isinstance(provider, dict) else c.get("publisher")
            items.append({
                "title": c.get("title") or "(untitled)",
                "publisher": publisher or "",
                "date": (c.get("pubDate") or "")[:10],
                "url": url or "",
            })
        return items
    except Exception:
        return []


def show_news(ticker: str):
    """Render a ticker's recent headlines as clickable links."""
    news = get_news(ticker)
    if not news:
        st.caption("No recent news available for this ticker.")
        return
    for n in news:
        meta = " · ".join([p for p in [n["publisher"], n["date"]] if p])
        if n["url"]:
            st.markdown(
                f"- [{n['title']}]({n['url']})  \n"
                f"  <span style='opacity:0.55;font-size:0.85em'>{meta}</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"- {n['title']}  \n  <span style='opacity:0.55;font-size:0.85em'>{meta}</span>",
                        unsafe_allow_html=True)


# ---------------------------------------------------------
# ADD-TO-WATCHLIST HELPER
# Appends new tickers to watchlist.csv (skipping any already
# there) and keeps the live session copy in sync. Returns how
# many were newly added.
# ---------------------------------------------------------
def add_tickers_to_watchlist(tickers):
    # Start from the live session watchlist if present, else the
    # saved file (single-user mode only), else empty.
    if "watchlist_df" in st.session_state:
        existing = st.session_state.watchlist_df.copy()
    elif not MULTIUSER and os.path.exists(WATCHLIST_FILE):
        existing = pd.read_csv(WATCHLIST_FILE)
    else:
        existing = pd.DataFrame(columns=WATCHLIST_COLUMNS)

    have = set(existing["Ticker"].astype(str).str.upper()) if "Ticker" in existing.columns and not existing.empty else set()
    new_rows = [{"Ticker": t, "Notes": ""} for t in tickers if t.upper() not in have]
    if not new_rows:
        return 0

    updated = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    st.session_state.watchlist_df = updated
    # Only persist to the shared file when running locally (single user).
    if not MULTIUSER:
        updated.to_csv(WATCHLIST_FILE, index=False)
    return len(new_rows)


# ---------------------------------------------------------
# RICHER QUOTE HELPER FOR THE PORTFOLIO TRACKER
# Returns the current price PLUS the previous close (so we can
# show today's change), the sector, and the dividend yield.
# Returns None if the ticker can't be found.
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_portfolio_quote(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        fast = stock.fast_info
        price = fast.get("lastPrice")
        prev_close = fast.get("previousClose")
        if price is None:
            price = stock.history(period="1d")["Close"].iloc[-1]

        # .info is slower, so we only reach for the extras it provides.
        info = stock.info
        sector = info.get("sector", "Other / ETF")
        dividend_yield = info.get("dividendYield", 0) or 0

        return {
            "price": float(price),
            "prev_close": float(prev_close) if prev_close else float(price),
            "sector": sector if sector else "Other / ETF",
            "dividend_yield": float(dividend_yield),
        }
    except Exception:
        return None


# ---------------------------------------------------------
# SECTION 6: SMALL FORMATTING HELPER
# Turns large numbers into easy-to-read text, e.g.
# 2500000000000 -> "$2.50T"
# ---------------------------------------------------------
def format_market_cap(value):
    if value is None:
        return "N/A"
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    elif value >= 1e9:
        return f"${value / 1e9:.2f}B"
    elif value >= 1e6:
        return f"${value / 1e6:.2f}M"
    else:
        return f"${value:,.0f}"


# ---------------------------------------------------------
# A FEW MORE SMALL FORMATTING HELPERS
# These safely turn raw numbers into readable text and show
# "N/A" instead of crashing when a value is missing (common
# for ETFs and some stocks).
#   fmt_ratio   -> plain number like a P/E ("28.43")
#   fmt_decimal_pct -> a fraction like 0.21 shown as "21.00%"
#   fmt_dollar_big  -> large dollar amounts using T/B/M
# ---------------------------------------------------------
def fmt_ratio(value):
    return f"{value:.2f}" if value is not None and pd.notna(value) else "N/A"


def fmt_decimal_pct(value):
    return f"{value * 100:.2f}%" if value is not None and pd.notna(value) else "N/A"


def fmt_price(value):
    # A dollar amount with cents, or "N/A" when missing.
    return f"${value:,.2f}" if value is not None and pd.notna(value) else "N/A"


# ---------------------------------------------------------
# SHARED HELPER: A CONSISTENT "NOTHING HERE YET" MESSAGE
# Every page uses this so empty states look and read the same.
# ---------------------------------------------------------
def empty_state(message):
    st.info(message)


def fmt_dollar_big(value):
    # Reuse the market-cap formatter; it already handles T/B/M
    # and also negative values (e.g. negative free cash flow).
    if value is None or not pd.notna(value):
        return "N/A"
    negative = value < 0
    text = format_market_cap(abs(value))
    return f"-{text}" if negative else text


# ---------------------------------------------------------
# SHARED HELPER: LOAD THE SAVED PORTFOLIO HOLDINGS
# The Overview page and the Screener both need to know what
# you own. This reads the holdings from the live session if
# you've been editing them, otherwise from the saved CSV file,
# and cleans up the tickers. Returns an empty table if there's
# nothing saved yet.
# ---------------------------------------------------------
def load_portfolio_holdings():
    try:
        if "portfolio_df" in st.session_state:
            df = st.session_state.portfolio_df.copy()
        elif not MULTIUSER and os.path.exists(PORTFOLIO_FILE):
            df = pd.read_csv(PORTFOLIO_FILE)
        else:
            return pd.DataFrame(columns=PORTFOLIO_COLUMNS)

        if "Ticker" not in df.columns:
            return pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        df = df.dropna(subset=["Ticker"]).copy()
        df = df[df["Ticker"].astype(str).str.strip() != ""]
        if df.empty:
            return pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
        df["Shares"] = pd.to_numeric(df.get("Shares"), errors="coerce").fillna(0)
        if "Cost Basis Per Share" in df.columns:
            df["Cost Basis Per Share"] = pd.to_numeric(df["Cost Basis Per Share"], errors="coerce").fillna(0)
        return df
    except Exception:
        # A corrupted or unreadable file shouldn't crash the app.
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)


# ---------------------------------------------------------
# SHARED HELPER: FETCH ONE DATA SERIES FROM FRED
# FRED (the Federal Reserve's free database) lets anyone
# download a series as a plain CSV with no API key. Used by
# both the Overview page and the Macro Data page. Cached for
# a day since economic data updates slowly.
# ---------------------------------------------------------
@st.cache_data(ttl=86400)
def get_fred_series(series_code: str, years_back: int = 10):
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_code}"
        data = pd.read_csv(url, parse_dates=["observation_date"], index_col="observation_date")
        data[series_code] = pd.to_numeric(data[series_code], errors="coerce")
        data = data.dropna()
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=365 * years_back)
        data = data[data.index >= cutoff]
        if data.empty:
            return None, f"No recent data returned for '{series_code}'."
        return data, None
    except Exception as e:
        return None, f"Couldn't fetch data for '{series_code}': {e}"


# ---------------------------------------------------------
# SHARED HELPER: SCORE A SINGLE METRIC FROM 0 TO 100
# Given a value plus a "good" anchor (scores 100) and a "bad"
# anchor (scores 0), we interpolate linearly in between and
# clamp to 0-100. This works for both "higher is better"
# (good > bad, e.g. ROE) and "lower is better" (good < bad,
# e.g. P/E) just by how you set the anchors. Missing data
# returns None so it can be skipped.
# ---------------------------------------------------------
def linear_score(value, good, bad):
    if value is None or not pd.notna(value) or good == bad:
        return None
    score = (value - bad) / (good - bad) * 100
    return max(0.0, min(100.0, score))


def _avg(scores):
    """Average a list of scores, ignoring any that are None."""
    vals = [s for s in scores if s is not None]
    return sum(vals) / len(vals) if vals else None


def score_to_letter(score):
    """Turn a 0-100 score into a letter grade."""
    if score is None:
        return "N/A"
    if score >= 90: return "A+"
    if score >= 85: return "A"
    if score >= 80: return "A-"
    if score >= 75: return "B+"
    if score >= 70: return "B"
    if score >= 65: return "B-"
    if score >= 60: return "C+"
    if score >= 55: return "C"
    if score >= 50: return "C-"
    if score >= 45: return "D+"
    if score >= 40: return "D"
    return "F"


# ---------------------------------------------------------
# SHARED HELPER: GRADE A STOCK ACROSS FIVE CATEGORIES
# Returns (category_scores, overall_score, details) where
# details[category] is a list of (label, formatted_value, score)
# so the Grade page can show exactly which metrics drove each
# category. Balanced weighting = categories count equally.
# ---------------------------------------------------------
def grade_stock(info, history):
    # Precompute the momentum inputs from price history.
    ma200_pct = yr_ret = off_high = None
    if history is not None and not history.empty:
        price = history["Close"].iloc[-1]
        ma200 = history["Close"].rolling(200).mean().iloc[-1]
        if pd.notna(ma200):
            ma200_pct = price / ma200 - 1
        yr_ret = price / history["Close"].iloc[0] - 1
        wk_high = info.get("fiftyTwoWeekHigh")
        if wk_high:
            off_high = (price - wk_high) / wk_high

    fcf = info.get("freeCashflow")
    fcf_score = (100 if fcf and fcf > 0 else 0) if fcf is not None else None

    # (category, label, value, good_anchor, bad_anchor, kind)
    specs = [
        ("Valuation", "Trailing P/E", info.get("trailingPE"), 12, 40, "ratio"),
        ("Valuation", "Forward P/E", info.get("forwardPE"), 12, 35, "ratio"),
        ("Valuation", "Price/Book", info.get("priceToBook"), 1.5, 10, "ratio"),
        ("Valuation", "Price/Sales", info.get("priceToSalesTrailing12Months"), 1, 12, "ratio"),
        ("Valuation", "PEG Ratio", info.get("trailingPegRatio"), 1, 3, "ratio"),
        ("Profitability", "Profit Margin", info.get("profitMargins"), 0.25, 0, "pct"),
        ("Profitability", "Return on Equity", info.get("returnOnEquity"), 0.25, 0, "pct"),
        ("Profitability", "Operating Margin", info.get("operatingMargins"), 0.25, 0, "pct"),
        ("Growth", "Revenue Growth", info.get("revenueGrowth"), 0.20, -0.05, "pct"),
        ("Growth", "Earnings Growth", info.get("earningsGrowth"), 0.20, -0.10, "pct"),
        ("Financial Health", "Debt/Equity", info.get("debtToEquity"), 20, 200, "ratio"),
        ("Financial Health", "Current Ratio", info.get("currentRatio"), 2.5, 1, "ratio"),
        ("Momentum", "Price vs. 200-day MA", ma200_pct, 0.15, -0.20, "pct"),
        ("Momentum", "1-Year Return", yr_ret, 0.30, -0.20, "pct"),
        ("Momentum", "% Off 52-wk High", off_high, 0, -0.40, "pct"),
    ]

    order = ["Valuation", "Profitability", "Growth", "Financial Health", "Momentum"]
    buckets = {cat: [] for cat in order}

    for cat, label, value, good, bad, kind in specs:
        score = linear_score(value, good, bad)
        if kind == "pct":
            shown = fmt_decimal_pct(value)
        else:
            shown = fmt_ratio(value)
        buckets[cat].append((label, shown, score))

    # Free-cash-flow positivity is a yes/no health check.
    buckets["Financial Health"].append((
        "Positive Free Cash Flow",
        "Yes" if (fcf and fcf > 0) else ("No" if fcf is not None else "N/A"),
        fcf_score,
    ))

    cats = {}
    details = {}
    for cat in order:
        rows = buckets[cat]
        cats[cat] = _avg([r[2] for r in rows])
        details[cat] = rows

    overall = _avg(list(cats.values()))
    return cats, overall, details


# ---------------------------------------------------------
# SHARED HELPER: RENDER A GRADE BREAKDOWN
# Shows each category's metrics with a colored dot indicating
# whether each helped (🟢), was so-so (🟡), hurt (🔴), or was
# missing (⚪). Used by both Grade & Value and the Watchlist.
# ---------------------------------------------------------
def show_grade_breakdown(cats, details):
    for cat_name, rows in details.items():
        cat_score = cats.get(cat_name)
        header = f"{cat_name} — {score_to_letter(cat_score)}"
        header += f" ({cat_score:.0f}/100)" if cat_score is not None else " (N/A)"
        st.markdown(f"**{header}**")
        for label, shown, sub in rows:
            if sub is None:
                color = "#8a909a"
            elif sub >= 66:
                color = "#5fae8a"
            elif sub >= 40:
                color = "#d9a05b"
            else:
                color = "#cf6b6b"
            dot = f"<span style='color:{color}'>&#9679;</span>"
            sub_txt = f"{sub:.0f}/100" if sub is not None else "no data"
            st.markdown(
                f"&nbsp;&nbsp;{dot} **{label}**: {shown} &nbsp;·&nbsp; "
                f"<span style='opacity:0.6'>{sub_txt}</span>",
                unsafe_allow_html=True,
            )
        st.markdown("")


# ---------------------------------------------------------
# SHARED HELPER: PER-STOCK RISK STATS
# From a price history, compute annualized volatility, the
# Sharpe ratio (return per unit of risk), and max drawdown
# (worst peak-to-trough drop). Returns None if not enough data.
# ---------------------------------------------------------
def stock_risk_stats(history):
    if history is None or history.empty:
        return None
    rets = history["Close"].pct_change().dropna()
    if rets.empty or rets.std() == 0:
        return None
    volatility = rets.std() * np.sqrt(252) * 100
    sharpe = (rets.mean() / rets.std()) * np.sqrt(252)
    cumulative = (1 + rets).cumprod()
    max_drawdown = (cumulative / cumulative.cummax() - 1).min() * 100
    return volatility, sharpe, max_drawdown


# ---------------------------------------------------------
# SHARED HELPER: BUY / SELL SIGNAL
# Blends four ingredients into one 0-100 "buy score":
#   1) our overall A-F grade
#   2) analyst price-target upside vs. today's price
#   3) analyst consensus rating (1 = strong buy ... 5 = sell)
#   4) price momentum (price vs. its 200-day average)
# The score then maps to a Strong Buy -> Strong Sell label.
# This is a data-driven signal for learning, NOT advice.
# ---------------------------------------------------------
def buy_sell_signal(info, overall_score, history):
    parts = []
    comps = []  # (name, shown_value, subscore) — the "why" behind the signal

    if overall_score is not None:
        parts.append(overall_score)
        comps.append(("Overall grade", score_to_letter(overall_score), overall_score))

    price = history["Close"].iloc[-1] if history is not None and not history.empty else None
    target = info.get("targetMeanPrice")
    if price and target:
        upside = target / price - 1
        s = linear_score(upside, good=0.30, bad=-0.10)
        parts.append(s)
        comps.append(("Analyst price-target upside", f"{upside * 100:+.1f}%", s))

    rec_mean = info.get("recommendationMean")  # 1 best, 5 worst
    if rec_mean:
        s = linear_score(rec_mean, good=1, bad=5)
        parts.append(s)
        comps.append(("Analyst consensus", f"{rec_mean:.1f}/5 (1=buy, 5=sell)", s))

    if price is not None:
        ma200 = history["Close"].rolling(200).mean().iloc[-1]
        if pd.notna(ma200):
            s = linear_score(price / ma200 - 1, good=0.15, bad=-0.20)
            parts.append(s)
            comps.append(("Momentum vs. 200-day avg", f"{(price / ma200 - 1) * 100:+.1f}%", s))

    score = _avg(parts)
    if score is None:
        return None, "N/A", comps
    if score >= 75:
        label = "Strong Buy"
    elif score >= 60:
        label = "Buy"
    elif score >= 45:
        label = "Hold"
    elif score >= 30:
        label = "Sell"
    else:
        label = "Strong Sell"
    return score, label, comps


# Colors for each signal label, reused by badges and tables.
SIGNAL_COLORS = {
    "Strong Buy": "#5fae8a", "Buy": "#7fae5f", "Hold": "#d9a05b",
    "Sell": "#cf8a6b", "Strong Sell": "#cf6b6b", "N/A": "#8a909a",
}


# ---------------------------------------------------------
# SHARED HELPER: RENDER THE BUY/SELL SIGNAL BADGE + "WHY"
# Shows a colored pill with the signal label and score, plus an
# expander breaking down the four inputs that produced it.
# ---------------------------------------------------------
def show_signal(info, history, overall_score):
    score, label, comps = buy_sell_signal(info, overall_score, history)
    if score is None:
        return
    color = SIGNAL_COLORS.get(label, "#8a909a")
    st.markdown(
        f"<div style='display:inline-flex; align-items:center; gap:10px; "
        f"background:#11151d; border:1px solid {color}; border-radius:10px; "
        f"padding:8px 14px; margin:2px 0 6px;'>"
        f"<span style='font-size:12px; color:#8b93a1;'>SIGNAL</span>"
        f"<span style='font-size:18px; font-weight:700; color:{color};'>{label}</span>"
        f"<span style='font-size:12px; color:#8b93a1;'>· score {score:.0f}/100</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    with st.expander("Why this signal?"):
        for name, shown, sub in comps:
            if sub is None:
                dot_color = "#8a909a"
            elif sub >= 66:
                dot_color = "#5fae8a"
            elif sub >= 40:
                dot_color = "#d9a05b"
            else:
                dot_color = "#cf6b6b"
            dot = f"<span style='color:{dot_color}'>&#9679;</span>"
            sub_txt = f"{sub:.0f}/100" if sub is not None else "no data"
            st.markdown(
                f"{dot} **{name}**: {shown} &nbsp;·&nbsp; <span style='opacity:0.6'>{sub_txt}</span>",
                unsafe_allow_html=True,
            )
        st.caption("A blended, data-driven signal for research — not financial advice.")


# ---------------------------------------------------------
# SHARED HELPER: PULL SYMBOLS FROM A YAHOO PREDEFINED SCREEN
# Yahoo offers ready-made screens (e.g. small-cap gainers,
# undervalued growth). We grab the tickers from one, with the
# result cached for an hour. Returns a list of dicts; empty on
# any error so the page degrades gracefully.
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_screen_symbols(screen_key: str, count: int = 25):
    try:
        res = yf.screen(screen_key, count=count)
        quotes = res.get("quotes", []) if isinstance(res, dict) else []
        out = []
        for q in quotes:
            sym = q.get("symbol")
            if sym:
                out.append({
                    "symbol": sym,
                    "name": q.get("shortName") or q.get("longName") or sym,
                    "marketCap": q.get("marketCap"),
                })
        return out
    except Exception:
        return []


# ---------------------------------------------------------
# SHARED HELPER: SIMPLE DISCOUNTED-CASH-FLOW FAIR VALUE
# Projects free cash flow forward, discounts it back to today,
# adds a terminal value, subtracts net debt, and divides by
# shares to get an estimated value per share. Returns None when
# the needed inputs are missing or don't make sense (e.g. a
# company with negative free cash flow, or an ETF).
# ---------------------------------------------------------
def estimate_fair_value(info, growth, discount, years, terminal):
    fcf = info.get("freeCashflow")
    shares = info.get("sharesOutstanding")
    if not fcf or fcf <= 0 or not shares or discount <= terminal:
        return None

    present_value = 0.0
    cash_flow = fcf
    for year in range(1, years + 1):
        cash_flow *= (1 + growth)
        present_value += cash_flow / ((1 + discount) ** year)

    terminal_value = cash_flow * (1 + terminal) / (discount - terminal)
    present_value += terminal_value / ((1 + discount) ** years)

    net_debt = (info.get("totalDebt") or 0) - (info.get("totalCash") or 0)
    equity_value = present_value - net_debt
    return equity_value / shares if equity_value > 0 else None


# ---------------------------------------------------------
# SHARED HELPER: MONTE CARLO PRICE SIMULATION
# Uses the stock's own historical daily returns (average and
# bumpiness) to simulate many possible future price paths, then
# returns percentile bands over time plus the final-price spread.
# ---------------------------------------------------------
def monte_carlo_paths(history, days=252, simulations=500, seed=42):
    returns = history["Close"].pct_change().dropna()
    if returns.empty:
        return None
    mu, sigma = returns.mean(), returns.std()
    start_price = history["Close"].iloc[-1]

    rng = np.random.default_rng(seed)
    # shape: (days, simulations)
    shocks = rng.normal(mu, sigma, size=(days, simulations))
    paths = start_price * np.cumprod(1 + shocks, axis=0)
    return start_price, paths


# ---------------------------------------------------------
# SHARED HELPER: ANNUAL REVENUE & NET INCOME HISTORY
# Pulls the multi-year income statement so we can chart whether
# the business is actually growing. Cached; returns None if the
# data isn't available (common for ETFs).
# ---------------------------------------------------------
@st.cache_data(ttl=86400)
def get_financials(ticker: str):
    try:
        stmt = yf.Ticker(ticker).income_stmt
        if stmt is None or stmt.empty:
            return None
        wanted = {}
        for label in ["Total Revenue", "Net Income"]:
            if label in stmt.index:
                row = stmt.loc[label].dropna()
                wanted[label] = row
        if not wanted:
            return None
        return wanted
    except Exception:
        return None


# ---------------------------------------------------------
# SHARED HELPER: LOAD / SAVE THE WATCHLIST
# ---------------------------------------------------------
def load_watchlist():
    try:
        if not MULTIUSER and os.path.exists(WATCHLIST_FILE):
            df = pd.read_csv(WATCHLIST_FILE)
            if "Ticker" not in df.columns:
                return pd.DataFrame(columns=WATCHLIST_COLUMNS)
            return df
    except Exception:
        return pd.DataFrame(columns=WATCHLIST_COLUMNS)
    return pd.DataFrame([{"Ticker": "AAPL", "Notes": ""}], columns=WATCHLIST_COLUMNS)


# ---------------------------------------------------------
# SHARED HELPER: LOAD ALERT RULES
# ---------------------------------------------------------
def load_alerts():
    try:
        if not MULTIUSER and os.path.exists(ALERTS_FILE):
            df = pd.read_csv(ALERTS_FILE)
            if "Ticker" not in df.columns:
                return pd.DataFrame(columns=ALERTS_COLUMNS)
            return df
    except Exception:
        return pd.DataFrame(columns=ALERTS_COLUMNS)
    return pd.DataFrame(columns=ALERTS_COLUMNS)


# ---------------------------------------------------------
# SHARED HELPER: EVALUATE ALERT RULES AGAINST LIVE DATA
# Returns a list of plain-English messages for rules that are
# currently triggered. Uses cached data so repeated checks are
# fast. Price/move rules are cheap; "Signal is" rules also grade
# the stock, so they cost a little more.
# ---------------------------------------------------------
def evaluate_alerts():
    # Use the live (session) rules if the user has been editing them,
    # otherwise the saved rules (single-user mode).
    if "alerts_df" in st.session_state:
        rules = st.session_state.alerts_df
    else:
        rules = load_alerts()
    rules = rules.dropna(subset=["Ticker"]) if "Ticker" in rules.columns else rules
    triggered = []
    if rules.empty:
        return triggered

    for _, rule in rules.iterrows():
        ticker = str(rule.get("Ticker", "")).strip().upper()
        condition = str(rule.get("Condition", "")).strip()
        raw_value = rule.get("Value", "")
        if not ticker or not condition:
            continue

        quote = get_portfolio_quote(ticker)
        if quote is None:
            continue
        price = quote["price"]
        prev = quote["prev_close"]
        move = ((price - prev) / prev * 100) if prev else 0.0

        try:
            num_value = float(raw_value)
        except (TypeError, ValueError):
            num_value = None

        if condition == "Price above" and num_value is not None and price >= num_value:
            triggered.append(f"{ticker} is above ${num_value:,.2f} — now ${price:,.2f}")
        elif condition == "Price below" and num_value is not None and price <= num_value:
            triggered.append(f"{ticker} is below ${num_value:,.2f} — now ${price:,.2f}")
        elif condition == "Daily move % above" and num_value is not None and abs(move) >= num_value:
            triggered.append(f"{ticker} moved {move:+.1f}% today (over {num_value:.1f}%)")
        elif condition == "Signal is":
            info, history, error = get_stock_data(ticker)
            if not error and history is not None and not history.empty:
                _, overall, _ = grade_stock(info, history)
                _, label, _ = buy_sell_signal(info, overall, history)
                if label.strip().lower() == str(raw_value).strip().lower():
                    triggered.append(f"{ticker} signal is now {label}")
    return triggered


# ---------------------------------------------------------
# SECTION 7: SLEEK SIDEBAR NAVIGATION
# This uses the "option_menu" component to make a compact
# vertical menu of icons + labels on the left, instead of a
# big radio list. Each entry has a Bootstrap icon name.
# The page names (without icons) are what we check below to
# decide which page's code to run.
# ---------------------------------------------------------
PAGES = ["Overview", "Ticker Lookup", "Grade & Value", "Compare", "Discover", "Watchlist",
         "Alerts", "Portfolio Tracker", "Screener", "Backtester", "Bonds", "Mutual Funds",
         "Macro Data", "Glossary"]

with st.sidebar:
    # Brand header (logo + name + tagline) at the top of the sidebar.
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:11px; padding:2px 4px 14px;">
          <div style="width:42px; height:42px; border-radius:12px; background:{CARD_BG};
                      border:1px solid {CARD_BORDER}; display:flex; align-items:center;
                      justify-content:center; flex:0 0 auto;">
            <svg width="30" height="30" viewBox="0 0 64 64" aria-hidden="true">
              <path d="M18 43 A14 14 0 0 1 46 43 Z" fill="{ACCENT}"/>
              <g stroke="{ACCENT}" stroke-width="4.4" stroke-linecap="round">
                <line x1="11" y1="43" x2="53" y2="43"/>
                <line x1="32" y1="8" x2="32" y2="16"/>
                <line x1="15" y1="15" x2="20" y2="22"/>
                <line x1="49" y1="15" x2="44" y2="22"/>
                <line x1="7" y1="30" x2="14" y2="33"/>
                <line x1="57" y1="30" x2="50" y2="33"/>
              </g>
            </svg>
          </div>
          <div>
            <div style="font-size:20px; font-weight:700; color:#e8eaed; line-height:1.1; letter-spacing:0.5px;">Lumen</div>
            <div style="font-size:12px; color:#8b93a1;">Your personal market dashboard</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = option_menu(
        menu_title=None,                       # no title = more compact
        options=PAGES,
        icons=["house", "search", "clipboard-check", "arrow-left-right", "binoculars", "star",
               "bell", "briefcase", "table", "graph-up", "bank", "collection", "globe", "book"],  # Bootstrap icon names
        default_index=0,
        styles={
            "container": {"padding": "4px", "background-color": CARD_BG},
            "icon": {"color": ACCENT, "font-size": "16px"},
            "nav-link": {
                "font-size": "14px",
                "padding": "8px 10px",
                "margin": "2px 0",
                "color": "#e6e6e6",
                "--hover-color": "#222a36",
            },
            # When a tab is selected, force the accent background and
            # make BOTH the text and its icon white so they stay
            # clearly visible against the highlight.
            "nav-link-selected": {
                "background-color": ACCENT,
                "color": "#ffffff",
            },
            "nav-link-selected .icon": {"color": "#ffffff !important"},
        },
    )
    st.caption("A beginner-friendly investing dashboard.")

    st.divider()
    # Manual refresh: clears the cached data so the next loads
    # pull fresh numbers from Yahoo / FRED.
    if st.button("Refresh data"):
        st.cache_data.clear()
        st.session_state["data_refreshed_at"] = datetime.now()
        st.session_state.pop("alerts_checked", None)  # re-check alerts on refresh
        st.rerun()
    # Show how long ago data was last refreshed, in friendly terms.
    _elapsed_min = int((datetime.now() - st.session_state["data_refreshed_at"]).total_seconds() // 60)
    if _elapsed_min < 1:
        _rel = "just now"
    elif _elapsed_min == 1:
        _rel = "1 minute ago"
    elif _elapsed_min < 60:
        _rel = f"{_elapsed_min} minutes ago"
    else:
        _hrs = _elapsed_min // 60
        _rel = f"{_hrs} hour{'s' if _hrs > 1 else ''} ago"
    st.caption(f"Data updated {_rel}. Cached up to ~1 hour for speed.")


# -------------------------------------------------------------
# PAGE TITLE
# The current page's name is shown as the title at the top of
# the main area (the brand/logo now lives in the sidebar).
# -------------------------------------------------------------
st.markdown(
    f"<div style='font-size:36px; font-weight:800; color:#f3f5f8; "
    f"letter-spacing:0.2px; line-height:1.15; margin:0 0 6px; "
    f"padding-bottom:10px; border-bottom:1px solid {CARD_BORDER};'>{page}</div>",
    unsafe_allow_html=True,
)

# Check alert rules once per session (or after a refresh) and
# show a banner on every page if any are currently triggered.
if "alerts_checked" not in st.session_state:
    try:
        st.session_state["triggered_alerts"] = evaluate_alerts()
    except Exception:
        st.session_state["triggered_alerts"] = []
    st.session_state["alerts_checked"] = True

_triggered = st.session_state.get("triggered_alerts", [])
if _triggered:
    preview = "; ".join(_triggered[:3]) + ("…" if len(_triggered) > 3 else "")
    st.warning(f"**{len(_triggered)} alert(s) triggered** — {preview}  ·  Open the Alerts page for details.")


# ===========================================================
# PAGE 0: OVERVIEW / HOME
# A landing page with two glances: your portfolio snapshot at
# the top, and key macro signals at the bottom.
# ===========================================================
if page == "Overview":
    st.caption("Your portfolio and key market signals at a glance.")

    # -------------------------------------------------------
    # PORTFOLIO SNAPSHOT
    # Reads your saved holdings and values them live. If you
    # haven't added any yet, we nudge you to the Portfolio page.
    # -------------------------------------------------------
    st.header("Your Portfolio")
    holdings = load_portfolio_holdings()

    if holdings.empty:
        st.info("No holdings saved yet. Go to the **Portfolio Tracker** page to add some, then they'll show up here.")
    else:
        ov_total_value = 0.0
        ov_total_cost = 0.0
        ov_day_change = 0.0
        ov_rows = []
        ov_failed = []

        for _, row in holdings.iterrows():
            quote = get_portfolio_quote(row["Ticker"])
            if quote is None:
                ov_failed.append(row["Ticker"])
                continue
            shares = row["Shares"]
            value = shares * quote["price"]
            cost = shares * row.get("Cost Basis Per Share", 0)
            ov_total_value += value
            ov_total_cost += cost
            ov_day_change += (quote["price"] - quote["prev_close"]) * shares
            ov_rows.append({"Ticker": row["Ticker"], "Value": value})

        if ov_rows:
            ov_gain = ov_total_value - ov_total_cost
            ov_gain_pct = (ov_gain / ov_total_cost * 100) if ov_total_cost > 0 else 0
            ov_prior = ov_total_value - ov_day_change
            ov_day_pct = (ov_day_change / ov_prior * 100) if ov_prior else 0

            o1, o2, o3 = st.columns(3)
            o1.metric("Total Value", f"${ov_total_value:,.2f}")
            o2.metric("Today's Change", f"${ov_day_change:,.2f}", f"{ov_day_pct:+.2f}%")
            o3.metric("Total Gain/Loss", f"${ov_gain:,.2f}", f"{ov_gain_pct:+.2f}%")

            # A compact allocation donut so the home page feels alive.
            ov_df = pd.DataFrame(ov_rows)
            ov_pie = px.pie(ov_df, names="Ticker", values="Value", hole=0.5)
            ov_pie.update_traces(textinfo="percent+label")
            style_chart(ov_pie, height=350, xaxis_title="")
            st.plotly_chart(ov_pie, use_container_width=True)

        if ov_failed:
            st.caption(f"(Couldn't price: {', '.join(ov_failed)})")

    st.divider()

    # -------------------------------------------------------
    # MACRO SIGNALS
    # A quick read on rates, inflation, jobs, and market fear.
    # Each is fetched from FRED; missing ones just show "N/A".
    # -------------------------------------------------------
    st.header("Market & Economy Signals")

    # (label, FRED code, transform, formatter, help text)
    signals = [
        ("Fed Funds Rate", "FEDFUNDS", "level", "pct", "The Fed's key short-term interest rate."),
        ("CPI Inflation (YoY)", "CPIAUCSL", "yoy", "pct", "Consumer prices vs. a year ago."),
        ("Unemployment", "UNRATE", "level", "pct", "Share of the labor force without a job."),
        ("Yield Curve (10y−2y)", "T10Y2Y", "level", "pct", "Negative has historically preceded recessions."),
        ("VIX (Fear Gauge)", "VIXCLS", "level", "index", "Expected stock-market volatility; higher = more fear."),
    ]

    sig_cols = st.columns(len(signals))
    for col, (label, code, transform, fmt, helptext) in zip(sig_cols, signals):
        data, err = get_fred_series(code)
        if err or data is None or data.empty:
            col.metric(label, "N/A", help=helptext)
            continue
        series = data[code].dropna()
        if transform == "yoy" and len(series) > 12:
            series = (series.pct_change(periods=12) * 100).dropna()
        latest = series.iloc[-1]
        if fmt == "pct":
            shown = f"{latest:.2f}%"
        else:
            shown = f"{latest:.1f}"
        col.metric(label, shown, help=helptext)

    st.caption("See the **Macro Data** page for full history and more indicators.")


# ===========================================================
# PAGE 1: TICKER LOOKUP
# (The original single-ticker dashboard.)
# ===========================================================
elif page == "Ticker Lookup":
    st.caption("Look up any stock or ETF for fundamentals, a price chart, and news.")

    # -------------------------------------------------------
    # USER INPUT: the text box where you type a ticker.
    # We automatically capitalize it (so "aapl" still works)
    # and remove extra spaces.
    # -------------------------------------------------------
    ticker_input = st.text_input("Enter a stock or ETF ticker:", key="shared_ticker").strip().upper()

    if ticker_input:
        with st.spinner(f"Loading {ticker_input}…"):
            info, history, error = get_stock_data(ticker_input)

        if error:
            st.error(error)
        else:
            # -------------------------------------------------
            # FUNDAMENTAL SECTION
            # This box shows basic company facts side by side.
            # We use .get() with a default of "N/A" so the app
            # doesn't crash if a piece of data is missing
            # (this happens sometimes, especially for ETFs).
            # -------------------------------------------------
            st.header("Fundamentals")

            company_name = info.get("longName", info.get("shortName", "N/A"))
            is_etf = info.get("quoteType") == "ETF"
            sector = info.get("sector", "N/A")
            market_cap = info.get("marketCap", None)
            pe_ratio = info.get("trailingPE", None)
            dividend_yield = info.get("dividendYield", None)
            week_high = info.get("fiftyTwoWeekHigh", None)
            week_low = info.get("fiftyTwoWeekLow", None)

            # Dividend yield comes from Yahoo as a decimal (e.g. 0.0045 = 0.45%).
            # These all route through the shared formatters so missing
            # values show a consistent "N/A" everywhere.
            dividend_yield_display = fmt_decimal_pct(dividend_yield)
            pe_ratio_display = fmt_ratio(pe_ratio)
            week_high_display = fmt_price(week_high)
            week_low_display = fmt_price(week_low)

            st.subheader(f"{company_name} ({ticker_input})")
            if is_etf:
                st.caption("This is an ETF (a basket of many holdings), so company-specific metrics like P/E may be blank.")
            else:
                # Buy/Hold/Sell signal badge (with a "why" breakdown).
                _, _overall_tl, _ = grade_stock(info, history)
                show_signal(info, history, _overall_tl)

            # Lay out the fundamental facts in a clean grid of columns.
            col1, col2, col3 = st.columns(3)
            col1.metric("Sector", sector, help="The part of the economy this company operates in.")
            col2.metric("Market Cap", format_market_cap(market_cap),
                        help="Total value of all shares (price × shares). A measure of company size.")
            col3.metric("P/E Ratio", pe_ratio_display,
                        help="Price ÷ yearly earnings per share. Lower can mean cheaper. See the Glossary for more.")

            col4, col5, col6 = st.columns(3)
            col4.metric("Dividend Yield", dividend_yield_display,
                        help="Annual dividends as a percent of the share price.")
            col5.metric("52-Week High", week_high_display, help="Highest price over the past year.")
            col6.metric("52-Week Low", week_low_display, help="Lowest price over the past year.")

            st.divider()

            # -------------------------------------------------
            # ETF PROFILE (shown instead of the company deep dive
            # when the ticker is a fund, since company fundamentals
            # like P/E and margins don't apply to a basket).
            # -------------------------------------------------
            if is_etf:
                st.header("ETF Profile")
                e1, e2, e3, e4 = st.columns(4)
                e1.metric("Category", info.get("category", "N/A"),
                          help="The type of assets this ETF focuses on.")
                e2.metric("Total Assets", format_market_cap(info.get("totalAssets")),
                          help="How much money the fund manages.")
                e3.metric("Yield", fmt_decimal_pct(info.get("yield")),
                          help="Income paid out as a percent of price.")
                e4.metric("3-Yr Beta", fmt_ratio(info.get("beta3Year") or info.get("beta")),
                          help="Volatility vs. the market. 1 = moves with the market.")
                summary = info.get("longBusinessSummary")
                if summary:
                    with st.expander("ℹ️ About this fund"):
                        st.write(summary)

            # -------------------------------------------------
            # DEEPER COMPANY ("MICRO") DATA  (stocks only)
            # These are more advanced, company-specific numbers
            # grouped into four categories. Each uses .get() so
            # missing values just show "N/A".
            # -------------------------------------------------
            else:
                st.header("Company Deep Dive")

                # --- Valuation: is the stock cheap or expensive? ---
                st.markdown("**Valuation**")
                v1, v2, v3, v4 = st.columns(4)
                v1.metric("Forward P/E", fmt_ratio(info.get("forwardPE")),
                          help="Price ÷ expected future earnings. Like P/E but forward-looking.")
                v2.metric("PEG Ratio", fmt_ratio(info.get("trailingPegRatio")),
                          help="P/E adjusted for growth. Around 1 is often considered fair.")
                v3.metric("Price / Book", fmt_ratio(info.get("priceToBook")),
                          help="Price vs. the company's accounting net worth.")
                v4.metric("Price / Sales", fmt_ratio(info.get("priceToSalesTrailing12Months")),
                          help="Price vs. revenue. Useful when there are no profits yet.")

                # --- Profitability: how good is the business? ---
                st.markdown("**Profitability**")
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Profit Margin", fmt_decimal_pct(info.get("profitMargins")),
                          help="Percent of revenue left as profit.")
                p2.metric("Return on Equity", fmt_decimal_pct(info.get("returnOnEquity")),
                          help="Profit generated per dollar of shareholder money.")
                p3.metric("Operating Margin", fmt_decimal_pct(info.get("operatingMargins")),
                          help="Profit from core operations as a percent of revenue.")
                p4.metric("Gross Margin", fmt_decimal_pct(info.get("grossMargins")),
                          help="Revenue left after direct costs of goods.")

                # --- Growth: is the business getting bigger? ---
                st.markdown("**Growth**")
                g1, g2, g3, g4 = st.columns(4)
                g1.metric("Revenue Growth (YoY)", fmt_decimal_pct(info.get("revenueGrowth")),
                          help="How much sales grew vs. a year ago.")
                g2.metric("Earnings Growth (YoY)", fmt_decimal_pct(info.get("earningsGrowth")),
                          help="How much profit grew vs. a year ago.")
                g3.metric("EPS (trailing)", fmt_ratio(info.get("trailingEps")),
                          help="Earnings per share over the last 12 months.")
                g4.metric("Beta", fmt_ratio(info.get("beta")),
                          help="How volatile vs. the market. 1 = moves with the market.")

                # --- Financial health & analyst view ---
                st.markdown("**Financial Health & Analyst View**")
                h1, h2, h3, h4 = st.columns(4)
                h1.metric("Debt / Equity", fmt_ratio(info.get("debtToEquity")),
                          help="Debt relative to shareholder equity. Lower is generally safer.")
                h2.metric("Free Cash Flow", fmt_dollar_big(info.get("freeCashflow")),
                          help="Cash left after running and maintaining the business.")
                h3.metric("Analyst Target", fmt_ratio(info.get("targetMeanPrice")),
                          help="Average price target from Wall Street analysts.")
                recommendation = info.get("recommendationKey", "N/A")
                h4.metric("Analyst Rating", recommendation.replace("_", " ").title() if recommendation else "N/A",
                          help="Consensus analyst recommendation (e.g. Buy, Hold).")

            st.divider()

            # -------------------------------------------------
            # TECHNICAL SECTION
            # This calculates the 50-day and 200-day moving averages
            # (the average closing price over the last 50 or 200 days)
            # and plots them on top of the price chart.
            # -------------------------------------------------
            st.header("Technical Chart (1-Year Price History)")

            history["MA50"] = history["Close"].rolling(window=50).mean()
            history["MA200"] = history["Close"].rolling(window=200).mean()

            fig = go.Figure()

            # The actual closing price, day by day
            fig.add_trace(go.Scatter(
                x=history.index, y=history["Close"],
                mode="lines", name="Close Price", line=dict(color=COLOR_PRIMARY)
            ))

            # 50-day moving average line
            fig.add_trace(go.Scatter(
                x=history.index, y=history["MA50"],
                mode="lines", name="50-Day Moving Avg", line=dict(color=COLOR_ACCENT)
            ))

            # 200-day moving average line
            fig.add_trace(go.Scatter(
                x=history.index, y=history["MA200"],
                mode="lines", name="200-Day Moving Avg", line=dict(color=COLOR_GREEN)
            ))

            style_chart(fig, height=550, yaxis_title="Price (USD)", y_dollar=True)
            st.plotly_chart(fig, use_container_width=True)

            # -------------------------------------------------
            # RISK STATS (for this stock, over the past year)
            # Volatility, Sharpe, and max drawdown describe how
            # bumpy and risky the ride has been.
            # -------------------------------------------------
            risk = stock_risk_stats(history)
            if risk:
                vol, sharpe, maxdd = risk
                st.markdown("**Risk (past year)**")
                r1, r2, r3 = st.columns(3)
                r1.metric("Volatility (annualized)", f"{vol:.1f}%",
                          help="How much the price bounces around. Higher = bumpier, riskier.")
                r2.metric("Sharpe Ratio", f"{sharpe:.2f}",
                          help="Return earned per unit of risk. Higher is better; above 1 is decent.")
                r3.metric("Max Drawdown", f"{maxdd:.1f}%",
                          help="The worst peak-to-trough drop over the past year.")

            st.divider()

            # -------------------------------------------------
            # RECENT NEWS
            # Recent headlines so you can see what's driving the
            # stock, not just the numbers.
            # -------------------------------------------------
            st.header("Recent News")
            show_news(ticker_input)

    else:
        empty_state("Enter a ticker above to get started.")


# ===========================================================
# PAGE: GRADE & VALUE
# The "investment grading" page. Enter a ticker to get:
#   1) an A-F scorecard across five categories
#   2) a discounted-cash-flow fair-value estimate
#   3) forward-looking views: scenarios, Monte Carlo, analysts
# ===========================================================
elif page == "Grade & Value":
    st.caption("Score a stock and estimate what it's worth.")

    gv_ticker = st.text_input("Ticker to grade:", key="shared_ticker").strip().upper()

    if not gv_ticker:
        empty_state("Enter a ticker to grade it.")
    else:
        with st.spinner(f"Analyzing {gv_ticker}…"):
            info, history, error = get_stock_data(gv_ticker)
        if error:
            st.error(error)
        else:
            company_name = info.get("longName", info.get("shortName", gv_ticker))
            current_price = history["Close"].iloc[-1]

            # ETFs are baskets, so the company-style grade barely
            # applies (most inputs are blank). Warn up front.
            if info.get("quoteType") == "ETF":
                st.info(
                    "**Heads up:** this is an ETF (a basket of holdings). The grade and fair-value "
                    "tools are built for individual companies, so most inputs will be blank and the "
                    "score won't be meaningful. Use the **Ticker Lookup** page for an ETF-friendly view."
                )

            # -------------------------------------------------
            # 1) THE SCORECARD
            # -------------------------------------------------
            cats, overall, grade_details = grade_stock(info, history)
            overall_letter = score_to_letter(overall)

            st.header(f"Grade: {overall_letter}  ({company_name})")

            # Color the headline grade green/amber/red.
            if overall is not None:
                grade_color = COLOR_GREEN if overall >= 70 else (COLOR_ACCENT if overall >= 50 else "#ff5c5c")
                st.markdown(
                    f"<h2 style='color:{grade_color};margin-top:-10px'>"
                    f"Overall score: {overall:.0f}/100</h2>",
                    unsafe_allow_html=True,
                )

            st.caption(
                "Balanced grade across Valuation, Profitability, Growth, Financial Health, and Momentum. "
                "Higher is better. Missing data is skipped, not penalized."
            )

            # Buy/Hold/Sell signal badge (with a "why" breakdown).
            show_signal(info, history, overall)

            # One metric per category, with its own letter.
            cat_cols = st.columns(len(cats))
            for col, (cat_name, cat_score) in zip(cat_cols, cats.items()):
                shown = f"{cat_score:.0f}/100" if cat_score is not None else "N/A"
                col.metric(cat_name, score_to_letter(cat_score), shown)

            # A bar chart of the category scores.
            cat_df = pd.DataFrame(
                [{"Category": k, "Score": v} for k, v in cats.items() if v is not None]
            )
            if not cat_df.empty:
                grade_fig = px.bar(cat_df, x="Category", y="Score", color="Score",
                                   color_continuous_scale=["#ff5c5c", "#ffa600", "#37d67a"],
                                   range_color=[0, 100])
                grade_fig.update_layout(yaxis_range=[0, 100])
                style_chart(grade_fig, height=380, yaxis_title="Score (0–100)", xaxis_title="")
                st.plotly_chart(grade_fig, use_container_width=True)

            # -------------------------------------------------
            # WHY THIS GRADE? — the metrics behind each category
            # A colored dot shows whether each metric helped
            # (🟢), hurt (🔴), was so-so (🟡), or was missing (⚪).
            # -------------------------------------------------
            with st.expander("Why this grade? See the metrics behind each category"):
                show_grade_breakdown(cats, grade_details)
                st.caption("Each metric is scored 0–100 by how it compares to healthy benchmarks, then averaged per category.")

            # Risk stats for this stock (same as the Ticker Lookup page).
            risk = stock_risk_stats(history)
            if risk:
                vol, sharpe, maxdd = risk
                st.markdown("**Risk (past year)**")
                rr1, rr2, rr3 = st.columns(3)
                rr1.metric("Volatility (annualized)", f"{vol:.1f}%",
                           help="How much the price bounces around. Higher = bumpier, riskier.")
                rr2.metric("Sharpe Ratio", f"{sharpe:.2f}",
                           help="Return earned per unit of risk. Higher is better; above 1 is decent.")
                rr3.metric("Max Drawdown", f"{maxdd:.1f}%",
                           help="The worst peak-to-trough drop over the past year.")

            st.divider()

            # -------------------------------------------------
            # 2) FAIR VALUE (DCF)
            # -------------------------------------------------
            st.header("Fair-Value Estimate (DCF)")
            st.caption(
                "A simple discounted-cash-flow model. Adjust the assumptions to see how the estimate changes. "
                "Only works for companies with positive free cash flow (not ETFs)."
            )

            fc1, fc2, fc3, fc4 = st.columns(4)
            # Default the growth slider to the company's own revenue growth, if sensible.
            default_growth = info.get("revenueGrowth")
            default_growth = int(default_growth * 100) if default_growth and 0 < default_growth < 0.5 else 8
            dcf_growth = fc1.slider("Growth rate (next 5 yrs, %):", 0, 30, default_growth) / 100
            dcf_discount = fc2.slider("Discount rate (%):", 5, 15, 9) / 100
            dcf_years = fc3.slider("Years projected:", 3, 10, 5)
            dcf_terminal = fc4.slider("Terminal growth (%):", 0, 4, 2) / 100

            fair_value = estimate_fair_value(info, dcf_growth, dcf_discount, dcf_years, dcf_terminal)

            if fair_value is None:
                st.warning("Can't estimate a fair value for this ticker (needs positive free cash flow and share count).")
            else:
                upside = (fair_value / current_price - 1) * 100
                verdict = "Undervalued" if upside > 10 else ("Overvalued" if upside < -10 else "Roughly fairly valued")
                d1, d2, d3 = st.columns(3)
                d1.metric("Current Price", f"${current_price:,.2f}")
                d2.metric("Estimated Fair Value", f"${fair_value:,.2f}")
                d3.metric("Upside / Downside", f"{upside:+.1f}%", verdict)
                st.caption("Note: a DCF is only as good as its assumptions — treat it as one input, not gospel.")

            st.divider()

            # -------------------------------------------------
            # 3a) RETURN SCENARIOS (bull / base / bear)
            # -------------------------------------------------
            st.header("Future Potential")
            st.subheader("Return Scenarios")
            eps = info.get("trailingEps")
            base_pe = info.get("forwardPE") or info.get("trailingPE")

            if not eps or eps <= 0 or not base_pe:
                st.info("Not enough earnings data to build scenarios for this ticker.")
            else:
                sc1, sc2, sc3 = st.columns(3)
                horizon = sc1.slider("Years ahead:", 1, 10, 5, key="scenario_years")
                base_growth = sc2.slider("Base earnings growth (%/yr):", 0, 30, 8) / 100
                base_multiple = sc3.slider("Assumed future P/E:", 5, 40, int(min(base_pe, 40)))

                scenarios = {
                    "Bear": (base_growth - 0.05, base_multiple * 0.8),
                    "Base": (base_growth, base_multiple),
                    "Bull": (base_growth + 0.05, base_multiple * 1.2),
                }
                rows = []
                for name, (g, pe) in scenarios.items():
                    future_eps = eps * ((1 + max(g, -0.99)) ** horizon)
                    future_price = future_eps * pe
                    annualized = (future_price / current_price) ** (1 / horizon) - 1
                    rows.append({
                        "Scenario": name,
                        "Projected Price": future_price,
                        "Total Return": (future_price / current_price - 1) * 100,
                        "Annualized Return": annualized * 100,
                    })
                scen_df = pd.DataFrame(rows)
                show = scen_df.copy()
                show["Projected Price"] = show["Projected Price"].map("${:,.2f}".format)
                show["Total Return"] = show["Total Return"].map("{:+.1f}%".format)
                show["Annualized Return"] = show["Annualized Return"].map("{:+.1f}%".format)
                st.dataframe(show, use_container_width=True, hide_index=True)
                st.caption(f"Starting from today's price of ${current_price:,.2f}. Bull/Bear shift growth ±5pts and the P/E ±20%.")

            st.divider()

            # -------------------------------------------------
            # 3b) MONTE CARLO SIMULATION
            # -------------------------------------------------
            st.subheader("Monte Carlo Simulation (1 Year)")
            st.caption(
                "Simulates 500 possible price paths over the next year using this stock's own historical "
                "volatility. Shows the range of outcomes — not a prediction."
            )
            mc = monte_carlo_paths(history, days=252, simulations=500)
            if mc is None:
                st.info("Not enough price history to simulate.")
            else:
                start_price, paths = mc
                # Percentile bands across time.
                p5 = np.percentile(paths, 5, axis=1)
                p50 = np.percentile(paths, 50, axis=1)
                p95 = np.percentile(paths, 95, axis=1)
                steps = np.arange(1, paths.shape[0] + 1)

                mc_fig = go.Figure()
                mc_fig.add_trace(go.Scatter(x=steps, y=p95, mode="lines",
                                            line=dict(width=0), showlegend=False))
                mc_fig.add_trace(go.Scatter(x=steps, y=p5, mode="lines", fill="tonexty",
                                            fillcolor="rgba(59,158,255,0.15)", line=dict(width=0),
                                            name="5th–95th percentile"))
                mc_fig.add_trace(go.Scatter(x=steps, y=p50, mode="lines",
                                            line=dict(color=COLOR_PRIMARY), name="Median path"))
                style_chart(mc_fig, height=420, yaxis_title="Simulated Price (USD)", xaxis_title="Trading days ahead", y_dollar=True)
                st.plotly_chart(mc_fig, use_container_width=True)

                final_prices = paths[-1, :]
                prob_gain = (final_prices > start_price).mean() * 100
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Median in 1 yr", f"${np.median(final_prices):,.2f}")
                m2.metric("Pessimistic (5%)", f"${np.percentile(final_prices, 5):,.2f}")
                m3.metric("Optimistic (95%)", f"${np.percentile(final_prices, 95):,.2f}")
                m4.metric("Chance of a Gain", f"{prob_gain:.0f}%")

            st.divider()

            # -------------------------------------------------
            # 3c) ANALYST TARGETS + EARNINGS TRENDS
            # -------------------------------------------------
            st.subheader("Analyst View & Business Trends")
            target = info.get("targetMeanPrice")
            ac1, ac2, ac3 = st.columns(3)
            if target:
                ac1.metric("Avg Analyst Target", f"${target:,.2f}",
                           f"{(target / current_price - 1) * 100:+.1f}% vs. price")
            else:
                ac1.metric("Avg Analyst Target", "N/A")
            rec = info.get("recommendationKey", "")
            ac2.metric("Analyst Rating", rec.replace("_", " ").title() if rec else "N/A")
            ac3.metric("# of Analysts", f"{info.get('numberOfAnalystOpinions', 'N/A')}")

            financials = get_financials(gv_ticker)
            if financials:
                for label, series in financials.items():
                    s = series.sort_index()
                    trend_fig = go.Figure()
                    trend_fig.add_trace(go.Bar(
                        x=[d.year for d in s.index], y=s.values,
                        marker_color=COLOR_PRIMARY, name=label
                    ))
                    style_chart(trend_fig, height=280, yaxis_title=label, xaxis_title="Year")
                    st.markdown(f"**{label} by Year**")
                    st.plotly_chart(trend_fig, use_container_width=True)
            else:
                st.caption("(Multi-year revenue/earnings history isn't available for this ticker.)")

            st.divider()
            st.subheader("Recent News")
            show_news(gv_ticker)


# ===========================================================
# PAGE: COMPARE (HEAD-TO-HEAD)
# Pick two tickers and see them side-by-side: overall grades,
# a fundamentals table that highlights the "winner" on each
# metric, and a normalized price chart.
# ===========================================================
elif page == "Compare":
    st.caption("Two tickers, head-to-head.")

    cc1, cc2 = st.columns(2)
    ticker_a = cc1.text_input("First ticker:", value=st.session_state.get("shared_ticker", "AAPL"),
                              key="cmp_a").strip().upper()
    ticker_b = cc2.text_input("Second ticker:", value="MSFT", key="cmp_b").strip().upper()

    if not ticker_a or not ticker_b:
        empty_state("Enter two tickers to compare them.")
    else:
        with st.spinner(f"Loading {ticker_a} and {ticker_b}…"):
            info_a, hist_a, err_a = get_stock_data(ticker_a)
            info_b, hist_b, err_b = get_stock_data(ticker_b)

        problems = []
        if err_a:
            problems.append(f"{ticker_a}: {err_a}")
        if err_b:
            problems.append(f"{ticker_b}: {err_b}")

        if problems:
            for p in problems:
                st.error(p)
        else:
            name_a = info_a.get("longName", info_a.get("shortName", ticker_a))
            name_b = info_b.get("longName", info_b.get("shortName", ticker_b))
            price_a = hist_a["Close"].iloc[-1]
            price_b = hist_b["Close"].iloc[-1]

            # -------------------------------------------------
            # GRADES SIDE BY SIDE
            # -------------------------------------------------
            cats_a, overall_a, _ = grade_stock(info_a, hist_a)
            cats_b, overall_b, _ = grade_stock(info_b, hist_b)

            st.header("Grades")
            gcol1, gcol2 = st.columns(2)
            gcol1.metric(
                f"{ticker_a} — {name_a}",
                score_to_letter(overall_a),
                f"{overall_a:.0f}/100" if overall_a is not None else "N/A",
            )
            gcol2.metric(
                f"{ticker_b} — {name_b}",
                score_to_letter(overall_b),
                f"{overall_b:.0f}/100" if overall_b is not None else "N/A",
            )

            # Buy/Hold/Sell signal badge under each ticker's grade.
            scol1, scol2 = st.columns(2)
            with scol1:
                show_signal(info_a, hist_a, overall_a)
            with scol2:
                show_signal(info_b, hist_b, overall_b)

            # Grouped bar chart of category scores.
            cat_rows = []
            for cat in cats_a.keys():
                cat_rows.append({"Category": cat, "Ticker": ticker_a, "Score": cats_a.get(cat)})
                cat_rows.append({"Category": cat, "Ticker": ticker_b, "Score": cats_b.get(cat)})
            cat_cmp_df = pd.DataFrame(cat_rows).dropna(subset=["Score"])
            if not cat_cmp_df.empty:
                cmp_fig = px.bar(cat_cmp_df, x="Category", y="Score", color="Ticker",
                                 barmode="group")
                cmp_fig.update_layout(yaxis_range=[0, 100])
                style_chart(cmp_fig, height=380, yaxis_title="Score (0–100)", xaxis_title="")
                st.plotly_chart(cmp_fig, use_container_width=True)

            st.divider()

            # -------------------------------------------------
            # FUNDAMENTALS TABLE WITH "WINNER" HIGHLIGHTING
            # Each metric knows whether higher or lower is better
            # so we can shade the stronger ticker's cell green.
            # -------------------------------------------------
            st.header("Head-to-Head Metrics")

            one_yr_a = (price_a / hist_a["Close"].iloc[0] - 1) * 100
            one_yr_b = (price_b / hist_b["Close"].iloc[0] - 1) * 100

            # (label, value for A, value for B, direction, formatter)
            def pct_dec(v):   # decimal fraction -> percent
                return f"{v * 100:.2f}%" if v is not None and pd.notna(v) else "N/A"

            def pct_already(v):
                return f"{v:+.2f}%" if v is not None and pd.notna(v) else "N/A"

            metric_defs = [
                ("Price", price_a, price_b, "none", fmt_price),
                ("Market Cap", info_a.get("marketCap"), info_b.get("marketCap"), "high", format_market_cap),
                ("Trailing P/E", info_a.get("trailingPE"), info_b.get("trailingPE"), "low", fmt_ratio),
                ("Forward P/E", info_a.get("forwardPE"), info_b.get("forwardPE"), "low", fmt_ratio),
                ("PEG Ratio", info_a.get("trailingPegRatio"), info_b.get("trailingPegRatio"), "low", fmt_ratio),
                ("Price/Book", info_a.get("priceToBook"), info_b.get("priceToBook"), "low", fmt_ratio),
                ("Dividend Yield", info_a.get("dividendYield"), info_b.get("dividendYield"), "high", pct_dec),
                ("Profit Margin", info_a.get("profitMargins"), info_b.get("profitMargins"), "high", pct_dec),
                ("Return on Equity", info_a.get("returnOnEquity"), info_b.get("returnOnEquity"), "high", pct_dec),
                ("Revenue Growth", info_a.get("revenueGrowth"), info_b.get("revenueGrowth"), "high", pct_dec),
                ("Beta", info_a.get("beta"), info_b.get("beta"), "none", fmt_ratio),
                ("1-Yr Return", one_yr_a, one_yr_b, "high", pct_already),
            ]

            # Build the display table and remember raw values + direction
            # so the styler can decide the winner.
            raw_a, raw_b, direction = {}, {}, {}
            table_rows = []
            for label, va, vb, dirn, fmt in metric_defs:
                raw_a[label] = va
                raw_b[label] = vb
                direction[label] = dirn
                table_rows.append({"Metric": label, ticker_a: fmt(va), ticker_b: fmt(vb)})
            cmp_table = pd.DataFrame(table_rows)

            def highlight_winner(row):
                label = row["Metric"]
                a, b = raw_a[label], raw_b[label]
                dirn = direction[label]
                styles = ["", "", ""]  # Metric, A, B
                if dirn == "none" or a is None or b is None or not pd.notna(a) or not pd.notna(b) or a == b:
                    return styles
                a_wins = (a > b) if dirn == "high" else (a < b)
                win_style = "background-color: rgba(55,214,122,0.18); font-weight: bold;"
                styles[1] = win_style if a_wins else ""
                styles[2] = win_style if not a_wins else ""
                return styles

            styler = cmp_table.style.apply(highlight_winner, axis=1)
            st.dataframe(styler, use_container_width=True, hide_index=True)
            st.caption("The stronger ticker on each metric is shaded green. (Price and Beta aren't judged as better/worse.)")

            st.divider()

            # -------------------------------------------------
            # NORMALIZED PRICE CHART
            # Both rebased to 100 a year ago for a fair race.
            # -------------------------------------------------
            st.header("1-Year Price Race (Rebased to 100)")
            race_fig = go.Figure()
            for ticker, hist in [(ticker_a, hist_a), (ticker_b, hist_b)]:
                normalized = hist["Close"] / hist["Close"].iloc[0] * 100
                race_fig.add_trace(go.Scatter(
                    x=normalized.index, y=normalized.values, mode="lines", name=ticker
                ))
            style_chart(race_fig, height=450, yaxis_title="Growth (start = 100)")
            st.plotly_chart(race_fig, use_container_width=True)


# ===========================================================
# PAGE: DISCOVER (UNDER-THE-RADAR)
# Pulls lesser-known candidates from Yahoo's small-cap and
# undervalued screens, grades each one, and assigns a
# data-driven Buy/Sell signal. Educational, not advice.
# ===========================================================
elif page == "Discover":
    st.caption("Find under-the-radar stocks with a Buy/Sell signal — a research starting point, not advice.")

    st.warning(
        "**Educational tool, not financial advice.** These signals are computed from "
        "public data and simple rules. They can be wrong, the data can be stale, and small "
        "companies are riskier. Always do your own research before investing."
    )

    # -------------------------------------------------------
    # CONTROLS
    # -------------------------------------------------------
    dc1, dc2 = st.columns(2)
    max_cap_b = dc1.slider("Max market cap ($ billions):", 1, 100, 20,
                           help="Lower = more under-the-radar. Filters out big, well-covered names.")
    how_many = dc2.slider("How many to analyze:", 5, 20, 10,
                          help="More = a fuller list but slower to load.")

    run = st.button("Find candidates")

    if not run:
        empty_state("Set your filters above and click **Find candidates** to scan for ideas.")
    else:
        # ---------------------------------------------------
        # GATHER CANDIDATES FROM A BLEND OF SCREENS
        # ---------------------------------------------------
        with st.spinner("Scanning small-cap and undervalued screens..."):
            blend = ["aggressive_small_caps", "small_cap_gainers", "undervalued_growth_stocks"]
            candidates = {}
            for screen_key in blend:
                for item in get_screen_symbols(screen_key, count=25):
                    cap = item.get("marketCap")
                    # Keep only names under the market-cap ceiling.
                    if cap and cap <= max_cap_b * 1e9:
                        candidates.setdefault(item["symbol"], item)

        if not candidates:
            st.error("No candidates came back right now (the screen may be temporarily unavailable, or your cap is too low). Try again or raise the cap.")
        else:
            # Smaller companies first (more under-the-radar), then cap the count.
            ordered = sorted(candidates.values(), key=lambda x: x.get("marketCap") or 0)
            ordered = ordered[:how_many]

            # ---------------------------------------------
            # GRADE EACH CANDIDATE AND BUILD A SIGNAL
            # ---------------------------------------------
            rows = []
            with st.spinner(f"Grading {len(ordered)} candidates..."):
                for item in ordered:
                    ticker = item["symbol"]
                    info, history, error = get_stock_data(ticker)
                    if error:
                        continue
                    cats, overall, _ = grade_stock(info, history)
                    score, label, _ = buy_sell_signal(info, overall, history)
                    price = history["Close"].iloc[-1]
                    target = info.get("targetMeanPrice")
                    upside = ((target / price - 1) * 100) if (target and price) else None
                    rows.append({
                        "Ticker": ticker,
                        "Name": info.get("longName", info.get("shortName", item["name"]))[:30],
                        "Market Cap": info.get("marketCap"),
                        "Price": price,
                        "Grade": score_to_letter(overall),
                        "Signal": label,
                        "Buy Score": round(score, 0) if score is not None else None,
                        "Analyst Upside": upside,
                    })

            if not rows:
                st.error("Couldn't grade any of the candidates right now. Try again in a moment.")
            else:
                disc_df = pd.DataFrame(rows).sort_values("Buy Score", ascending=False, na_position="last")

                # Color the Signal text and Buy Score.
                def color_signal(val):
                    colors = {
                        "Strong Buy": "#37d67a", "Buy": "#8fd14f", "Hold": "#ffa600",
                        "Sell": "#ff8c5c", "Strong Sell": "#ff5c5c",
                    }
                    return f"color: {colors.get(val, '#e6e6e6')}; font-weight: bold;"

                def color_score(val):
                    if pd.isna(val):
                        return ""
                    if val >= 60: return "color: #37d67a;"
                    if val >= 45: return "color: #ffa600;"
                    return "color: #ff5c5c;"

                styler = disc_df.style.map(color_signal, subset=["Signal"]) \
                                      .map(color_score, subset=["Buy Score"])
                st.dataframe(
                    styler,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Market Cap": st.column_config.NumberColumn(
                            "Market Cap", format="compact", help="Company size. Smaller = more under-the-radar."),
                        "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                        "Grade": st.column_config.TextColumn(
                            "Grade", help="Our A–F balanced grade for the company."),
                        "Signal": st.column_config.TextColumn(
                            "Signal", help="Strong Buy to Strong Sell, blended from grade, valuation, analysts, and momentum."),
                        "Buy Score": st.column_config.NumberColumn(
                            "Buy Score", format="%.0f", help="0–100 score behind the signal. Higher = more attractive."),
                        "Analyst Upside": st.column_config.NumberColumn(
                            "Analyst Upside", format="%.1f%%", help="Average analyst target vs. today's price."),
                    },
                )
                st.caption(
                    "Signal blends our A–F grade, analyst price-target upside, analyst consensus, and price momentum. "
                    "Sorted best-to-worst. Open **Grade & Value** for a full breakdown, or add names to your **Watchlist**."
                )

                # One-click: add any of these candidates to the watchlist.
                add_choices = st.multiselect(
                    "Add candidates to your watchlist:", disc_df["Ticker"].tolist(), key="disc_add"
                )
                if st.button("Add selected to Watchlist", key="disc_add_btn"):
                    added = add_tickers_to_watchlist(add_choices)
                    if added:
                        st.success(f"Added {added} ticker(s) to your watchlist.")
                    else:
                        st.info("Nothing new to add (they may already be on your watchlist).")


# ===========================================================
# PAGE: WATCHLIST
# A saved list of candidate investments, each auto-graded so
# you can compare them at a glance and jot notes.
# ===========================================================
elif page == "Watchlist":
    st.caption("Track and auto-grade candidate investments.")

    # Load (once per session) into editable state.
    if "watchlist_df" not in st.session_state:
        st.session_state.watchlist_df = load_watchlist()

    st.subheader("Your Watchlist")
    wl_edited = st.data_editor(
        st.session_state.watchlist_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker", help="e.g. AAPL, NVDA"),
            "Notes": st.column_config.TextColumn("Notes", help="Your own thoughts", width="large"),
        },
        key="watchlist_editor",
    )
    st.session_state.watchlist_df = wl_edited

    wl_save, wl_dl = st.columns(2)
    if MULTIUSER:
        wl_save.caption("Your watchlist stays in this session. Use Download/Upload to keep a copy.")
    else:
        if wl_save.button("Save Watchlist"):
            wl_edited.to_csv(WATCHLIST_FILE, index=False)
            st.success("Watchlist saved!")
    wl_dl.download_button(
        "Download backup",
        data=wl_edited.to_csv(index=False).encode("utf-8"),
        file_name="watchlist_backup.csv",
        mime="text/csv",
        help="Save a copy of your watchlist to your computer.",
    )

    wl_upload = st.file_uploader("Upload a saved watchlist (.csv)", type="csv", key="wl_upload")
    if wl_upload is not None and st.session_state.get("wl_upload_id") != getattr(wl_upload, "file_id", wl_upload.name):
        try:
            st.session_state.watchlist_df = pd.read_csv(wl_upload)
            st.session_state["wl_upload_id"] = getattr(wl_upload, "file_id", wl_upload.name)
            st.success("Watchlist loaded.")
            st.rerun()
        except Exception:
            st.warning("Couldn't read that file — make sure it's a Lumen watchlist backup.")

    st.divider()

    # Clean tickers and grade each one.
    wl_rows = wl_edited.dropna(subset=["Ticker"]).copy()
    wl_rows = wl_rows[wl_rows["Ticker"].astype(str).str.strip() != ""]
    wl_tickers = list(dict.fromkeys(wl_rows["Ticker"].astype(str).str.strip().str.upper()))

    if not wl_tickers:
        empty_state("Add at least one ticker above to see grades.")
    else:
        notes_map = {
            str(r["Ticker"]).strip().upper(): (r.get("Notes", "") if pd.notna(r.get("Notes", "")) else "")
            for _, r in wl_rows.iterrows()
        }
        graded = []
        wl_failed = []
        details_map = {}  # ticker -> (cats, details) for the "why" expanders
        for ticker in wl_tickers:
            info, history, error = get_stock_data(ticker)
            if error:
                wl_failed.append(ticker)
                continue
            cats, overall, details = grade_stock(info, history)
            details_map[ticker] = (cats, details)
            _, sig_label, _ = buy_sell_signal(info, overall, history)
            graded.append({
                "Ticker": ticker,
                "Grade": score_to_letter(overall),
                "Score": round(overall, 0) if overall is not None else None,
                "Signal": sig_label,
                "Price": history["Close"].iloc[-1],
                "Valuation": cats.get("Valuation"),
                "Profitability": cats.get("Profitability"),
                "Growth": cats.get("Growth"),
                "Fin. Health": cats.get("Financial Health"),
                "Momentum": cats.get("Momentum"),
                "Notes": notes_map.get(ticker, ""),
            })

        if wl_failed:
            st.warning(f"Couldn't grade: {', '.join(wl_failed)}. Check the spelling.")

        if graded:
            graded_df = pd.DataFrame(graded).sort_values("Score", ascending=False, na_position="last")

            # Color category score cells green→red.
            score_cols = ["Score", "Valuation", "Profitability", "Growth", "Fin. Health", "Momentum"]

            def color_score(val):
                if pd.isna(val):
                    return ""
                if val >= 70: return "color: #5fae8a;"
                if val >= 50: return "color: #d9a05b;"
                return "color: #cf6b6b;"

            def color_signal_cell(val):
                return f"color: {SIGNAL_COLORS.get(val, '#e6e6e6')}; font-weight: 600;"

            styler = graded_df.style.map(color_score, subset=score_cols) \
                                    .map(color_signal_cell, subset=["Signal"])
            st.dataframe(
                styler,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Signal": st.column_config.TextColumn("Signal", help="Blended Buy/Hold/Sell signal."),
                    "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "Score": st.column_config.NumberColumn("Score", format="%.0f"),
                    "Valuation": st.column_config.NumberColumn("Valuation", format="%.0f"),
                    "Profitability": st.column_config.NumberColumn("Profitability", format="%.0f"),
                    "Growth": st.column_config.NumberColumn("Growth", format="%.0f"),
                    "Fin. Health": st.column_config.NumberColumn("Fin. Health", format="%.0f"),
                    "Momentum": st.column_config.NumberColumn("Momentum", format="%.0f"),
                },
            )
            st.caption("Sorted by overall score. Expand any ticker below to see why it got its grade.")

            # "Why" breakdown per ticker, in the sorted order.
            st.divider()
            st.markdown("**Why these grades?**")
            for ticker in graded_df["Ticker"]:
                cats, details = details_map[ticker]
                with st.expander(f"{ticker} — {score_to_letter(_avg(list(cats.values())))}"):
                    show_grade_breakdown(cats, details)


# ===========================================================
# PAGE: ALERTS
# In-app alert rules. You define conditions; Lumen checks them
# when you open the app or hit Refresh and flags what's
# triggered (works only while the app is open).
# ===========================================================
elif page == "Alerts":
    st.caption("Set rules; Lumen flags what's triggered when you open it or hit Refresh.")

    st.info(
        "These are **in-app** alerts — they're checked while Lumen is open (on load or Refresh), "
        "not pushed to your phone. Email alerts would need the app hosted online."
    )

    # Load alert rules once per session into editable state.
    if "alerts_df" not in st.session_state:
        st.session_state.alerts_df = load_alerts()

    st.subheader("Your Alert Rules")
    alerts_edited = st.data_editor(
        st.session_state.alerts_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker", help="e.g. AAPL"),
            "Condition": st.column_config.SelectboxColumn(
                "Condition", options=ALERT_CONDITIONS, help="What to watch for."),
            "Value": st.column_config.TextColumn(
                "Value", help="A price (e.g. 200), a percent (e.g. 5), or a signal "
                              "(Strong Buy / Buy / Hold / Sell / Strong Sell)."),
        },
        key="alerts_editor",
    )
    st.session_state.alerts_df = alerts_edited

    col_save, col_check = st.columns(2)
    if MULTIUSER:
        col_save.caption("Alert rules stay in this session on the shared app.")
    else:
        if col_save.button("Save Alerts"):
            alerts_edited.to_csv(ALERTS_FILE, index=False)
            st.success("Alert rules saved!")
    if col_check.button("Check now"):
        st.session_state["triggered_alerts"] = evaluate_alerts()
        st.session_state["alerts_checked"] = True

    st.caption(
        "Conditions: **Price above/below** a dollar value · **Daily move % above** a percent · "
        "**Signal is** a label (Strong Buy / Buy / Hold / Sell / Strong Sell)."
    )

    st.divider()

    # Show the current results of the most recent check.
    st.subheader("Triggered Now")
    triggered = st.session_state.get("triggered_alerts", [])
    if not triggered:
        st.success("Nothing triggered right now.")
    else:
        for msg in triggered:
            st.warning(msg)


# ===========================================================
# PAGE 2: PORTFOLIO TRACKER
# Lets you enter your holdings and see live value & gain/loss.
# ===========================================================
elif page == "Portfolio Tracker":
    st.caption("Enter your holdings — they're saved for next time.")

    # -------------------------------------------------------
    # LOAD SAVED PORTFOLIO (IF ANY)
    # The first time you ever open this page, there's no saved
    # file yet, so we start with one example row instead.
    # We only load from disk once per session and keep the
    # working copy in "session state" so your edits aren't
    # lost every time the page refreshes.
    # -------------------------------------------------------
    if "portfolio_df" not in st.session_state:
        default_portfolio = pd.DataFrame(
            [{"Ticker": "AAPL", "Shares": 10, "Cost Basis Per Share": 150.00}],
            columns=PORTFOLIO_COLUMNS,
        )
        if MULTIUSER:
            # Published app: each visitor starts blank (their own session).
            st.session_state.portfolio_df = pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        else:
            try:
                if os.path.exists(PORTFOLIO_FILE):
                    loaded = pd.read_csv(PORTFOLIO_FILE)
                    st.session_state.portfolio_df = loaded if "Ticker" in loaded.columns else default_portfolio
                else:
                    st.session_state.portfolio_df = default_portfolio
            except Exception:
                st.warning("Your saved portfolio file couldn't be read, so we started fresh.")
                st.session_state.portfolio_df = default_portfolio

    # -------------------------------------------------------
    # EDITABLE TABLE
    # This lets you add, edit, or delete rows directly in the
    # browser, like a mini spreadsheet. num_rows="dynamic" is
    # what allows adding/removing rows.
    # -------------------------------------------------------
    st.subheader("Your Holdings")
    edited_df = st.data_editor(
        st.session_state.portfolio_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker", help="e.g. AAPL, VOO"),
            "Shares": st.column_config.NumberColumn(
                "Shares", min_value=0.0, step=0.0001, format="%.4f",
                help="Supports fractional shares (e.g. 1.5)."),
            "Cost Basis Per Share": st.column_config.NumberColumn(
                "Cost Basis Per Share", min_value=0.0, step=0.01, format="$%.2f"
            ),
        },
        key="portfolio_editor",
    )
    st.session_state.portfolio_df = edited_df

    # -------------------------------------------------------
    # SAVE BUTTON
    # Writes your current table to a CSV file on your computer
    # so it's still there next time you open the app.
    # -------------------------------------------------------
    save_col, dl_col = st.columns(2)
    if MULTIUSER:
        save_col.caption("Your data stays in this session. Use Download to keep a copy, Upload to restore it.")
    else:
        if save_col.button("Save Portfolio"):
            edited_df.to_csv(PORTFOLIO_FILE, index=False)
            st.success("Portfolio saved!")
    dl_col.download_button(
        "Download backup",
        data=edited_df.to_csv(index=False).encode("utf-8"),
        file_name="portfolio_backup.csv",
        mime="text/csv",
        help="Save a copy of your holdings to your computer.",
    )

    # Upload a previously downloaded backup to restore it.
    pf_upload = st.file_uploader("Upload a saved portfolio (.csv)", type="csv", key="pf_upload")
    if pf_upload is not None and st.session_state.get("pf_upload_id") != getattr(pf_upload, "file_id", pf_upload.name):
        try:
            st.session_state.portfolio_df = pd.read_csv(pf_upload)
            st.session_state["pf_upload_id"] = getattr(pf_upload, "file_id", pf_upload.name)
            st.success("Portfolio loaded.")
            st.rerun()
        except Exception:
            st.warning("Couldn't read that file — make sure it's a Lumen portfolio backup.")

    st.divider()

    # -------------------------------------------------------
    # CALCULATE CURRENT VALUE, GAIN/LOSS FOR EACH HOLDING
    # We clean up the table first (drop blank rows, make sure
    # tickers are uppercase) then fetch a live price for each
    # one and do the math.
    # -------------------------------------------------------
    valid_rows = edited_df.dropna(subset=["Ticker"]).copy()
    valid_rows = valid_rows[valid_rows["Ticker"].astype(str).str.strip() != ""]
    valid_rows["Ticker"] = valid_rows["Ticker"].astype(str).str.strip().str.upper()
    valid_rows["Shares"] = pd.to_numeric(valid_rows["Shares"], errors="coerce").fillna(0)
    valid_rows["Cost Basis Per Share"] = pd.to_numeric(
        valid_rows["Cost Basis Per Share"], errors="coerce"
    ).fillna(0)

    if valid_rows.empty:
        empty_state("Add at least one holding above to see your portfolio summary.")
    else:
        # Keep data entry fast: only fetch prices and build the charts
        # when the user asks. Otherwise every cell edit would trigger a
        # round of network fetches and make typing feel sluggish.
        if not st.session_state.get("value_portfolio"):
            if st.button("Value my portfolio"):
                st.session_state["value_portfolio"] = True
                st.rerun()
            st.caption("Enter all your holdings above, then click to value them.")
            st.stop()

        st.header("Portfolio Summary")

        results = []
        failed_tickers = []

        for _, row in valid_rows.iterrows():
            ticker = row["Ticker"]
            shares = row["Shares"]
            cost_basis = row["Cost Basis Per Share"]

            quote = get_portfolio_quote(ticker)

            if quote is None:
                failed_tickers.append(ticker)
                continue

            current_price = quote["price"]
            prev_close = quote["prev_close"]

            current_value = shares * current_price
            total_cost = shares * cost_basis
            gain_loss_dollars = current_value - total_cost
            gain_loss_percent = (gain_loss_dollars / total_cost * 100) if total_cost > 0 else 0

            # Today's move = how much each share changed since the
            # previous day's close, times how many shares we own.
            day_change_dollars = (current_price - prev_close) * shares
            day_change_percent = ((current_price - prev_close) / prev_close * 100) if prev_close else 0

            # Estimated annual dividend income = value × yield.
            annual_dividend = current_value * quote["dividend_yield"]

            results.append({
                "Ticker": ticker,
                "Shares": shares,
                "Current Price": current_price,
                "Current Value": current_value,
                "Total Cost": total_cost,
                "Day Change ($)": day_change_dollars,
                "Day Change (%)": day_change_percent,
                "Gain/Loss ($)": gain_loss_dollars,
                "Gain/Loss (%)": gain_loss_percent,
                "Sector": quote["sector"],
                "Annual Dividend": annual_dividend,
            })

        if failed_tickers:
            st.warning(f"Couldn't fetch prices for: {', '.join(failed_tickers)}. Check these tickers are spelled correctly.")

        if results:
            results_df = pd.DataFrame(results)

            # ---------------------------------------------
            # WEIGHT COLUMN: each holding's share of the
            # portfolio's total current value.
            # ---------------------------------------------
            total_value = results_df["Current Value"].sum()
            results_df["Weight (%)"] = results_df["Current Value"] / total_value * 100

            # ---------------------------------------------
            # TOP-LEVEL METRICS
            # Total value, total gain/loss, today's change,
            # and estimated annual dividend income.
            # ---------------------------------------------
            total_cost = results_df["Total Cost"].sum()
            total_gain_loss = total_value - total_cost
            total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0
            total_day_change = results_df["Day Change ($)"].sum()
            prior_value = total_value - total_day_change
            total_day_change_pct = (total_day_change / prior_value * 100) if prior_value else 0
            total_dividends = results_df["Annual Dividend"].sum()
            div_yield_on_value = (total_dividends / total_value * 100) if total_value else 0

            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            mcol1.metric("Total Value", f"${total_value:,.2f}")
            mcol2.metric(
                "Today's Change",
                f"${total_day_change:,.2f}",
                f"{total_day_change_pct:+.2f}%",
            )
            mcol3.metric(
                "Total Gain/Loss",
                f"${total_gain_loss:,.2f}",
                f"{total_gain_loss_pct:+.2f}%",
            )
            mcol4.metric(
                "Est. Annual Dividends",
                f"${total_dividends:,.2f}",
                help=f"Approximately a {div_yield_on_value:.2f}% yield on your current value.",
            )

            st.divider()

            # ---------------------------------------------
            # DETAILED TABLE
            # Per-holding breakdown, nicely formatted.
            # ---------------------------------------------
            st.subheader("Holdings Detail")
            # Keep numbers numeric so the table stays sortable and the
            # gain/loss columns can be colored green (up) / red (down).
            holdings_df = results_df[[
                "Ticker", "Sector", "Shares", "Current Price", "Current Value",
                "Weight (%)", "Day Change ($)", "Day Change (%)",
                "Gain/Loss ($)", "Gain/Loss (%)", "Annual Dividend",
            ]].copy()

            change_cols = ["Day Change ($)", "Day Change (%)", "Gain/Loss ($)", "Gain/Loss (%)"]

            def color_change(val):
                if pd.isna(val):
                    return ""
                return "color: #5fae8a;" if val >= 0 else "color: #cf6b6b;"

            holdings_styler = holdings_df.style.map(color_change, subset=change_cols)
            st.dataframe(
                holdings_styler, use_container_width=True, hide_index=True,
                column_config={
                    "Current Price": st.column_config.NumberColumn("Current Price", format="$%.2f"),
                    "Current Value": st.column_config.NumberColumn("Current Value", format="$%.2f"),
                    "Weight (%)": st.column_config.NumberColumn(
                        "Weight (%)", format="%.1f%%", help="This holding's share of your total portfolio value."),
                    "Day Change ($)": st.column_config.NumberColumn(
                        "Day Change ($)", format="$%.2f", help="Dollar change today (price move × shares)."),
                    "Day Change (%)": st.column_config.NumberColumn(
                        "Day Change (%)", format="%.2f%%", help="Percent change in price since yesterday's close."),
                    "Gain/Loss ($)": st.column_config.NumberColumn(
                        "Gain/Loss ($)", format="$%.2f", help="Current value minus what you paid."),
                    "Gain/Loss (%)": st.column_config.NumberColumn(
                        "Gain/Loss (%)", format="%.2f%%", help="Total return vs. your cost basis."),
                    "Annual Dividend": st.column_config.NumberColumn(
                        "Annual Dividend", format="$%.2f", help="Estimated yearly dividend income from this holding."),
                },
            )

            st.divider()

            # ---------------------------------------------
            # TWO ALLOCATION PIE CHARTS, SIDE BY SIDE
            # Left: by ticker. Right: grouped by sector so you
            # can see concentration risk (e.g. too much Tech).
            # ---------------------------------------------
            st.subheader("Allocation")
            pcol1, pcol2 = st.columns(2)

            with pcol1:
                st.markdown("**By Holding**")
                pie_fig = px.pie(results_df, names="Ticker", values="Current Value", hole=0.4)
                pie_fig.update_traces(textinfo="percent+label")
                style_chart(pie_fig, height=400, xaxis_title="")
                st.plotly_chart(pie_fig, use_container_width=True)

            with pcol2:
                st.markdown("**By Sector**")
                sector_df = results_df.groupby("Sector", as_index=False)["Current Value"].sum()
                sector_fig = px.pie(sector_df, names="Sector", values="Current Value", hole=0.4)
                sector_fig.update_traces(textinfo="percent+label")
                style_chart(sector_fig, height=400, xaxis_title="")
                st.plotly_chart(sector_fig, use_container_width=True)

            st.divider()

            # ---------------------------------------------
            # PERFORMANCE VS. BENCHMARK OVER THE PAST YEAR
            # Approximation: assume you held your CURRENT share
            # counts for the whole past year, then compare the
            # resulting value path to the same dollars in SPY.
            # ---------------------------------------------
            st.subheader("Performance vs. Benchmark (Past Year)")
            st.caption(
                "Approximate: assumes you held your current share counts for the whole year. "
                "Compared against the same starting dollars invested in SPY."
            )

            # Build a combined table of each holding's daily value.
            value_frames = []
            perf_failed = []
            for _, row in results_df.iterrows():
                ticker = row["Ticker"]
                shares = row["Shares"]
                _, hist, err = get_stock_data(ticker)
                if err or hist is None or hist.empty:
                    perf_failed.append(ticker)
                    continue
                value_frames.append((hist["Close"] * shares).rename(ticker))

            if value_frames:
                # Add up all holdings' values on each date.
                portfolio_value = pd.concat(value_frames, axis=1).dropna().sum(axis=1)

                if not portfolio_value.empty:
                    start_value = portfolio_value.iloc[0]

                    # Benchmark: same starting dollars in SPY.
                    _, spy_hist, spy_err = get_stock_data("SPY")
                    perf_fig = go.Figure()
                    perf_fig.add_trace(go.Scatter(
                        x=portfolio_value.index, y=portfolio_value.values,
                        mode="lines", name="Your Portfolio", line=dict(color=COLOR_PRIMARY)
                    ))
                    if not spy_err and spy_hist is not None and not spy_hist.empty:
                        spy_close = spy_hist["Close"]
                        spy_close = spy_close[spy_close.index.isin(portfolio_value.index)]
                        if not spy_close.empty:
                            spy_value = start_value * (spy_close / spy_close.iloc[0])
                            perf_fig.add_trace(go.Scatter(
                                x=spy_value.index, y=spy_value.values,
                                mode="lines", name="SPY (S&P 500)",
                                line=dict(color=COLOR_PURPLE, dash="dot")
                            ))
                    style_chart(perf_fig, height=450, yaxis_title="Value (USD)", y_dollar=True)
                    st.plotly_chart(perf_fig, use_container_width=True)

            if perf_failed:
                st.caption(f"(Couldn't include in the chart: {', '.join(perf_failed)})")

            st.divider()

            # ---------------------------------------------
            # DIVERSIFICATION & CORRELATION
            # If your holdings tend to move together (high
            # correlation), you have less diversification than
            # the number of names suggests. We show a heatmap
            # plus a 0-100 diversification score.
            # ---------------------------------------------
            st.subheader("Diversification & Correlation")

            if len(results_df) < 2:
                st.info("Add at least two holdings to analyze diversification.")
            else:
                return_frames = []
                for ticker in results_df["Ticker"]:
                    _, hist, err = get_stock_data(ticker)
                    if not err and hist is not None and not hist.empty:
                        return_frames.append(hist["Close"].pct_change().rename(ticker))

                if len(return_frames) < 2:
                    st.info("Couldn't load enough price history to analyze correlation.")
                else:
                    rets = pd.concat(return_frames, axis=1).dropna()
                    corr = rets.corr()

                    # Average correlation between different holdings.
                    mask = ~np.eye(len(corr), dtype=bool)
                    avg_corr = corr.values[mask].mean()

                    # "Effective number of positions" from how evenly
                    # money is spread (Herfindahl index of weights).
                    weights = (results_df.set_index("Ticker").loc[corr.columns, "Weight (%)"] / 100).values
                    hhi = float((weights ** 2).sum())
                    eff_positions = (1 / hhi) if hhi > 0 else 0

                    # Diversification score: reward low correlation and
                    # an even spread across many names.
                    corr_score = max(0.0, min(100.0, (1 - avg_corr) * 100))
                    spread_score = min(eff_positions / len(corr.columns), 1.0) * 100
                    div_score = 0.6 * corr_score + 0.4 * spread_score

                    if div_score >= 70:
                        verdict = "Well diversified"
                    elif div_score >= 45:
                        verdict = "Moderately diversified"
                    else:
                        verdict = "Concentrated / holdings move together"

                    dv1, dv2, dv3 = st.columns(3)
                    dv1.metric("Diversification Score", f"{div_score:.0f}/100", verdict)
                    dv2.metric("Avg. Correlation", f"{avg_corr:.2f}",
                               help="0 = move independently, 1 = move in lockstep. Lower is more diversified.")
                    dv3.metric("Effective # of Positions", f"{eff_positions:.1f}",
                               help="How many truly independent bets you have, accounting for position sizes.")

                    heat = px.imshow(
                        corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                        zmin=-1, zmax=1, aspect="auto",
                    )
                    style_chart(heat, height=450, xaxis_title="", yaxis_title="")
                    st.plotly_chart(heat, use_container_width=True)
                    st.caption(
                        "Red = holdings move together (less diversification benefit); "
                        "blue = they move oppositely (more cushion). A portfolio of similar tech stocks, "
                        "for example, will look very red."
                    )


# ===========================================================
# PAGE 3: SCREENER
# Lets you compare several tickers side-by-side in one table.
# ===========================================================
elif page == "Screener":
    st.caption("Compare several tickers side by side (comma-separated).")

    # -------------------------------------------------------
    # USER INPUT: a comma-separated list of tickers.
    # We split on commas, strip extra spaces, capitalize, and
    # remove any blanks/duplicates while keeping the order.
    # -------------------------------------------------------
    screener_input = st.text_input(
        "Tickers to compare:", value="AAPL, MSFT, VOO", key="screener_input"
    )

    # Load the tickers you own so we can highlight / optionally
    # include them in the comparison.
    owned_tickers = set(load_portfolio_holdings()["Ticker"].tolist())
    include_owned = False
    if owned_tickers:
        include_owned = st.checkbox(
            f"Also include my {len(owned_tickers)} portfolio holding(s)",
            value=False,
            help="Adds the tickers from your saved portfolio to the comparison.",
        )

    raw_tickers = [t.strip().upper() for t in screener_input.split(",")]
    if include_owned:
        raw_tickers += sorted(owned_tickers)
    screener_tickers = list(dict.fromkeys([t for t in raw_tickers if t]))  # de-duplicate, keep order

    if not screener_tickers:
        empty_state("Enter at least one ticker above to get started.")
    else:
        screener_rows = []
        screener_errors = []

        price_series = {}  # ticker -> 1-year close prices (for the normalized chart)

        # Warm the cache with a spinner so the user sees progress;
        # the loop below then reads the cached results instantly.
        with st.spinner(f"Loading {len(screener_tickers)} ticker(s)…"):
            for _t in screener_tickers:
                get_stock_data(_t)

        for ticker in screener_tickers:
            info, history, error = get_stock_data(ticker)

            if error:
                screener_errors.append(ticker)
                continue

            # Calculate the simple 1-year return: how much the price
            # changed from the first day in our history to the last day.
            start_price = history["Close"].iloc[0]
            end_price = history["Close"].iloc[-1]
            one_year_return_pct = ((end_price - start_price) / start_price) * 100

            # Year-to-date return: change from the first trading day
            # of the current calendar year to now.
            this_year = history[history.index.year == pd.Timestamp.now().year]["Close"]
            ytd_return_pct = ((end_price - this_year.iloc[0]) / this_year.iloc[0] * 100) if not this_year.empty else None

            week_high = info.get("fiftyTwoWeekHigh", None)
            # How far below its 52-week high the stock is currently trading.
            pct_off_high = ((week_high - end_price) / week_high * 100) if week_high else None

            # Save the price path for the normalized comparison chart.
            price_series[ticker] = history["Close"]

            screener_rows.append({
                "Ticker": ticker,
                "Owned": "✓" if ticker in owned_tickers else "",
                "Name": info.get("longName", info.get("shortName", "N/A")),
                "Sector": info.get("sector", "Other / ETF"),
                "Price": end_price,
                "Market Cap": info.get("marketCap", None),
                "P/E Ratio": info.get("trailingPE", None),
                "Forward P/E": info.get("forwardPE", None),
                "Dividend Yield": info.get("dividendYield", None),
                "ROE": info.get("returnOnEquity", None),
                "Profit Margin": info.get("profitMargins", None),
                "Beta": info.get("beta", None),
                "% Off High": pct_off_high,
                "YTD Return": ytd_return_pct,
                "1-Yr Return": one_year_return_pct,
            })

        if screener_errors:
            st.warning(f"Couldn't find data for: {', '.join(screener_errors)}. Check these tickers are spelled correctly.")

        if screener_rows:
            screener_df = pd.DataFrame(screener_rows)

            # ---------------------------------------------
            # COLOR-CODED, SORTABLE COMPARISON TABLE
            # We keep the numbers as real numbers (not text) so
            # the table stays sortable by clicking a column. A
            # pandas "Styler" colors gains green and losses red,
            # and column_config controls how each number looks.
            # ---------------------------------------------
            st.subheader("Comparison Table")
            caption = "Click any column header to sort. Green = gains, red = losses."
            if owned_tickers:
                caption += " Tickers you own are marked ✓ and shaded."
            st.caption(caption)

            # Columns where positive should be green and negative red.
            return_cols = ["YTD Return", "1-Yr Return"]

            def color_returns(val):
                if pd.isna(val):
                    return ""
                return "color: #37d67a;" if val >= 0 else "color: #ff5c5c;"

            # Shade the whole row faint blue for tickers you own.
            def highlight_owned(row):
                if row["Owned"] == "✓":
                    return ["background-color: rgba(59,158,255,0.12)"] * len(row)
                return [""] * len(row)

            styler = screener_df.style.map(color_returns, subset=return_cols)
            styler = styler.apply(highlight_owned, axis=1)

            st.dataframe(
                styler,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "Market Cap": st.column_config.NumberColumn(
                        "Market Cap", format="compact", help="Total value of all shares — company size."),
                    "P/E Ratio": st.column_config.NumberColumn(
                        "P/E", format="%.2f", help="Price ÷ yearly earnings. Lower can mean cheaper."),
                    "Forward P/E": st.column_config.NumberColumn(
                        "Fwd P/E", format="%.2f", help="P/E using expected future earnings."),
                    "Dividend Yield": st.column_config.NumberColumn(
                        "Div Yield", format="percent", help="Annual dividends as a % of price."),
                    "ROE": st.column_config.NumberColumn(
                        "ROE", format="percent", help="Return on equity — profit per $1 of shareholder money."),
                    "Profit Margin": st.column_config.NumberColumn(
                        "Profit Margin", format="percent", help="% of revenue kept as profit."),
                    "Beta": st.column_config.NumberColumn(
                        "Beta", format="%.2f", help="Volatility vs. the market. 1 = moves with it."),
                    "% Off High": st.column_config.NumberColumn(
                        "% Off High", format="%.1f%%", help="How far below its 52-week high it trades."),
                    "YTD Return": st.column_config.NumberColumn(
                        "YTD Return", format="%.2f%%", help="Return since the start of this calendar year."),
                    "1-Yr Return": st.column_config.NumberColumn(
                        "1-Yr Return", format="%.2f%%", help="Price change over the past year."),
                },
            )

            # ---------------------------------------------
            # DOWNLOAD BUTTON
            # Lets you export the raw comparison data to a CSV
            # spreadsheet you can open in Excel.
            # ---------------------------------------------
            st.download_button(
                "Download as CSV",
                data=screener_df.to_csv(index=False).encode("utf-8"),
                file_name="screener_comparison.csv",
                mime="text/csv",
            )

            st.divider()

            # ---------------------------------------------
            # 1-YEAR RETURN BAR CHART
            # A quick visual of which ticker performed best.
            # ---------------------------------------------
            st.subheader("1-Year Return Comparison")
            bar_fig = px.bar(
                screener_df,
                x="Ticker",
                y="1-Yr Return",
                color="Ticker",
                text=screener_df["1-Yr Return"].map("{:+.1f}%".format),
            )
            style_chart(bar_fig, height=450, yaxis_title="1-Year Return (%)", xaxis_title="Ticker", y_percent=True)
            bar_fig.update_layout(showlegend=False)
            st.plotly_chart(bar_fig, use_container_width=True)

            st.divider()

            # ---------------------------------------------
            # NORMALIZED PRICE CHART
            # Every ticker is rebased to 100 at the start of the
            # past year, so you compare growth paths directly
            # regardless of each stock's actual dollar price.
            # ---------------------------------------------
            st.subheader("Growth Comparison (Rebased to 100)")
            st.caption("Each line starts at 100 one year ago, so you can compare percentage growth, not dollar price.")
            norm_fig = go.Figure()
            for ticker, closes in price_series.items():
                normalized = closes / closes.iloc[0] * 100
                norm_fig.add_trace(go.Scatter(
                    x=normalized.index, y=normalized.values, mode="lines", name=ticker
                ))
            style_chart(norm_fig, height=450, yaxis_title="Growth (start = 100)")
            st.plotly_chart(norm_fig, use_container_width=True)

            st.divider()

            # One-click: add any compared ticker to the watchlist.
            sc_add = st.multiselect(
                "Add tickers to your watchlist:", screener_df["Ticker"].tolist(), key="screener_add"
            )
            if st.button("Add selected to Watchlist", key="screener_add_btn"):
                added = add_tickers_to_watchlist(sc_add)
                if added:
                    st.success(f"Added {added} ticker(s) to your watchlist.")
                else:
                    st.info("Nothing new to add (they may already be on your watchlist).")


# ===========================================================
# PAGE 4: BACKTESTER
# Tests a simple moving-average crossover strategy:
#   - BUY (go to 100% invested) when the short-term moving
#     average crosses ABOVE the long-term moving average
#   - SELL (go to 100% cash) when the short-term moving
#     average crosses BELOW the long-term moving average
# Then compares that strategy to buying & holding the stock,
# and to a benchmark of your choice, and reports risk stats.
# ===========================================================
elif page == "Backtester":
    st.caption("Test a strategy on historical data vs. buy & hold and a benchmark.")

    # -------------------------------------------------------
    # CHOOSE A STRATEGY
    # Two options:
    #   - "Moving Average Crossover": invested when the short MA
    #     is above the long MA.
    #   - "RSI (buy low / sell high)": buy when RSI falls into
    #     oversold territory, sell when it climbs into overbought.
    # -------------------------------------------------------
    strategy = st.radio(
        "Strategy:",
        ["Moving Average Crossover", "RSI (buy low / sell high)"],
        horizontal=True,
    )

    # -------------------------------------------------------
    # COMMON INPUTS (used by both strategies)
    # -------------------------------------------------------
    bt_col1, bt_col2, bt_col3 = st.columns(3)
    bt_ticker = bt_col1.text_input("Ticker:", value="AAPL", key="bt_ticker",
                                   help="The stock or ETF to test the strategy on.").strip().upper()
    bt_period = bt_col2.selectbox("Test period:", ["2y", "5y", "10y", "max"], index=1,
                                  help="How far back to run the simulation.")
    bt_investment = bt_col3.number_input("Starting investment ($):", min_value=100.0, value=10000.0, step=100.0,
                                         help="The hypothetical amount invested at the start.")

    # -------------------------------------------------------
    # STRATEGY-SPECIFIC INPUTS (only the relevant ones show)
    # -------------------------------------------------------
    if strategy == "Moving Average Crossover":
        c4, c5, c6 = st.columns(3)
        short_window = int(c4.number_input("Short moving average (days):", min_value=2, value=50, step=1,
                                           help="The faster average. Buy signal fires when it crosses above the long one."))
        long_window = int(c5.number_input("Long moving average (days):", min_value=5, value=200, step=1,
                                          help="The slower average. Sell signal fires when the short one drops below it."))
        benchmark_ticker = c6.text_input("Benchmark ticker:", value="SPY", key="bt_benchmark",
                                         help="A reference to compare against (default SPY = S&P 500).").strip().upper()
        min_required = long_window
        strategy_label = f"{short_window}/{long_window} MA"
    else:
        c4, c5, c6, c7 = st.columns(4)
        rsi_period = int(c4.number_input("RSI period (days):", min_value=2, value=14, step=1,
                                         help="How many days the RSI looks back over. 14 is standard."))
        rsi_oversold = c5.number_input("Buy below (oversold):", min_value=5, max_value=50, value=30, step=1,
                                       help="Buy when RSI dips below this 'oversold' level.")
        rsi_overbought = c6.number_input("Sell above (overbought):", min_value=50, max_value=95, value=70, step=1,
                                         help="Sell when RSI rises above this 'overbought' level.")
        benchmark_ticker = c7.text_input("Benchmark ticker:", value="SPY", key="bt_benchmark",
                                         help="A reference to compare against (default SPY = S&P 500).").strip().upper()
        min_required = rsi_period + 1
        strategy_label = f"RSI {rsi_period} ({rsi_oversold}/{rsi_overbought})"

    # -------------------------------------------------------
    # HELPER: download historical prices for a ticker/period.
    # Defined once and reused for the stock AND the benchmark.
    # -------------------------------------------------------
    @st.cache_data(ttl=3600)
    def get_backtest_history(ticker: str, period: str):
        try:
            history = yf.Ticker(ticker).history(period=period)
            if history.empty:
                return None, f"No data found for ticker '{ticker}'."
            return history, None
        except Exception as e:
            return None, f"Something went wrong while fetching data: {e}"

    # Guard: MA crossover needs the short window to be smaller.
    invalid = strategy == "Moving Average Crossover" and short_window >= long_window
    if invalid:
        st.error("The short moving average must be smaller than the long moving average.")
    elif bt_ticker:
        bt_history, bt_error = get_backtest_history(bt_ticker, bt_period)

        if bt_error:
            st.error(bt_error)
        elif len(bt_history) < min_required:
            st.error(
                f"Not enough price history ({len(bt_history)} days) for this strategy's settings. "
                "Pick a longer test period or smaller windows."
            )
        else:
            # -------------------------------------------------
            # FIGURE OUT THE STRATEGY'S POSITION EACH DAY
            # 1 = invested, 0 = in cash. The logic differs by
            # strategy, but everything afterward is shared.
            # -------------------------------------------------
            df = bt_history[["Close"]].copy()

            if strategy == "Moving Average Crossover":
                df["ShortMA"] = df["Close"].rolling(window=short_window).mean()
                df["LongMA"] = df["Close"].rolling(window=long_window).mean()
                # Invested whenever the short MA is above the long MA.
                df["Position"] = 0
                df.loc[df["ShortMA"] > df["LongMA"], "Position"] = 1
                warmup_col = "LongMA"
            else:
                # --- Compute RSI (Relative Strength Index) ---
                # RSI measures recent gains vs. losses on a 0-100
                # scale. Low (<30) = "oversold", high (>70) =
                # "overbought".
                delta = df["Close"].diff()
                gain = delta.clip(lower=0)
                loss = -delta.clip(upper=0)
                avg_gain = gain.rolling(window=rsi_period).mean()
                avg_loss = loss.rolling(window=rsi_period).mean()
                rs = avg_gain / avg_loss.replace(0, np.nan)
                df["RSI"] = 100 - (100 / (1 + rs))

                # Walk day by day: buy when RSI dips below the
                # oversold line, sell when it rises above the
                # overbought line, otherwise hold the prior stance.
                positions = []
                holding = 0
                for rsi_val in df["RSI"]:
                    if pd.notna(rsi_val):
                        if rsi_val < rsi_oversold:
                            holding = 1
                        elif rsi_val > rsi_overbought:
                            holding = 0
                    positions.append(holding)
                df["Position"] = positions
                warmup_col = "RSI"

            # Shift by 1 day: we can only act the day AFTER a signal
            # (you can't trade on a closing price before it's known).
            df["Position"] = df["Position"].shift(1).fillna(0)

            # Drop the early "warm-up" rows where the indicator
            # isn't available yet.
            df = df.dropna(subset=[warmup_col]).copy()

            # -------------------------------------------------
            # SIMULATE GROWTH OF THE STARTING INVESTMENT
            # Daily return = % change in price from the day before.
            # Strategy return = daily return, but only counted on
            # days we were actually "in the market" (Position == 1).
            # -------------------------------------------------
            df["DailyReturn"] = df["Close"].pct_change().fillna(0)
            df["StrategyReturn"] = df["DailyReturn"] * df["Position"]

            df["BuyHoldValue"] = bt_investment * (1 + df["DailyReturn"]).cumprod()
            df["StrategyValue"] = bt_investment * (1 + df["StrategyReturn"]).cumprod()

            final_buyhold = df["BuyHoldValue"].iloc[-1]
            final_strategy = df["StrategyValue"].iloc[-1]
            buyhold_return_pct = (final_buyhold / bt_investment - 1) * 100
            strategy_return_pct = (final_strategy / bt_investment - 1) * 100

            # -------------------------------------------------
            # RISK STAT 1: SHARPE RATIO
            # Roughly, return earned per unit of "bumpiness"
            # (volatility). Higher is better. We use the simple
            # version (no risk-free rate) and annualize by
            # multiplying by the square root of ~252 trading days.
            # -------------------------------------------------
            daily_strat = df["StrategyReturn"]
            if daily_strat.std() > 0:
                sharpe = (daily_strat.mean() / daily_strat.std()) * np.sqrt(252)
            else:
                sharpe = 0.0

            # -------------------------------------------------
            # RISK STAT 2: MAX DRAWDOWN
            # The worst peak-to-trough drop the strategy ever
            # experienced - i.e. the biggest % loss from a high
            # point. Less negative is better.
            # -------------------------------------------------
            running_max = df["StrategyValue"].cummax()
            drawdown = (df["StrategyValue"] / running_max - 1)
            max_drawdown_pct = drawdown.min() * 100

            # -------------------------------------------------
            # RISK STAT 3 & 4: NUMBER OF TRADES + WIN RATE
            # A "trade" is one full round trip: buy, then later
            # sell. We find the days the position flips from
            # cash->invested (a buy) and invested->cash (a sell),
            # then check whether the price was higher at the sell
            # than at the buy (a "win").
            # -------------------------------------------------
            position = df["Position"].values
            close = df["Close"].values
            dates = df.index
            trade_records = []   # full details for the trade log
            entry_price = None
            entry_date = None
            for i in range(len(position)):
                # Flip from 0 to 1 = we just bought
                if position[i] == 1 and (i == 0 or position[i - 1] == 0):
                    entry_price = close[i]
                    entry_date = dates[i]
                # Flip from 1 to 0 = we just sold
                elif position[i] == 0 and i > 0 and position[i - 1] == 1 and entry_price is not None:
                    trade_records.append({
                        "Entry Date": entry_date, "Entry Price": entry_price,
                        "Exit Date": dates[i], "Exit Price": close[i],
                        "Return": close[i] / entry_price - 1, "Status": "Closed",
                    })
                    entry_price = None
                    entry_date = None
            # If still holding at the very end, mark it as an open trade.
            if entry_price is not None:
                trade_records.append({
                    "Entry Date": entry_date, "Entry Price": entry_price,
                    "Exit Date": dates[-1], "Exit Price": close[-1],
                    "Return": close[-1] / entry_price - 1, "Status": "Open (still held)",
                })

            trades = [t["Return"] for t in trade_records]
            num_trades = len(trades)
            wins = sum(1 for r in trades if r > 0)
            win_rate_pct = (wins / num_trades * 100) if num_trades > 0 else 0

            # -------------------------------------------------
            # RISK STAT 5: CAGR (annualized return)
            # The single yearly growth rate that would turn the
            # starting amount into the final amount over the
            # actual number of years tested.
            # -------------------------------------------------
            years = max((df.index[-1] - df.index[0]).days / 365.25, 0.01)
            cagr_pct = ((final_strategy / bt_investment) ** (1 / years) - 1) * 100

            # -------------------------------------------------
            # RISK STAT 6: ANNUAL VOLATILITY
            # How bumpy the strategy's daily returns are, scaled
            # up to a yearly figure. Lower = smoother ride.
            # -------------------------------------------------
            annual_volatility_pct = daily_strat.std() * np.sqrt(252) * 100

            # -------------------------------------------------
            # BENCHMARK: grow the same starting investment in the
            # benchmark ticker over the EXACT same dates, so the
            # comparison is apples-to-apples.
            # -------------------------------------------------
            benchmark_value = None
            benchmark_return_pct = None
            if benchmark_ticker:
                bench_history, bench_error = get_backtest_history(benchmark_ticker, bt_period)
                if bench_error or bench_history is None or bench_history.empty:
                    st.warning(f"Couldn't load benchmark '{benchmark_ticker}', so it won't be shown.")
                else:
                    bench = bench_history[["Close"]].copy()
                    # Line the benchmark up to the same date range as the strategy.
                    bench = bench[bench.index.isin(df.index)]
                    if not bench.empty:
                        bench["DailyReturn"] = bench["Close"].pct_change().fillna(0)
                        bench["Value"] = bt_investment * (1 + bench["DailyReturn"]).cumprod()
                        benchmark_value = bench
                        benchmark_return_pct = (bench["Value"].iloc[-1] / bt_investment - 1) * 100

            # -------------------------------------------------
            # SHOW THE HEADLINE RESULTS
            # -------------------------------------------------
            st.header("Results")
            rcol1, rcol2, rcol3 = st.columns(3)
            rcol1.metric(
                f"Strategy ({strategy_label})",
                f"${final_strategy:,.2f}",
                f"{strategy_return_pct:+.2f}%",
            )
            rcol2.metric(
                "Buy & Hold",
                f"${final_buyhold:,.2f}",
                f"{buyhold_return_pct:+.2f}%",
            )
            if benchmark_return_pct is not None:
                rcol3.metric(
                    f"Benchmark ({benchmark_ticker})",
                    f"${benchmark_value['Value'].iloc[-1]:,.2f}",
                    f"{benchmark_return_pct:+.2f}%",
                )

            st.divider()

            # -------------------------------------------------
            # SHOW THE RISK STATS (two rows of four)
            # -------------------------------------------------
            st.subheader("Strategy Risk & Trade Stats")
            scol1, scol2, scol3, scol4 = st.columns(4)
            scol1.metric("Annualized Return (CAGR)", f"{cagr_pct:.2f}%")
            scol2.metric("Annual Volatility", f"{annual_volatility_pct:.2f}%")
            scol3.metric("Sharpe Ratio", f"{sharpe:.2f}")
            scol4.metric("Max Drawdown", f"{max_drawdown_pct:.2f}%")

            scol5, scol6, scol7, scol8 = st.columns(4)
            scol5.metric("Number of Trades", f"{num_trades}")
            scol6.metric("Win Rate", f"{win_rate_pct:.0f}%")

            st.caption(
                "CAGR = the steady yearly growth rate that produces this result. "
                "Volatility = how bumpy the ride was (lower is smoother). "
                "Sharpe ratio = return per unit of risk (>1 is decent). "
                "Max drawdown = the worst drop from a peak. "
                "Win rate = the share of completed trades that made money."
            )

            st.divider()

            # -------------------------------------------------
            # PRICE CHART WITH BUY/SELL MARKERS
            # Shows the stock price with the moving averages and
            # green ▲ where the strategy bought, red ▼ where it
            # sold, so you can see exactly when it traded.
            # -------------------------------------------------
            st.subheader("Trades on the Price Chart")

            # Find the buy days (position goes 0 -> 1) and sell
            # days (position goes 1 -> 0).
            pos = df["Position"]
            buy_days = df.index[(pos == 1) & (pos.shift(1) == 0)]
            sell_days = df.index[(pos == 0) & (pos.shift(1) == 1)]

            price_fig = go.Figure()
            price_fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"], mode="lines", name="Price",
                line=dict(color=COLOR_PRIMARY)
            ))
            # Only the MA strategy has moving-average lines to draw.
            if strategy == "Moving Average Crossover":
                price_fig.add_trace(go.Scatter(
                    x=df.index, y=df["ShortMA"], mode="lines",
                    name=f"{short_window}-day MA", line=dict(color=COLOR_ACCENT, width=1)
                ))
                price_fig.add_trace(go.Scatter(
                    x=df.index, y=df["LongMA"], mode="lines",
                    name=f"{long_window}-day MA", line=dict(color=COLOR_GREEN, width=1)
                ))
            price_fig.add_trace(go.Scatter(
                x=buy_days, y=df.loc[buy_days, "Close"], mode="markers", name="Buy",
                marker=dict(color=COLOR_GREEN, size=11, symbol="triangle-up")
            ))
            price_fig.add_trace(go.Scatter(
                x=sell_days, y=df.loc[sell_days, "Close"], mode="markers", name="Sell",
                marker=dict(color="#ff5c5c", size=11, symbol="triangle-down")
            ))
            style_chart(price_fig, height=500, yaxis_title="Price (USD)", y_dollar=True)
            st.plotly_chart(price_fig, use_container_width=True)

            # For the RSI strategy, show the RSI line with the
            # oversold/overbought thresholds so the signals make sense.
            if strategy == "RSI (buy low / sell high)":
                rsi_fig = go.Figure()
                rsi_fig.add_trace(go.Scatter(
                    x=df.index, y=df["RSI"], mode="lines", name="RSI",
                    line=dict(color=COLOR_ACCENT)
                ))
                rsi_fig.add_hline(y=rsi_overbought, line_dash="dash", line_color="#ff5c5c",
                                  annotation_text="Overbought")
                rsi_fig.add_hline(y=rsi_oversold, line_dash="dash", line_color=COLOR_GREEN,
                                  annotation_text="Oversold")
                style_chart(rsi_fig, height=280, yaxis_title="RSI (0–100)")
                st.plotly_chart(rsi_fig, use_container_width=True)

            st.divider()

            # -------------------------------------------------
            # TRADE LOG TABLE
            # Every completed (and any still-open) trade: when it
            # was entered/exited, at what price, and its return.
            # -------------------------------------------------
            st.subheader("Trade Log")
            if trade_records:
                log_df = pd.DataFrame(trade_records)
                log_df["Entry Date"] = pd.to_datetime(log_df["Entry Date"]).dt.strftime("%Y-%m-%d")
                log_df["Exit Date"] = pd.to_datetime(log_df["Exit Date"]).dt.strftime("%Y-%m-%d")
                log_df["Entry Price"] = log_df["Entry Price"].map("${:,.2f}".format)
                log_df["Exit Price"] = log_df["Exit Price"].map("${:,.2f}".format)
                log_df["Return"] = (log_df["Return"] * 100).map("{:+.2f}%".format)
                st.dataframe(log_df, use_container_width=True, hide_index=True)
            else:
                st.info("This strategy never entered the market with the current settings.")

            st.divider()

            # -------------------------------------------------
            # EQUITY CURVE CHART
            # Shows how the starting investment would have grown
            # under the strategy, buy & hold, and the benchmark.
            # -------------------------------------------------
            st.subheader("Growth of Starting Investment")
            equity_fig = go.Figure()
            equity_fig.add_trace(go.Scatter(
                x=df.index, y=df["StrategyValue"],
                mode="lines", name=f"{strategy_label} Strategy",
                line=dict(color=COLOR_PRIMARY)
            ))
            equity_fig.add_trace(go.Scatter(
                x=df.index, y=df["BuyHoldValue"],
                mode="lines", name="Buy & Hold", line=dict(color=COLOR_GRAY, dash="dash")
            ))
            if benchmark_value is not None:
                equity_fig.add_trace(go.Scatter(
                    x=benchmark_value.index, y=benchmark_value["Value"],
                    mode="lines", name=f"Benchmark ({benchmark_ticker})",
                    line=dict(color=COLOR_PURPLE, dash="dot")
                ))
            style_chart(equity_fig, height=500, yaxis_title="Portfolio Value (USD)", y_dollar=True)
            st.plotly_chart(equity_fig, use_container_width=True)

            st.divider()

            # -------------------------------------------------
            # DRAWDOWN ("UNDERWATER") CHART
            # Plots how far below its previous peak the strategy
            # was at each point in time. It's always 0 or negative;
            # the deepest dip is the max drawdown shown above.
            # -------------------------------------------------
            st.subheader("Drawdown Over Time")
            st.caption("How far the strategy was below its prior high at each point. Deeper = more painful losses.")
            dd_fig = go.Figure()
            dd_fig.add_trace(go.Scatter(
                x=df.index, y=drawdown.values * 100, mode="lines", name="Drawdown",
                fill="tozeroy", line=dict(color="#ff5c5c")
            ))
            style_chart(dd_fig, height=350, yaxis_title="Drawdown (%)", y_percent=True)
            st.plotly_chart(dd_fig, use_container_width=True)

            st.caption(
                "Note: this is a simplified educational simulation. It ignores trading fees, "
                "taxes, slippage, and dividends, and past performance never guarantees "
                "future results."
            )


# ===========================================================
# PAGE: BONDS / TREASURIES
# The Treasury yield curve, the 10yr-2yr spread (a recession
# signal) with a plain-English read, and a table of common
# bond ETFs you can actually invest in.
# ===========================================================
elif page == "Bonds":
    st.caption("Treasury yields, the yield curve, and common bond ETFs.")

    # -------------------------------------------------------
    # 1) THE TREASURY YIELD CURVE
    # We fetch the latest yield for each maturity from FRED and
    # plot yield vs. maturity. A normal curve slopes up; an
    # inverted one (down) has often preceded recessions.
    # -------------------------------------------------------
    st.header("Treasury Yield Curve")

    # (label, FRED code, maturity in years for ordering)
    maturities = [
        ("1mo", "DGS1MO", 1 / 12), ("3mo", "DGS3MO", 0.25), ("6mo", "DGS6MO", 0.5),
        ("1yr", "DGS1", 1), ("2yr", "DGS2", 2), ("3yr", "DGS3", 3), ("5yr", "DGS5", 5),
        ("7yr", "DGS7", 7), ("10yr", "DGS10", 10), ("20yr", "DGS20", 20), ("30yr", "DGS30", 30),
    ]

    curve_rows = []
    with st.spinner("Loading Treasury yields…"):
        for label, code, years in maturities:
            data, err = get_fred_series(code, years_back=1)
            if not err and data is not None and not data.empty:
                curve_rows.append({"Maturity": label, "Years": years, "Yield": data[code].dropna().iloc[-1]})

    if not curve_rows:
        st.error("Couldn't load Treasury yields right now (FRED may be temporarily unavailable). Try again later.")
    else:
        curve_df = pd.DataFrame(curve_rows).sort_values("Years")
        curve_fig = go.Figure()
        curve_fig.add_trace(go.Scatter(
            x=curve_df["Maturity"], y=curve_df["Yield"],
            mode="lines+markers", name="Yield", line=dict(color=COLOR_PRIMARY)
        ))
        style_chart(curve_fig, height=400, yaxis_title="Yield (%)", xaxis_title="Maturity", y_percent=True)
        st.plotly_chart(curve_fig, use_container_width=True)

    st.divider()

    # -------------------------------------------------------
    # 2) THE 10yr - 2yr SPREAD (RECESSION SIGNAL)
    # When this goes negative ("inverted"), long-term yields
    # are below short-term ones, which has historically often
    # come before recessions.
    # -------------------------------------------------------
    st.header("Yield Curve Spread (10yr − 2yr)")
    spread_data, spread_err = get_fred_series("T10Y2Y", years_back=10)

    if spread_err or spread_data is None or spread_data.empty:
        st.warning("Couldn't load the 10yr−2yr spread right now.")
    else:
        spread_now = spread_data["T10Y2Y"].dropna().iloc[-1]

        # Plain-English interpretation.
        if spread_now < 0:
            verdict = "Inverted"
            explanation = ("Long-term yields are BELOW short-term yields. An inverted curve has "
                           "historically often (not always) preceded recessions by 6–18 months.")
        elif spread_now < 0.5:
            verdict = "Flat"
            explanation = ("The curve is fairly flat — the market sees little extra reward for "
                           "lending longer. Often a sign of uncertainty about the economy.")
        else:
            verdict = "Normal (upward sloping)"
            explanation = ("Longer-term yields are healthily above short-term ones — the typical, "
                           "historically 'healthy' shape.")

        sc1, sc2 = st.columns([1, 2])
        sc1.metric("Current 10yr − 2yr", f"{spread_now:.2f}%", verdict)
        sc2.info(explanation)

        spread_fig = go.Figure()
        spread_fig.add_trace(go.Scatter(
            x=spread_data.index, y=spread_data["T10Y2Y"],
            mode="lines", name="10yr − 2yr", line=dict(color=COLOR_PRIMARY)
        ))
        # A zero line: below it = inverted.
        spread_fig.add_hline(y=0, line_dash="dash", line_color="#ff5c5c")
        style_chart(spread_fig, height=350, yaxis_title="Spread (%)", y_percent=True)
        st.plotly_chart(spread_fig, use_container_width=True)

    st.divider()

    # -------------------------------------------------------
    # 3) COMMON BOND ETFs YOU CAN ACTUALLY BUY
    # Treasury yields aren't directly investable, but these
    # ETFs are. We show price, yield, and 1-year return.
    # -------------------------------------------------------
    st.header("Common Bond ETFs")

    bond_etfs = [
        ("SHY", "1–3yr Treasuries (very safe, low yield)"),
        ("IEF", "7–10yr Treasuries"),
        ("TLT", "20+yr Treasuries (most rate-sensitive)"),
        ("BND", "Total U.S. bond market"),
        ("AGG", "U.S. aggregate bonds"),
        ("TIP", "Inflation-protected Treasuries (TIPS)"),
        ("LQD", "Investment-grade corporate bonds"),
        ("HYG", "High-yield ('junk') corporate bonds"),
    ]

    bond_rows = []
    bond_failed = []
    # Warm the cache with a spinner; the loop then reads it instantly.
    with st.spinner("Loading bond ETFs…"):
        for _t, _d in bond_etfs:
            get_stock_data(_t)
    for ticker, desc in bond_etfs:
        info, history, error = get_stock_data(ticker)
        if error or history is None or history.empty:
            bond_failed.append(ticker)
            continue
        price = history["Close"].iloc[-1]
        one_yr = (price / history["Close"].iloc[0] - 1) * 100
        bond_rows.append({
            "Ticker": ticker,
            "What it holds": desc,
            "Price": price,
            "Yield": info.get("yield") or info.get("dividendYield"),
            "1-Yr Return": one_yr,
        })

    if bond_failed:
        st.caption(f"(Couldn't load: {', '.join(bond_failed)})")

    if bond_rows:
        bond_df = pd.DataFrame(bond_rows)

        def color_ret(val):
            if pd.isna(val):
                return ""
            return "color: #37d67a;" if val >= 0 else "color: #ff5c5c;"

        styler = bond_df.style.map(color_ret, subset=["1-Yr Return"])
        st.dataframe(
            styler,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "Yield": st.column_config.NumberColumn(
                    "Yield", format="percent", help="Income paid out as a % of price (the fund's distribution yield)."),
                "1-Yr Return": st.column_config.NumberColumn(
                    "1-Yr Return", format="%.2f%%", help="Price change over the past year (excludes income paid out)."),
            },
        )
        st.caption(
            "Rule of thumb: longer-maturity bond funds (like TLT) swing more when interest rates move; "
            "shorter ones (like SHY) are steadier. Higher yield usually means higher risk."
        )


# ===========================================================
# PAGE: MUTUAL FUNDS
# A fund-tailored view: mutual funds don't have a P/E or the
# same fundamentals as a stock, so we show what actually
# matters for a fund — expense ratio, yield, ratings, and
# returns — plus a long-term growth chart.
# ===========================================================
elif page == "Mutual Funds":
    st.caption("Look up a fund for fees, ratings, and returns.")

    fund_ticker = st.text_input("Mutual fund ticker:", value="VFIAX", key="fund_ticker").strip().upper()

    if not fund_ticker:
        empty_state("Enter a mutual fund ticker to get started.")
    else:
        with st.spinner(f"Loading {fund_ticker}…"):
            info, history, error = get_fund_data(fund_ticker)
        if error:
            st.error(error)
        else:
            quote_type = info.get("quoteType", "")
            fund_name = info.get("longName", info.get("shortName", fund_ticker))
            st.subheader(f"{fund_name} ({fund_ticker})")

            # Gently warn if this isn't actually a mutual fund.
            if quote_type and quote_type != "MUTUALFUND":
                st.info(f"Heads up: '{fund_ticker}' looks like a {quote_type.title()}, not a mutual fund. "
                        "The Ticker Lookup page may suit it better.")

            # -------------------------------------------------
            # KEY FUND FACTS
            # Expense ratio and yield come back as decimals
            # (0.0004 = 0.04%); the return figures are already
            # in percent. Everything uses "N/A" when missing.
            # -------------------------------------------------
            expense = info.get("annualReportExpenseRatio")
            fund_yield = info.get("yield")
            total_assets = info.get("totalAssets")
            ms_rating = info.get("morningStarOverallRating")
            ms_risk = info.get("morningStarRiskRating")
            beta3 = info.get("beta3Year")
            ytd = info.get("ytdReturn")
            three_mo = info.get("trailingThreeMonthReturns")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Expense Ratio", f"{expense * 100:.2f}%" if expense is not None else "N/A",
                      help="Annual fee. Under ~0.20% is cheap; over ~1% is expensive.")
            c2.metric("Yield", f"{fund_yield * 100:.2f}%" if fund_yield is not None else "N/A",
                      help="Income paid out as a percent of price.")
            c3.metric("Total Assets", format_market_cap(total_assets) if total_assets else "N/A",
                      help="How much money the fund manages.")
            c4.metric("Beta (3yr)", fmt_ratio(beta3),
                      help="Volatility vs. the market. 1 = moves with the market.")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Morningstar Rating", f"{ms_rating}/5" if ms_rating else "N/A",
                      help="Morningstar's overall star rating (5 = best).")
            c6.metric("Risk Rating", f"{ms_risk}/5" if ms_risk else "N/A",
                      help="Morningstar risk rating (higher = riskier).")
            c7.metric("YTD Return", f"{ytd:+.2f}%" if ytd is not None else "N/A")
            c8.metric("3-Month Return", f"{three_mo:+.2f}%" if three_mo is not None else "N/A")

            # A plain-English note on the expense ratio.
            if expense is not None:
                if expense <= 0.002:
                    st.success(f"At {expense*100:.2f}%, this is a very low-cost fund — fees barely eat into returns.")
                elif expense >= 0.01:
                    st.warning(f"At {expense*100:.2f}%, this fund's fees are on the high side. Over decades, high fees compound against you.")

            st.divider()

            # -------------------------------------------------
            # GROWTH CHART (5-YEAR)
            # Mutual funds price once a day (NAV), so a simple
            # line of the closing NAV over time tells the story.
            # -------------------------------------------------
            st.subheader("5-Year Growth")
            fund_fig = go.Figure()
            fund_fig.add_trace(go.Scatter(
                x=history.index, y=history["Close"],
                mode="lines", name="NAV", line=dict(color=COLOR_PRIMARY)
            ))
            style_chart(fund_fig, height=450, yaxis_title="Price / NAV (USD)", y_dollar=True)
            st.plotly_chart(fund_fig, use_container_width=True)

            st.caption(
                "Funds are best judged on costs, diversification, and long-term consistency — "
                "not short-term price swings. Low fees are one of the few things you can control."
            )


# ===========================================================
# PAGE 5: MACRO DATA
# Shows key economic indicators from FRED (the Federal
# Reserve's free public database of economic data). This
# gives broader context for the stocks/ETFs you're analyzing
# elsewhere in the app.
# ===========================================================
elif page == "Macro Data":
    st.caption(
        "Key U.S. economic indicators from the Federal Reserve's public FRED database. "
        "Useful as background context for your stock/ETF analysis."
    )

    # -------------------------------------------------------
    # THE LIST OF INDICATORS WE WANT, GROUPED BY CATEGORY
    # Every dataset on FRED has a unique "series code". For each
    # one we record:
    #   label     - friendly name to display
    #   code      - the FRED series code
    #   category  - which group it belongs to (for layout)
    #   transform - "level" = use the number as-is
    #               "yoy"   = convert to year-over-year % change
    #               (used for things like CPI where the % change
    #                is what people actually care about)
    #   yoy_periods - how many data points back equals one year
    #                 (12 for monthly data, 4 for quarterly)
    #   fmt       - how to display the latest value
    #   help      - a plain-English explanation
    # -------------------------------------------------------
    MACRO_INDICATORS = [
        # --- Interest Rates & Bonds ---
        {"label": "Fed Funds Rate", "code": "FEDFUNDS", "category": "Interest Rates & Bonds",
         "transform": "level", "fmt": "pct", "help": "The Federal Reserve's key short-term interest rate."},
        {"label": "2-Year Treasury Yield", "code": "DGS2", "category": "Interest Rates & Bonds",
         "transform": "level", "fmt": "pct", "help": "Yield on 2-year U.S. government bonds."},
        {"label": "10-Year Treasury Yield", "code": "DGS10", "category": "Interest Rates & Bonds",
         "transform": "level", "fmt": "pct", "help": "Yield on 10-year U.S. government bonds."},
        {"label": "Yield Curve (10yr − 2yr)", "code": "T10Y2Y", "category": "Interest Rates & Bonds",
         "transform": "level", "fmt": "pct",
         "help": "10-year minus 2-year yield. When negative (inverted), it has historically preceded recessions."},
        # --- Inflation ---
        {"label": "CPI Inflation (YoY)", "code": "CPIAUCSL", "category": "Inflation",
         "transform": "yoy", "yoy_periods": 12, "fmt": "pct",
         "help": "How much consumer prices have risen vs. a year ago."},
        {"label": "Core PCE Inflation (YoY)", "code": "PCEPILFE", "category": "Inflation",
         "transform": "yoy", "yoy_periods": 12, "fmt": "pct",
         "help": "The Fed's preferred inflation gauge (excludes food & energy)."},
        # --- Growth & Output ---
        {"label": "Real GDP Growth (YoY)", "code": "GDPC1", "category": "Growth & Output",
         "transform": "yoy", "yoy_periods": 4, "fmt": "pct",
         "help": "How much the inflation-adjusted economy grew vs. a year ago."},
        # --- Jobs ---
        {"label": "Unemployment Rate", "code": "UNRATE", "category": "Jobs",
         "transform": "level", "fmt": "pct", "help": "Percent of the labor force without a job."},
        {"label": "Initial Jobless Claims", "code": "ICSA", "category": "Jobs",
         "transform": "level", "fmt": "count",
         "help": "New unemployment claims filed last week. Rising = labor market weakening."},
        # --- Sentiment & Risk ---
        {"label": "Consumer Sentiment", "code": "UMCSENT", "category": "Sentiment & Risk",
         "transform": "level", "fmt": "index",
         "help": "Survey of how optimistic consumers feel (University of Michigan)."},
        {"label": "VIX (Volatility Index)", "code": "VIXCLS", "category": "Sentiment & Risk",
         "transform": "level", "fmt": "index",
         "help": "The market's 'fear gauge.' Higher = more expected stock-market turbulence."},
    ]

    # (The FRED fetch helper "get_fred_series" is defined once
    #  near the top of the file and shared with the Overview page.)

    # -------------------------------------------------------
    # SMALL HELPER TO FORMAT A LATEST VALUE FOR DISPLAY
    # -------------------------------------------------------
    def fmt_macro(value, kind):
        if value is None or not pd.notna(value):
            return "N/A"
        if kind == "pct":
            return f"{value:.2f}%"
        if kind == "count":
            return f"{value:,.0f}"
        return f"{value:.1f}"  # "index" style (VIX, sentiment)

    # -------------------------------------------------------
    # FETCH EVERY INDICATOR AND BUILD ITS DISPLAY SERIES
    # For "yoy" indicators we convert the raw level into a
    # year-over-year percent change before storing it.
    # -------------------------------------------------------
    macro_errors = []
    macro_data = {}  # label -> {"series": pandas Series, "latest": number, "meta": dict}

    for ind in MACRO_INDICATORS:
        raw, error = get_fred_series(ind["code"])
        if error or raw is None or raw.empty:
            macro_errors.append(ind["label"])
            continue

        series = raw[ind["code"]].dropna()

        if ind["transform"] == "yoy":
            periods = ind.get("yoy_periods", 12)
            if len(series) <= periods:
                macro_errors.append(ind["label"])
                continue
            series = (series.pct_change(periods=periods) * 100).dropna()

        if series.empty:
            macro_errors.append(ind["label"])
            continue

        macro_data[ind["label"]] = {
            "series": series,
            "latest": series.iloc[-1],
            "meta": ind,
        }

    if macro_errors:
        st.warning(
            f"Couldn't fetch live data for: {', '.join(macro_errors)}. "
            "FRED's website may be temporarily unavailable - try again later."
        )

    if not macro_data:
        st.error("Couldn't load any macro data right now. Please check your internet connection and try again.")
    else:
        # ---------------------------------------------------
        # WALK THROUGH EACH CATEGORY IN ORDER, SHOWING:
        #   1) a row of "latest reading" metric boxes
        #   2) a line chart per indicator inside an expander
        #      (collapsed by default to keep the page compact)
        # ---------------------------------------------------
        # Get the category names in the order they first appear.
        categories = list(dict.fromkeys(ind["category"] for ind in MACRO_INDICATORS))

        for category in categories:
            # Which loaded indicators belong to this category?
            items = [
                (label, macro_data[label])
                for ind in MACRO_INDICATORS
                if ind["category"] == category and ind["label"] in macro_data
                for label in [ind["label"]]
            ]
            if not items:
                continue

            st.header(category)

            # --- Row of latest-reading metric boxes ---
            cols = st.columns(len(items))
            for col, (label, entry) in zip(cols, items):
                col.metric(
                    label,
                    fmt_macro(entry["latest"], entry["meta"]["fmt"]),
                    help=entry["meta"]["help"],
                )

            # --- Charts (collapsed by default) ---
            for label, entry in items:
                with st.expander(f"{label} — trend over time"):
                    series = entry["series"]
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=series.index, y=series.values,
                        mode="lines", name=label, line=dict(color=COLOR_PRIMARY)
                    ))
                    # The yield curve chart gets a zero line so it's
                    # easy to see when it goes negative (inverted).
                    if entry["meta"]["code"] == "T10Y2Y":
                        fig.add_hline(y=0, line_dash="dash", line_color=COLOR_GRAY)
                    unit = "%" if entry["meta"]["fmt"] == "pct" else ""
                    style_chart(fig, height=300, yaxis_title=unit)
                    st.plotly_chart(fig, use_container_width=True)

            st.divider()


# ===========================================================
# PAGE: GLOSSARY
# Plain-English definitions of every metric used in the app,
# grouped by topic, with a search box. Built for beginners.
# ===========================================================
elif page == "Glossary":
    st.caption("Plain-English definitions of every term used in Lumen.")

    # term -> (category, definition)
    GLOSSARY = {
        "Market Cap": ("Valuation", "The total value of all a company's shares (share price × number of shares). A quick measure of company size."),
        "P/E Ratio (Price-to-Earnings)": ("Valuation", "Share price divided by earnings per share. Roughly, how many dollars you pay for each $1 of yearly profit. Lower can mean cheaper."),
        "Forward P/E": ("Valuation", "Like P/E, but using analysts' expected future earnings instead of past ones."),
        "PEG Ratio": ("Valuation", "P/E divided by the earnings growth rate. Around 1 is often considered fair — it adjusts the P/E for how fast the company is growing."),
        "Price/Book": ("Valuation", "Share price vs. the company's accounting net worth (assets minus liabilities) per share."),
        "Price/Sales": ("Valuation", "Share price vs. revenue per share. Useful for companies that aren't profitable yet."),
        "Fair Value (DCF)": ("Valuation", "An estimate of what a stock is 'worth' by projecting its future cash and discounting it back to today. Very sensitive to assumptions."),
        "Profit Margin": ("Profitability", "The percent of revenue left as profit after all expenses. Higher = more efficient."),
        "Return on Equity (ROE)": ("Profitability", "Profit generated for each dollar of shareholder money. Higher is generally better."),
        "Operating Margin": ("Profitability", "Profit from core operations as a percent of revenue, before interest and taxes."),
        "Gross Margin": ("Profitability", "Revenue left after the direct cost of making the product, as a percent of revenue."),
        "Revenue Growth": ("Growth", "How much sales grew compared to a year ago."),
        "Earnings Growth": ("Growth", "How much profit grew compared to a year ago."),
        "EPS (Earnings Per Share)": ("Growth", "A company's profit divided by its number of shares."),
        "Debt/Equity": ("Financial Health", "How much debt a company has relative to shareholder equity. Lower is generally safer."),
        "Current Ratio": ("Financial Health", "Short-term assets divided by short-term bills. Above 1 means it can cover near-term obligations."),
        "Free Cash Flow": ("Financial Health", "Cash left over after running and maintaining the business — money that can fund dividends, buybacks, or growth."),
        "Beta": ("Risk", "How much a stock moves relative to the overall market. 1 = moves with the market; above 1 = more volatile; below 1 = steadier."),
        "Volatility": ("Risk", "How much a price bounces around. Higher volatility = a bumpier, riskier ride."),
        "Sharpe Ratio": ("Risk", "Return earned per unit of risk taken. Higher is better; above 1 is generally considered decent."),
        "Max Drawdown": ("Risk", "The worst peak-to-trough drop over a period — the most you'd have been down from a high point."),
        "Dividend Yield": ("Income", "Annual dividends paid as a percent of the share price. A 3% yield pays $3/year per $100 invested."),
        "Expense Ratio": ("Funds", "The annual fee a fund charges, as a percent of your money. Under ~0.20% is cheap; over ~1% is expensive."),
        "NAV (Net Asset Value)": ("Funds", "The per-share value of a mutual fund, calculated once per day after markets close."),
        "Moving Average (50/200-day)": ("Technical", "The average closing price over the last 50 (or 200) days. Smooths out daily noise to show the trend."),
        "RSI (Relative Strength Index)": ("Technical", "A 0–100 gauge of recent gains vs. losses. Below 30 is often called 'oversold,' above 70 'overbought.'"),
        "CAGR": ("Returns", "Compound Annual Growth Rate — the steady yearly rate that would produce a given total return over several years."),
        "Yield Curve": ("Bonds", "A plot of Treasury interest rates across maturities. Normally slopes up; when it inverts (slopes down), it has often preceded recessions."),
        "10yr–2yr Spread": ("Bonds", "The 10-year Treasury yield minus the 2-year. Negative ('inverted') is a classic recession warning sign."),
        "VIX": ("Macro", "The market's 'fear gauge' — expected stock-market volatility. Spikes when investors are nervous."),
        "CPI / Inflation": ("Macro", "The Consumer Price Index measures the cost of a basket of goods. Its yearly change is the inflation rate."),
        "Correlation": ("Portfolio", "How closely two investments move together, from -1 (opposite) to +1 (lockstep). Lower correlation between holdings = better diversification."),
        "Diversification": ("Portfolio", "Spreading money across investments that don't all move together, to reduce risk without necessarily reducing return."),
    }

    query = st.text_input("Search terms:", value="", placeholder="e.g. P/E, beta, drawdown").strip().lower()

    # Filter by the search box (matches term or definition).
    filtered = {
        term: (cat, defn) for term, (cat, defn) in GLOSSARY.items()
        if query in term.lower() or query in defn.lower()
    }

    if not filtered:
        st.info("No terms match your search.")
    else:
        # Group alphabetically by category.
        categories = sorted({cat for cat, _ in filtered.values()})
        for category in categories:
            st.subheader(category)
            for term, (cat, defn) in sorted(filtered.items()):
                if cat == category:
                    st.markdown(f"**{term}** — {defn}")
            st.divider()

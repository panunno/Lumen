"""
Fills the landing page's ticker cards with REAL Lumen output.

WHY THIS EXISTS
---------------
The landing page (landing/index.html) is a plain static file hosted on Netlify.
It has no server, so it cannot use your API keys -- anything written into that
page is readable by anyone who views the source. And the interesting numbers on
the card (grade, fair value, signal) are not raw market data at all: they come
out of Lumen's own Python functions.

So instead of fetching data in the browser, this script runs Lumen's real
grading code here on your computer, and writes the results into the page along
with the date they were computed. The page then shows genuine Lumen output,
and can never disagree with the app -- because it IS the app's code.

HOW TO USE
----------
    py make_landing_data.py

Then drag the `landing` folder onto Netlify's Deploys tab. Re-run it whenever
you want the numbers refreshed; the page always says when they were computed.
"""

import json
import re
import sys
import types
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

HERE = Path(__file__).parent
TARGET = HERE / "landing" / "index.html"
TICKERS = ["AAPL", "NVDA", "VOO", "PLTR"]


# -------------------------------------------------------------------
# app.py is a Streamlit script: importing it normally would try to draw
# a whole web page. We swap in a stand-in "streamlit" module that quietly
# absorbs every UI call, so we can import app.py purely for its FUNCTIONS.
# Only the pieces app.py actually reads at startup need real behaviour.
# -------------------------------------------------------------------
class _SessionState(dict):
    def pop(self, key, default=None):
        return dict.pop(self, key, default)


class _StreamlitStub(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        # Read at import time by app.py:
        self.session_state = _SessionState(theme="Dark")
        self.secrets = {}          # empty -> no API keys -> yfinance path (fine locally)

        def _cache(*args, **kwargs):
            # Supports both @st.cache_data and @st.cache_data(ttl=...)
            if args and callable(args[0]):
                return args[0]
            return lambda fn: fn

        _cache.clear = lambda: None
        self.cache_data = _cache
        self.cache_resource = _cache

        self.columns = lambda spec, **k: [
            MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))
        ]
        self.button = lambda *a, **k: False
        self.checkbox = lambda *a, **k: False
        self.sidebar = MagicMock()

    def __getattr__(self, name):
        # Every other st.* call (markdown, header, plotly_chart, ...) is a no-op.
        return MagicMock()


_menu = types.ModuleType("streamlit_option_menu")
_menu.option_menu = lambda *a, **k: "Welcome"   # land on the page that fetches nothing

sys.modules["streamlit"] = _StreamlitStub()
sys.modules["streamlit_option_menu"] = _menu

sys.path.insert(0, str(HERE))
import app  # noqa: E402  (must come after the stubs above)


# -------------------------------------------------------------------
# Formatting helpers. Anything we can't compute honestly becomes "N/A"
# rather than a guess.
# -------------------------------------------------------------------
def _pct(value):
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else "−"
    return f"{sign}{abs(value) * 100:.1f}%"


def _num(value):
    return "N/A" if value is None else f"{value:.1f}"


def _money(value):
    return "N/A" if value is None else f"${value:,.0f}"


def build_card(ticker):
    info, history, err = app.get_stock_data(ticker)
    if err or info is None:
        print(f"  {ticker}: FAILED - {err or 'no data'}")
        return None

    cats, overall, _ = app.grade_stock(info, history)
    _, signal_label, _ = app.buy_sell_signal(info, overall, history)

    price = float(history["Close"].iloc[-1]) if history is not None and not history.empty else None
    yr_return = (price / float(history["Close"].iloc[0]) - 1) if price else None

    # Same DCF defaults the Grade & Value page starts with.
    growth = info.get("revenueGrowth")
    growth = growth if (growth and 0 < growth < 0.5) else 0.08
    fair_value = app.estimate_fair_value(info, growth, 0.09, 5, 0.02)

    target = info.get("targetMeanPrice")
    upside = (target / price - 1) if (target and price) else None

    exchange = info.get("fullExchangeName") or info.get("exchange") or ""
    momentum = cats.get("Momentum")

    card = {
        "nm": info.get("longName") or info.get("shortName") or ticker,
        "sub": f"{exchange} · {ticker}".strip(" ·"),
        "grade": app.score_to_letter(overall),
        "sig": signal_label,
        "fv": _money(fair_value),
        "yr": _pct(yr_return),
        "pe": _num(info.get("trailingPE")),
        "up": _pct(upside),
        "mo": "N/A" if momentum is None else f"{momentum:.0f}/100",
        # The five category scores behind the letter, for the bars further
        # down the page. None stays None so the page can show "N/A" rather
        # than draw a zero-length bar that looks like a real score of 0.
        "cats": {name: (None if score is None else round(score)) for name, score in cats.items()},
    }
    # The cards use typographic characters (− and ·) that the Windows console
    # can't encode, so keep progress messages plain ASCII.
    _plain = f"  {ticker}: {card['grade']} / {card['sig']} / 1yr {card['yr']}"
    print(_plain.replace("−", "-").replace("·", "-"))
    return card


def main():
    print("Computing real Lumen grades (this hits the market data sources)...")
    cards, order = {}, []
    for ticker in TICKERS:
        card = build_card(ticker)
        if card:
            cards[ticker] = card
            order.append(ticker)

    if not cards:
        print("\nNo tickers succeeded - leaving the page untouched.")
        return 1

    payload = {
        "asof": date.today().strftime("%b %d, %Y"),
        "order": order,
        "cards": cards,
    }
    block = json.dumps(payload, indent=2, ensure_ascii=False)

    html = TARGET.read_text(encoding="utf-8")
    new_html, count = re.subn(
        r'(<script id="lumen-data" type="application/json">)(.*?)(</script>)',
        lambda m: m.group(1) + "\n" + block + "\n" + m.group(3),
        html,
        flags=re.S,
    )
    if count != 1:
        print(f"\nCouldn't find the data block in {TARGET} - nothing written.")
        return 1

    TARGET.write_text(new_html, encoding="utf-8")
    print(f"\nWrote {len(cards)} real cards to {TARGET}")
    print(f"Stamped 'as of {payload['asof']}'.")
    print("Next: drag the `landing` folder onto Netlify's Deploys tab.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

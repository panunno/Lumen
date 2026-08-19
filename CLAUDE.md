# CLAUDE.md — Lumen

Personal investing dashboard. Streamlit, single-file app, deployed publicly.
Audience is a **beginner investor**, so plain-English explanation is a feature, not decoration.

> Educational tool, **not financial advice**. Never write copy that reads as a
> recommendation to buy or sell. Signals and grades are rule-based outputs with a
> visible "why", and every page that shows one also shows the caveat.

## Layout

| Path | What it is |
|---|---|
| `app.py` | **The entire app** — ~5,150 lines, one file. |
| `requirements.txt` | Hard-pinned (`==`) deps. Streamlit Cloud installs exactly this. |
| `.streamlit/config.toml` | Dark/gold theme. Committed. |
| `.streamlit/secrets.toml` | `FMP_API_KEY`, `TWELVEDATA_API_KEY`. **Git-ignored — never commit or print.** |
| `landing/index.html` | Static marketing page, hosted separately on Netlify. |
| `make_landing_data.py` | Regenerates the stats baked into `landing/index.html`. |
| `portfolio.csv`, `watchlist.csv`, `alerts.csv`, `portfolio_history.csv` | Personal data. Git-ignored. |

## Live deployments

- **App** → `lumeninvest.streamlit.app` — Streamlit Community Cloud, auto-redeploys from GitHub `main` in ~1 min.
- **Landing** → `lumeninvest.netlify.app` — manual drag-and-drop of the `landing/` folder onto Netlify's Deploys tab.

## Running locally

```
py -m streamlit run app.py
```

Python 3.13 at `%LOCALAPPDATA%\Programs\Python\Python313\`. `run_dashboard.bat` does the same.
`.claude/launch.json` (`lumen`, port 8599) pins the absolute interpreter path deliberately —
a bare `py` breaks when a shell inherits a stale PATH.

## Architecture of `app.py`

Top-to-bottom script, no framework. Order matters — everything below is defined before use.

1. **Imports, theme, palette** (~L23–224) — `PALETTES` dict drives Dark/Light; `ACCENT`, `CARD_BG`, `CARD_BORDER` derive from it.
2. **Config & constants** (~L225–254) — `APP_VERSION`, CSV filenames, column schemas.
3. **`MULTIUSER`** (~L255–274) — see below.
4. **Secrets** (~L277–291) — via `get_secret()`, empty string when absent.
5. **Data layer** (~L294–1150) — providers, fetch chain, caching, formatters.
6. **Scoring** (~L1152–1760) — `grade_stock()`, `buy_sell_signal()`, DCF, Monte Carlo.
7. **Nav** (~L1766–1830) — `PAGES` list + `option_menu` sets `page`.
8. **Pages** (~L1970–end) — one `if page == "…": / elif` branch per entry, each fenced by a `# ====` banner.

Adding a page = append to `PAGES` **and** add the matching `elif` branch. The two must stay in sync.

### The data-source chain

`get_stock_data()` → `_fetch_stock_cached()` tries **Yahoo (yfinance) → FMP → Stooq**, in that order.

This cascade exists because **Yahoo IP-blocks shared cloud hosts**, so Streamlit Cloud almost never
gets past step 1 while local runs almost always do. Consequence worth remembering: *the same ticker
can grade differently local vs. deployed.* `_stock_data_from_fmp()` deliberately maps
`revenueGrowth`/`earningsGrowth` so the Growth category isn't silently dropped, which would average
4 categories on cloud vs. 5 locally.

- `_fetch_stock_cached` **raises** rather than returns on failure — that's intentional, so Streamlit
  won't cache a failure for an hour. Don't "fix" it into returning `None`.
- `_clean_history()` drops rows with no `Close`. Everything reads `history["Close"].iloc[-1]`, so one
  blank trailing row turns the whole app into `nan`.
- TwelveData is a *quote-only* fallback; FRED (keyless CSV) backs Bonds and Macro.

### Caching

`@st.cache_data(ttl=…)` — 600s for quotes, 3600s for full history/fundamentals, 86400s for FRED.
Match the TTL to how fast the data actually moves when adding a fetcher.

### MULTIUSER

`MULTIUSER` is true only when the `MULTIUSER = "true"` secret is set — i.e. **on the cloud only**.

- **Local (false):** reads/writes the CSV files, auto-saving.
- **Cloud (true):** never touches disk; data lives in `st.session_state`, and users persist it with
  the Download/Upload buttons.

Any new persistence **must** honor this flag — writing to disk unconditionally would leak one
visitor's portfolio to the next. Follow `load_portfolio_holdings()` as the reference pattern.

## Conventions

- **Comments explain *why*, in full sentences**, often as a `# ---` banner above a function. Match this —
  the existing density is high on purpose and several comments encode real production bugs.
- Colors come from the palette constants (`ACCENT`, `COLOR_GREEN`, …). No new hex literals inline.
- Charts go through `style_chart()` so they stay theme-consistent.
- Formatting goes through `fmt_price`, `fmt_ratio`, `fmt_decimal_pct`, `fmt_dollar_big`,
  `format_market_cap` — they already handle `None`/`nan`.
- Missing data is **skipped, never penalized**, in grading. Preserve that.
- Degrade quietly: a dead provider or absent API key should disable a feature, not crash a page.
  Broad `except Exception` returning a neutral value is the established idiom here.
- Any new term shown to the user belongs in the **Glossary** page.

## Before shipping

```
py -m py_compile app.py
```

A syntax error is the one failure mode that takes the live site down, and there are no tests —
so compile-check, then click through the affected page locally.

Bump `APP_VERSION` (L230) for user-visible changes; it renders in the sidebar.
If the landing page's numbers change, re-run `py make_landing_data.py` and redeploy `landing/` to Netlify.

## Gotchas

- **`option_menu` only applies its `styles` on first mount** — theme switches need the documented remount trick (~L1801).
- Editing `.streamlit/config.toml` requires a full restart; Streamlit won't hot-reload it.
- The folder lives in **OneDrive** with Files On-Demand, so files may be cloud placeholders that hydrate on access.
- `requirements.txt` is exact-pinned. Changing a version here changes what the live site installs — verify locally first.

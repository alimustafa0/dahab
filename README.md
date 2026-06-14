# Dahab — Egyptian Gold Price & Forecast

Dahab (دهب) tracks the price of 21-karat gold (عيار 21) in Egypt and forecasts it
with backtested, honest confidence intervals.

## Why it's built this way

Gold pricing in Egypt is driven by three coupled factors, not one: the global XAU
spot price (USD/oz), the USD→EGP exchange rate, and a local market premium. Dahab
models them **separately** and recombines them in log space, because treating the
EGP gold price as a single time series misses its dominant driver — the currency.
The fair-value identity is:

```
fair_EGP_per_gram(21K) = (spot_USD_per_oz / 31.1034768) × USD_to_EGP × 0.875
```

## Features

- Live 21K / 24K / 22K / 18K prices in EGP, cached from GoldAPI.io
- Hybrid forecast (spot × FX × purity) with 5–95% Monte Carlo intervals at
  1 / 7 / 30 / 90-day horizons
- Walk-forward backtest reporting MAE and MAPE per horizon
- Five years of historical data, seeded for free (no API quota used)
- Strict free-tier API economy: a guarded daily fetch with a cache-TTL check and a
  monthly-budget circuit breaker
- Dashboard with a price-history and forecast chart

## Tech stack

Python 3.13 · Django 6 · pandas / numpy · Chart.js · SQLite (development).
Data sources: GoldAPI.io (live) and Yahoo Finance via `yfinance` (historical seed).

## How it works

**Data layer (`prices`)** — `GoldQuote` caches GoldAPI snapshots (the API-credit
firewall); `FxRate` holds USD/EGP rates (official, parallel, or implied);
`DailyObservation` is the clean per-day series the model trains on; `ApiCallLog`
tracks calls for the budget guard; and `LocalMarketPrice` is an optional retail
ground-truth layer.

**Model layer (`predictions`)** — `ModelRun` is a versioned model with its backtest
metrics; `Prediction` stores each forecast point with its interval and the
spot/FX component breakdown.

The daily job fetches XAU/EGP and XAU/USD, derives the implied USD/EGP rate from the
two, and builds the day's observation. The forecaster estimates drift and volatility
from each series' log-returns, runs a Monte Carlo simulation, and writes predictions.

## Local setup

```bash
git clone https://github.com/<your-username>/dahab.git
cd dahab
py -3.13 -m venv .venv
.venv\Scripts\activate          # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

# Create a .env file in the project root containing:
#   GOLDAPI_KEY=your-goldapi-key

python manage.py migrate
python manage.py seed_history --years 5     # backfill history (no API calls)
python manage.py fetch_gold_quote --force   # one live fetch (uses 2 API calls)
python manage.py run_forecast               # fit, backtest, store predictions
python manage.py runserver
```

Then open http://127.0.0.1:8000/.

## Management commands

| Command | What it does |
| --- | --- |
| `fetch_gold_quote [--force]` | Daily cached fetch of XAU/EGP + XAU/USD, guarded against the free-tier limit |
| `seed_history [--years N]` | Backfills historical observations from Yahoo Finance (no API calls) |
| `run_forecast [--sims N] [--lookback N]` | Fits the hybrid model, backtests it, stores a new active run + predictions |

## Scheduling

Run `fetch_gold_quote` once a day and `run_forecast` after it. Locally this is a
Windows Task Scheduler job; in production it runs on the host's scheduler.

## Model accuracy (honest)

Walk-forward backtest MAPE is roughly 0.7% at 1 day, 3% at 7 days, 7% at 30 days, and
17% at 90 days. Short-horizon error is near the random-walk floor — gold spot is hard
to beat. Long-horizon error is dominated by EGP devaluations, which are central-bank
decisions no model can predict from price history. Dahab forecasts **fair value** and
reports calibrated intervals rather than a single false-precision number.

## Deployment

The app deploys to any Django-capable host. In production it reads secrets from
environment variables — `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`,
`DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, and `GOLDAPI_KEY` — serves static files via
WhiteNoise, and runs the daily `fetch_gold_quote` on the host's scheduler.

## Roadmap

- Ingest local retail prices to model the real market premium (predict the actual
  price people pay, not just fair value)
- Arabic / RTL interface
- All karats + the gold pound (جنيه ذهب, 8 g) + a making-charges (مصنعية) calculator
- GARCH-based volatility for better-calibrated intervals
- Telegram price alerts, a JSON API, and a live realized-vs-predicted accuracy tracker

## Disclaimer

Forecasts are model estimates of fair value and are **not financial advice**.

## License

MIT — add a `LICENSE` file to make it official.
# Dahab — دهب

Egyptian 21-karat gold price tracker and forecaster. Dahab pulls the daily gold price, decomposes it into the factors that actually drive the local market, and projects it forward with honest, backtested confidence bands. The interface is bilingual (English / Arabic, right-to-left).

> Dahab tracks **fair value** — global spot × USD/EGP × karat purity — adjusted by the local market premium when retail data is available. It is **not financial advice**.

## Features

- **All karats + the gold pound.** 24K, 22K, 21K (عيار 21), and 18K per-gram prices, plus the Egyptian gold pound (الجنيه الذهب, 8 g of 21K).
- **Making-charges calculator (المصنعية).** Enter karat, weight, and workshop fee per gram to estimate what you'd actually pay at a jeweler.
- **Forecasts with confidence bands.** 1, 7, 30, and 90-day projections for the 21K price, each with a 5–95% range from a Monte Carlo simulation.
- **Local premium modeling.** Record the real retail price and Dahab forecasts the actual market price (fair value × premium), not just import-parity fair value.
- **Live accuracy tracker.** Every prediction is compared against the realized price once its date arrives, with a running average error.
- **Bilingual EN / AR.** Full right-to-left Arabic interface with a one-click language toggle.

## How it works

The Egyptian local price decomposes into three coupled factors, and Dahab models each one separately:

```
fair_EGP_per_gram(21K) = (spot_USD_per_oz / 31.1034768) × USD_to_EGP × 0.875
local_price             = fair_value × (1 + premium)
```

- **Global spot** (gold USD/oz) — modeled as a random walk with drift.
- **USD/EGP exchange rate** — the riskiest factor; estimated over a recent window so a calm regime isn't mistaken for a trend. No model can anticipate a policy-driven devaluation.
- **Local premium** — the gap between the real retail price and fair value; applied when retail data exists, zero otherwise.

The forecaster fits drift and **exponentially-weighted volatility** (RiskMetrics-style, so the band tracks the current volatility regime) to each component, runs 10,000 joint Monte Carlo paths per horizon, recombines them into the 21K price, and reads off the median and the 5th/95th percentiles. A walk-forward backtest measures real out-of-sample error.

### The API-credit firewall

GoldAPI.io's free tier allows roughly 100 requests per month. Every user-facing page reads from the database; the live API is touched **only** by a scheduled job (2 calls/day: XAU/EGP and XAU/USD), guarded by a cache-TTL check and a monthly budget counter. Years of history are seeded **free** from Yahoo Finance, using zero API quota.

## Accuracy — the honest version

Walk-forward backtest MAPE over ~5 years (2021–2026):

| Horizon  | MAPE  |
| -------: | ----: |
| +1 day   | 0.7%  |
| +7 days  | 2.9%  |
| +30 days | 7.2%  |
| +90 days | 17.0% |

The +1-day figure is essentially the random-walk floor — you cannot meaningfully beat "tomorrow ≈ today" for gold. The longer-horizon numbers are inflated by Egypt's 2024 currency float, a devaluation no model could foresee; recent-regime accuracy is better. The historical seed uses the *official* USD/EGP rate, so fair value for the 2022–2024 crisis years understates what gold actually cost locally — that gap is exactly the premium that requires local retail data to capture.

## Tech stack

- Python 3.13, Django 6
- SQLite (development) — PostgreSQL in production
- NumPy + pandas (modeling), Chart.js (charts)
- GoldAPI.io (live quotes), yfinance (historical seed)

## Project structure

```
dahab/
├── config/                       # Django project (settings, urls)
├── prices/                       # Data + ingestion
│   ├── models.py                 # GoldQuote, FxRate, LocalMarketPrice, DailyObservation, ApiCallLog
│   ├── i18n.py                   # EN / AR UI strings
│   ├── services/                 # goldapi, ingest, seed
│   └── management/commands/      # fetch_gold_quote, seed_history, add_local_price
├── predictions/                  # Forecasting
│   ├── models.py                 # ModelRun, Prediction
│   ├── services/                 # data, forecast, montecarlo, backtest, run, accuracy
│   └── management/commands/      # run_forecast, backfill_accuracy
└── templates/                    # base.html, dashboard.html
```

## Setup (Windows)

```bat
:: 1. Clone and enter
git clone https://github.com/alimustafa0/dahab.git
cd dahab

:: 2. Create the virtual environment (Python 3.13)
py -3.13 -m venv .venv
.venv\Scripts\activate

:: 3. Install dependencies
pip install -r requirements.txt

:: 4. Configure secrets — copy the example, then add your GoldAPI key
copy .env.example .env
::    edit .env and set GOLDAPI_KEY=your_key

:: 5. Set up the database
python manage.py migrate
python manage.py createsuperuser

:: 6. Seed ~5 years of history (free, no API calls)
python manage.py seed_history --years 5

:: 7. Fetch today's live quote (uses 2 API calls)
python manage.py fetch_gold_quote --force

:: 8. Generate the forecast
python manage.py run_forecast

:: 9. Run it
python manage.py runserver
```

Open http://127.0.0.1:8000/.

## Management commands

| Command | What it does |
| --- | --- |
| `fetch_gold_quote [--force]` | Fetch XAU/EGP + XAU/USD, cache them, and build the day's observation. Free-tier guarded. |
| `seed_history [--years N]` | Backfill spot + FX history from Yahoo Finance (zero API quota). |
| `run_forecast [--sims N] [--lookback N]` | Fit, simulate, backtest, and store a new active forecast. |
| `add_local_price PRICE [--karat 21] [--date YYYY-MM-DD]` | Record a real retail price and compute the premium. |
| `backfill_accuracy` | Fill realized prices into predictions whose target date has passed. |

The daily job runs `fetch_gold_quote`, `run_forecast`, and `backfill_accuracy` — via Windows Task Scheduler locally, and GitHub Actions in production.

## Roadmap

- Deployment on a free stack: Vercel (web) + Supabase (PostgreSQL) + GitHub Actions (daily jobs).
- Optional automated local-price ingestion (currently manual entry via the command or the admin).

## Disclaimer

Dahab estimates the local 21K gold price from public market data. Forecasts are statistical projections with wide, honest uncertainty bands — they cannot anticipate currency devaluations or sudden shifts in the local premium, and they are **not financial advice**.
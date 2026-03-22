<p align="center">
  <a href="https://github.com/simon-verbois/be-energy-monitor/graphs/traffic"><img src="https://api.visitorbadge.io/api/visitors?path=https%3A%2F%2Fgithub.com%2Fsimon-verbois%2Fbe-energy-monitor&label=Visitors&countColor=26A65B&style=flat" alt="Visitor Count" height="28"/></a>
  <a href="https://github.com/simon-verbois/be-energy-monitor/commits/main"><img src="https://img.shields.io/github/last-commit/simon-verbois/be-energy-monitor?style=flat" alt="GitHub Last Commit" height="28"/></a>
  <a href="https://github.com/simon-verbois/be-energy-monitor/stargazers"><img src="https://img.shields.io/github/stars/simon-verbois/be-energy-monitor?style=flat&color=yellow" alt="GitHub Stars" height="28"/></a>
  <a href="https://github.com/simon-verbois/be-energy-monitor/issues"><img src="https://img.shields.io/github/issues/simon-verbois/be-energy-monitor?style=flat&color=red" alt="GitHub Issues" height="28"/></a>
  <a href="https://github.com/simon-verbois/be-energy-monitor/pulls"><img src="https://img.shields.io/github/issues-pr/simon-verbois/be-energy-monitor?style=flat&color=blue" alt="GitHub Pull Requests" height="28"/></a>
</p>

# Belgian Energy Monitor

Python microservice that monitors Belgian energy prices and sends alerts and reports by email.

## Data sources

| Energy type | Source | Schedule |
|-------------|--------|----------|
| Heating oil | SPF Economy (PDF) | Daily 08:30 |
| Fuels (95/98/B7) | SPF Economy (PDF) | Daily 08:30 |
| Electricity (peak/off-peak) | TotalEnergies (PDF) | Daily 08:35 |
| Natural gas | TotalEnergies (PDF) | Daily 08:35 |

## Features

- Email alerts when a price drops significantly below its threshold
- Daily digest report with price tables and trend charts
- Weekly summary every Sunday
- Price history persisted in SQLite

## Project structure

```
energy-monitor/
├── main.py              # Entry point — APScheduler jobs and Config
├── src/
│   ├── i18n.py          # Translation strings (fr / en / nl)
│   ├── scrapers.py      # HTTP fetching and PDF parsing
│   ├── database.py      # SQLAlchemy models and query helpers
│   ├── visualizer.py    # Matplotlib chart generation
│   └── notifier.py      # HTML email templates and SMTP sending
├── k8s-deployment/      # Kubernetes manifests
├── data/                # SQLite database (bind-mount in Docker)
├── Dockerfile
├── compose.yml
├── requirements.txt
└── .env.example
```

## Quick start

```bash
cp .env.example .env
# Edit .env with your SMTP settings and recipient address
docker compose up -d
```

Data is persisted in `./data/energy.db`.

## Kubernetes

```bash
kubectl apply -f k8s-deployment/
```

Secrets (`SMTP_USER`, `SMTP_PASSWORD`) should be provided via a Kubernetes Secret mounted as environment variables, not stored in the ConfigMap.

## Configuration

Copy `.env.example` to `.env` and fill in your values.

### SMTP

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_SERVER` | *required* | SMTP server hostname or IP |
| `SMTP_PORT` | `25` | SMTP port (25 for relay, 587 for STARTTLS) |
| `SMTP_AUTH` | `starttls` | Auth mode: `starttls` or `none` (unauthenticated relay) |
| `SMTP_USER` | — | Login username (STARTTLS only) |
| `SMTP_PASSWORD` | — | Login password or app password (STARTTLS only) |
| `SMTP_FROM` | `SMTP_USER` | From address — required in relay mode |

### Recipients

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_EMAIL_TO` | *required* | Recipient address for all emails |

### Alert thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `OIL_ALERT_ENABLED` | `true` | Enable heating oil price drop alerts |
| `OIL_ALERT_THRESHOLD_PERCENT` | `5` | Alert when current price is X% below the 7-day average |
| `FUEL_ALERT_ENABLED` | `false` | Enable fuel price drop alerts |
| `FUEL_ALERT_THRESHOLD_PERCENT` | `3` | Alert when monthly average drops X% vs previous month |
| `ELEC_ALERT_ENABLED` | `true` | Enable electricity price alerts |
| `ELEC_PRICE_CEILING` | `0.10` | Alert when day rate drops below this value (€/kWh) |
| `GAS_ALERT_ENABLED` | `false` | Enable natural gas price drop alerts |
| `GAS_ALERT_THRESHOLD_PERCENT` | `5` | Alert when quarterly price drops X% vs previous quarter |

### Reports and charts

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_DAILY_REPORT` | `true` | Send daily digest at 09:00 |
| `ENABLE_WEEKLY_REPORT` | `true` | Send weekly summary on Sundays at 18:00 |
| `CHART_MONTHS` | `3` | Months of history shown in trend charts |

### Language

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGUAGE` | `fr` | Email language: `fr` (French), `en` (English), `nl` (Dutch) |

### Advanced

| Variable | Default | Description |
|----------|---------|-------------|
| `TZ` | `Europe/Brussels` | Timezone — do not change for Belgian context |
| `TOTALENERGIES_ELEC_PDF_URL` | *(see .env.example)* | Override if TotalEnergies changes the document URL |
| `TOTALENERGIES_GAS_PDF_URL` | *(see .env.example)* | Override if TotalEnergies changes the document URL |
| `LOG_LEVEL` | `INFO` | Log verbosity: `INFO` or `DEBUG` |

## Development

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

"""
main.py — Belgian Energy Monitor core service.

Scheduler jobs:
  08:30 daily    → job_fetch_petroleum  (mazout + carburants, SPF Economie PDF)
  08:35 daily    → job_fetch_gas        (TotalEnergies monthly tariff)
  :05 hourly     → job_fetch_elec       (TotalEnergies monthly tariff)
  09:00 daily    → job_daily_digest     (if ENABLE_DAILY_REPORT=true)
  Sun 18:00      → job_weekly_summary   (if ENABLE_WEEKLY_REPORT=true)

Alert thresholds:
  Oil / Fuel : current price > ALERT_THRESHOLD_PERCENT% below 7-day average
  Electricity: current price < ELEC_PRICE_CEILING (€/kWh, default 0.10)
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from src.database import (
    ElecPrice,
    FuelPrice,
    GasPrice,
    OilPrice,
    get_all_gas_prices,
    get_elec_last_n_months,
    get_engine,
    get_fuel_last_n_months,
    get_latest_elec_price,
    get_latest_fuel_price,
    get_latest_gas_price,
    get_latest_oil_price,
    get_oil_7day_avg,
    get_oil_last_n_months,
    init_db,
    make_session_factory,
    upsert_elec_price,
    upsert_fuel_price,
    upsert_gas_price,
    upsert_oil_price,
)
from src.notifier import (
    send_daily_digest,
    send_elec_alert,
    send_oil_alert,
    send_startup_report,
    send_system_alert,
    send_weekly_summary,
)
from src.scrapers import ElecScraper, GasScraper, PetroleumScraper, ScraperError
from src.visualizer import (
    generate_elec_chart,
    generate_fuel_chart,
    generate_gas_chart,
    generate_oil_chart,
)

# ── Logging ───────────────────────────────────────────────────────────────────
#
# Level guide:
#   DEBUG   — internal details: parsed PDF values, regex matches, chart point counts
#   INFO    — business events: job start/end, new price stored, email sent, scheduler up
#   WARNING — recovered anomalies: DB schema migration, parsing fallback used
#   ERROR   — operation failures: scraper error, email failure (service keeps running)
#   CRITICAL— fatal config errors (missing env vars) → process exits

_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
# Suppress APScheduler's noisy job-registration messages unless in DEBUG mode
if _log_level != "DEBUG":
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

log = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class Config:
    SMTP_SERVER:             str   = field(default_factory=lambda: os.environ["SMTP_SERVER"])
    SMTP_PORT:               int   = field(default_factory=lambda: int(os.environ.get("SMTP_PORT", "25")))
    SMTP_AUTH:               str   = field(default_factory=lambda: os.environ.get("SMTP_AUTH", "starttls").lower())
    SMTP_USER:               str   = field(default_factory=lambda: os.environ.get("SMTP_USER", ""))
    SMTP_PASSWORD:           str   = field(default_factory=lambda: os.environ.get("SMTP_PASSWORD", ""))
    SMTP_FROM:               str   = field(default_factory=lambda: os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER", "energy-monitor@localhost"))
    ALERT_EMAIL_TO:          str   = field(default_factory=lambda: os.environ["ALERT_EMAIL_TO"])
    # Oil alert
    OIL_ALERT_ENABLED:         bool  = field(default_factory=lambda: os.environ.get("OIL_ALERT_ENABLED", "true").lower() == "true")
    OIL_ALERT_THRESHOLD_PERCENT: float = field(default_factory=lambda: float(
        os.environ.get("OIL_ALERT_THRESHOLD_PERCENT") or os.environ.get("ALERT_THRESHOLD_PERCENT", "5")
    ))
    # Fuel alert
    FUEL_ALERT_ENABLED:        bool  = field(default_factory=lambda: os.environ.get("FUEL_ALERT_ENABLED", "false").lower() == "true")
    FUEL_ALERT_THRESHOLD_PERCENT: float = field(default_factory=lambda: float(os.environ.get("FUEL_ALERT_THRESHOLD_PERCENT", "3")))
    # Electricity alert
    ELEC_ALERT_ENABLED:        bool  = field(default_factory=lambda: os.environ.get("ELEC_ALERT_ENABLED", "true").lower() == "true")
    ELEC_PRICE_CEILING:        float = field(default_factory=lambda: float(os.environ.get("ELEC_PRICE_CEILING", "0.10")))
    # Gas alert
    GAS_ALERT_ENABLED:         bool  = field(default_factory=lambda: os.environ.get("GAS_ALERT_ENABLED", "false").lower() == "true")
    GAS_ALERT_THRESHOLD_PERCENT: float = field(default_factory=lambda: float(os.environ.get("GAS_ALERT_THRESHOLD_PERCENT", "5")))
    # Backward-compat alias
    ALERT_THRESHOLD_PERCENT:   float = field(default_factory=lambda: float(
        os.environ.get("OIL_ALERT_THRESHOLD_PERCENT") or os.environ.get("ALERT_THRESHOLD_PERCENT", "5")
    ))
    ENABLE_DAILY_REPORT:     bool  = field(default_factory=lambda: os.environ.get("ENABLE_DAILY_REPORT", "true").lower() == "true")
    ENABLE_WEEKLY_REPORT:    bool  = field(default_factory=lambda: os.environ.get("ENABLE_WEEKLY_REPORT", "true").lower() == "true")
    DB_PATH:                 str   = field(default_factory=lambda: os.environ.get("DB_PATH", "data/energy.db"))
    CHART_MONTHS:            int   = field(default_factory=lambda: int(os.environ.get("CHART_MONTHS", "3")))


# ── Application state ─────────────────────────────────────────────────────────

cfg: Config
SessionLocal = None
petroleum_scraper: PetroleumScraper
elec_scraper:      ElecScraper
gas_scraper:       GasScraper


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _build_elec_chart(session, months: int, ceiling: float) -> bytes:
    records = get_elec_last_n_months(session, months)
    return generate_elec_chart(records, ceiling=ceiling, months=months)


# ── Alert helpers ─────────────────────────────────────────────────────────────

def _check_oil_alert(current_price: float, session) -> bool:
    if not cfg.OIL_ALERT_ENABLED:
        return False
    avg = get_oil_7day_avg(session)
    if avg is None or avg == 0:
        return False
    triggered = current_price < avg * (1 - cfg.OIL_ALERT_THRESHOLD_PERCENT / 100)
    if triggered:
        log.info("Oil alert: %.4f < threshold (avg=%.4f, %%=%.1f)",
                 current_price, avg, cfg.OIL_ALERT_THRESHOLD_PERCENT)
    return triggered


def _check_elec_alert(price_day: float) -> bool:
    if not cfg.ELEC_ALERT_ENABLED:
        return False
    triggered = price_day < cfg.ELEC_PRICE_CEILING
    if triggered:
        log.info("Elec alert: jour %.5f €/kWh < ceiling %.5f €/kWh",
                 price_day, cfg.ELEC_PRICE_CEILING)
    return triggered


# ── Scheduled jobs ────────────────────────────────────────────────────────────

def job_fetch_petroleum() -> None:
    log.info(">>> job_fetch_petroleum")
    try:
        oil_result, fuel_result = petroleum_scraper.fetch()
    except ScraperError as exc:
        log.error("PetroleumScraper failed: %s", exc)
        send_system_alert(cfg, "SPF Économie (Pétrole)", str(exc))
        return
    except Exception as exc:
        log.exception("Unexpected error in job_fetch_petroleum")
        send_system_alert(cfg, "SPF Économie (Pétrole)", f"Erreur inattendue: {exc}")
        return

    with SessionLocal() as session:
        upsert_oil_price(session, OilPrice(
            valid_from=oil_result.valid_from.date(),
            tariff_no=oil_result.tariff_no,
            price_below_2000=oil_result.price_below_2000,
            price_above_2000=oil_result.price_above_2000,
            fetched_at=datetime.now(UTC),
        ))
        upsert_fuel_price(session, FuelPrice(
            period=fuel_result.period,
            essence_95_e5=fuel_result.essence_95_e5,
            essence_98_e5=fuel_result.essence_98_e5,
            diesel_b7=fuel_result.diesel_b7,
            fetched_at=datetime.now(UTC),
        ))

        if _check_oil_alert(oil_result.price_below_2000, session):
            avg = get_oil_7day_avg(session)
            try:
                send_oil_alert(cfg, oil_result, avg,
                               generate_oil_chart(get_oil_last_n_months(session, cfg.CHART_MONTHS), months=cfg.CHART_MONTHS))
            except Exception as exc:
                log.error("Failed to send oil alert: %s", exc)

    log.info("<<< job_fetch_petroleum complete")


def job_fetch_gas() -> None:
    log.info(">>> job_fetch_gas")
    try:
        gas_result = gas_scraper.fetch()
    except ScraperError as exc:
        log.error("GasScraper failed: %s", exc)
        send_system_alert(cfg, "TotalEnergies (Gaz naturel)", str(exc))
        return
    except Exception as exc:
        log.exception("Unexpected error in job_fetch_gas")
        send_system_alert(cfg, "TotalEnergies (Gaz naturel)", f"Erreur inattendue: {exc}")
        return

    with SessionLocal() as session:
        upsert_gas_price(session, GasPrice(
            period=gas_result.period,
            total_kwh_ttc=gas_result.total_kwh_ttc,
            source_url=gas_result.source_url,
            fetched_at=datetime.now(UTC),
        ))

    log.info("<<< job_fetch_gas complete: %s = %.5f €/kWh", gas_result.period, gas_result.total_kwh_ttc)


def job_fetch_elec() -> None:
    log.info(">>> job_fetch_elec")
    try:
        result = elec_scraper.fetch()
    except ScraperError as exc:
        log.error("ElecScraper failed: %s", exc)
        send_system_alert(cfg, "TotalEnergies (Électricité)", str(exc))
        return
    except Exception as exc:
        log.exception("Unexpected error in job_fetch_elec")
        send_system_alert(cfg, "TotalEnergies (Électricité)", f"Erreur inattendue: {exc}")
        return

    with SessionLocal() as session:
        inserted = upsert_elec_price(session, ElecPrice(
            valid_from=result.valid_from,
            price_day=result.price_day,
            price_night=result.price_night,
            source_url=result.source_url,
            fetched_at=datetime.now(UTC),
        ))

        if inserted and _check_elec_alert(result.price_day):
            latest = get_latest_elec_price(session)
            try:
                send_elec_alert(cfg, latest, cfg.ELEC_PRICE_CEILING,
                                _build_elec_chart(session, cfg.CHART_MONTHS, cfg.ELEC_PRICE_CEILING))
            except Exception as exc:
                log.error("Failed to send elec alert: %s", exc)

    log.info("<<< job_fetch_elec complete")


def job_daily_digest() -> None:
    if not cfg.ENABLE_DAILY_REPORT:
        return
    log.info(">>> job_daily_digest")
    months = cfg.CHART_MONTHS
    with SessionLocal() as session:
        latest_oil  = get_latest_oil_price(session)
        latest_fuel = get_latest_fuel_price(session)
        latest_elec = get_latest_elec_price(session)
        latest_gas  = get_latest_gas_price(session)
        oil_records  = get_oil_last_n_months(session, months)
        fuel_records = get_fuel_last_n_months(session, months)
        gas_records  = get_all_gas_prices(session)
        oil_png  = generate_oil_chart(oil_records, months=months)
        fuel_png = generate_fuel_chart(fuel_records, months=months)
        elec_png = _build_elec_chart(session, months, cfg.ELEC_PRICE_CEILING)
        gas_png  = generate_gas_chart(gas_records)

    try:
        send_daily_digest(cfg, latest_oil, latest_fuel, latest_elec, latest_gas,
                          oil_records, fuel_records,
                          oil_png, fuel_png, elec_png, gas_png)
    except Exception as exc:
        log.error("Failed to send daily digest: %s", exc)
    log.info("<<< job_daily_digest complete")


def job_weekly_summary() -> None:
    if not cfg.ENABLE_WEEKLY_REPORT:
        return
    log.info(">>> job_weekly_summary")
    months = cfg.CHART_MONTHS
    with SessionLocal() as session:
        latest_elec  = get_latest_elec_price(session)
        latest_gas   = get_latest_gas_price(session)
        oil_records  = get_oil_last_n_months(session, months)
        fuel_records = get_fuel_last_n_months(session, months)
        gas_records  = get_all_gas_prices(session)
        oil_png  = generate_oil_chart(oil_records, months=months)
        fuel_png = generate_fuel_chart(fuel_records, months=months)
        elec_png = _build_elec_chart(session, months, cfg.ELEC_PRICE_CEILING)
        gas_png  = generate_gas_chart(gas_records)

    try:
        send_weekly_summary(cfg, oil_records, fuel_records, latest_elec, latest_gas,
                            oil_png, fuel_png, elec_png, gas_png)
    except Exception as exc:
        log.error("Failed to send weekly summary: %s", exc)
    log.info("<<< job_weekly_summary complete")


# ── Startup helpers ───────────────────────────────────────────────────────────

def _startup_fetch_petroleum():
    """Fetch oil + fuel at startup. Returns (oil_result|None, oil_err, fuel_result|None, fuel_err)."""
    log.info("Startup: fetching petroleum prices…")
    try:
        oil_result, fuel_result = petroleum_scraper.fetch()
    except ScraperError as exc:
        log.error("Startup petroleum fetch failed: %s", exc)
        return None, str(exc), None, str(exc)
    except Exception as exc:
        log.exception("Unexpected error in startup petroleum fetch")
        msg = f"Erreur inattendue: {exc}"
        return None, msg, None, msg

    with SessionLocal() as session:
        upsert_oil_price(session, OilPrice(
            valid_from=oil_result.valid_from.date(),
            tariff_no=oil_result.tariff_no,
            price_below_2000=oil_result.price_below_2000,
            price_above_2000=oil_result.price_above_2000,
            fetched_at=datetime.now(UTC),
        ))
        upsert_fuel_price(session, FuelPrice(
            period=fuel_result.period,
            essence_95_e5=fuel_result.essence_95_e5,
            essence_98_e5=fuel_result.essence_98_e5,
            diesel_b7=fuel_result.diesel_b7,
            fetched_at=datetime.now(UTC),
        ))

    return oil_result, None, fuel_result, None


def _startup_fetch_elec():
    """Fetch current TotalEnergies electricity tariff. Returns (result|None, error|None)."""
    log.info("Startup: fetching TotalEnergies electricity tariff…")
    try:
        result = elec_scraper.fetch()
    except ScraperError as exc:
        log.error("Startup elec fetch failed: %s", exc)
        return None, str(exc)
    except Exception as exc:
        log.exception("Unexpected error in startup elec fetch")
        return None, f"Erreur inattendue: {exc}"

    with SessionLocal() as session:
        upsert_elec_price(session, ElecPrice(
            valid_from=result.valid_from,
            price_day=result.price_day,
            price_night=result.price_night,
            source_url=result.source_url,
            fetched_at=datetime.now(UTC),
        ))
    return result, None


def _startup_fetch_gas():
    """Fetch current TotalEnergies monthly gas tariff. Returns (result|None, error|None)."""
    log.info("Startup: fetching TotalEnergies natural gas tariff…")
    try:
        gas_result = gas_scraper.fetch()
    except ScraperError as exc:
        log.error("Startup gas fetch failed: %s", exc)
        return None, str(exc)
    except Exception as exc:
        log.exception("Unexpected error in startup gas fetch")
        return None, f"Erreur inattendue: {exc}"

    with SessionLocal() as session:
        upsert_gas_price(session, GasPrice(
            period=gas_result.period,
            total_kwh_ttc=gas_result.total_kwh_ttc,
            source_url=gas_result.source_url,
            fetched_at=datetime.now(UTC),
        ))
    return gas_result, None


# ── Scheduler ─────────────────────────────────────────────────────────────────

def _build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Europe/Brussels")

    scheduler.add_job(job_fetch_petroleum,
                      CronTrigger(hour=8, minute=30, timezone="Europe/Brussels"),
                      id="fetch_petroleum", max_instances=1, misfire_grace_time=300)

    scheduler.add_job(job_fetch_gas,
                      CronTrigger(hour=8, minute=35, timezone="Europe/Brussels"),
                      id="fetch_gas", max_instances=1, misfire_grace_time=300)

    scheduler.add_job(job_fetch_elec,
                      CronTrigger(minute=5, timezone="Europe/Brussels"),
                      id="fetch_elec", max_instances=1, misfire_grace_time=120)

    scheduler.add_job(job_daily_digest,
                      CronTrigger(hour=9, minute=0, timezone="Europe/Brussels"),
                      id="daily_digest", max_instances=1, misfire_grace_time=300)

    scheduler.add_job(job_weekly_summary,
                      CronTrigger(day_of_week="sun", hour=18, minute=0, timezone="Europe/Brussels"),
                      id="weekly_summary", max_instances=1, misfire_grace_time=600)

    return scheduler


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    global cfg, SessionLocal, petroleum_scraper, elec_scraper, gas_scraper

    load_dotenv()
    log.info("Belgian Energy Monitor starting up…")

    # Validate required env vars
    always_required = ["SMTP_SERVER", "ALERT_EMAIL_TO"]
    missing = [v for v in always_required if not os.environ.get(v)]
    if os.environ.get("SMTP_AUTH", "starttls").lower() == "starttls":
        missing += [v for v in ("SMTP_USER", "SMTP_PASSWORD") if not os.environ.get(v)]
    if missing:
        log.critical("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    cfg = Config()
    log.info(
        "Config: DB=%s | chart_months=%d | daily=%s weekly=%s",
        cfg.DB_PATH, cfg.CHART_MONTHS, cfg.ENABLE_DAILY_REPORT, cfg.ENABLE_WEEKLY_REPORT,
    )
    log.info(
        "Alerts: oil=%s(%.1f%%) | fuel=%s(%.1f%%) | elec=%s(%.5f €/kWh) | gas=%s(%.1f%%)",
        "ON" if cfg.OIL_ALERT_ENABLED  else "OFF", cfg.OIL_ALERT_THRESHOLD_PERCENT,
        "ON" if cfg.FUEL_ALERT_ENABLED else "OFF", cfg.FUEL_ALERT_THRESHOLD_PERCENT,
        "ON" if cfg.ELEC_ALERT_ENABLED else "OFF", cfg.ELEC_PRICE_CEILING,
        "ON" if cfg.GAS_ALERT_ENABLED  else "OFF", cfg.GAS_ALERT_THRESHOLD_PERCENT,
    )

    engine = get_engine(cfg.DB_PATH)
    init_db(engine)
    SessionLocal = make_session_factory(engine)

    petroleum_scraper = PetroleumScraper()
    elec_scraper      = ElecScraper()
    gas_scraper       = GasScraper()

    # Startup: fetch all sources, then send ONE consolidated email
    log.info("Startup: initial data fetch…")
    oil_result, oil_err, fuel_result, fuel_err = _startup_fetch_petroleum()
    elec_result, elec_err                      = _startup_fetch_elec()
    gas_result,  gas_err                       = _startup_fetch_gas()

    # Generate charts from DB (may have only 1 point — that's fine)
    months = cfg.CHART_MONTHS
    try:
        with SessionLocal() as session:
            oil_png  = generate_oil_chart(get_oil_last_n_months(session, months), months=months)
            fuel_png = generate_fuel_chart(get_fuel_last_n_months(session, months), months=months)
            elec_png = _build_elec_chart(session, months, cfg.ELEC_PRICE_CEILING)
            gas_png  = generate_gas_chart(get_all_gas_prices(session))
    except Exception as exc:
        log.warning("Could not generate startup charts: %s", exc)
        oil_png = fuel_png = elec_png = gas_png = None

    send_startup_report(cfg,
                        oil_result,  oil_err,
                        fuel_result, fuel_err,
                        elec_result, elec_err,
                        gas_result,  gas_err,
                        oil_png=oil_png, fuel_png=fuel_png,
                        elec_png=elec_png, gas_png=gas_png)

    scheduler = _build_scheduler()
    log.info("Scheduler starting. Jobs:")
    for job in scheduler.get_jobs():
        log.info("  • %-20s → %s", job.id, job.trigger)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()

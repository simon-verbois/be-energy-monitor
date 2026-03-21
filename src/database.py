"""
database.py — SQLAlchemy 2.x models and DB helper functions.

All datetimes are stored as UTC timezone-aware values.
DST-safe conversion to Europe/Brussels happens at the display/chart layer.

Tables:
  oil_prices   — Heating oil (mazout) tariffs from SPF Economie PDF (monthly/on change)
  fuel_prices  — Fuel (Essence 95/98, Diesel B7) from SPF Economie PDF (monthly)
  elec_prices  — Electricity market price from Elia ods046 (hourly, €/kWh)
  gas_prices   — Natural gas social tariff from CREG PDF (quarterly, €/kWh TTC)
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    String,
    UniqueConstraint,
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

log = logging.getLogger(__name__)


# ── ORM Base ──────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────

class OilPrice(Base):
    """One row per official mazout tariff period (identified by valid_from date)."""

    __tablename__ = "oil_prices"
    __table_args__ = (UniqueConstraint("valid_from", name="uq_oil_valid_from"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    tariff_no: Mapped[str] = mapped_column(String(30), default="")
    price_below_2000: Mapped[float] = mapped_column(Float)   # TTC €/L, < 2 000 L
    price_above_2000: Mapped[float] = mapped_column(Float)   # TTC €/L, ≥ 2 000 L

    def __repr__(self) -> str:
        return (
            f"OilPrice(valid_from={self.valid_from}, "
            f"below={self.price_below_2000:.4f}, above={self.price_above_2000:.4f})"
        )


class FuelPrice(Base):
    """
    Monthly average maximum fuel prices from SPF Economie PDF.

    Period format: "YYYY-MM" (e.g. "2026-02").
    All prices are TTC (VAT included), in €/L.
    """

    __tablename__ = "fuel_prices"
    __table_args__ = (UniqueConstraint("period", name="uq_fuel_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    period: Mapped[str] = mapped_column(String(10), index=True)   # "2026-02"
    essence_95_e5: Mapped[float] = mapped_column(Float)           # TTC €/L
    essence_98_e5: Mapped[float] = mapped_column(Float)           # TTC €/L
    diesel_b7: Mapped[float] = mapped_column(Float)               # TTC €/L

    def __repr__(self) -> str:
        return (
            f"FuelPrice(period={self.period}, "
            f"95={self.essence_95_e5:.4f}, 98={self.essence_98_e5:.4f}, "
            f"B7={self.diesel_b7:.4f})"
        )


class ElecPrice(Base):
    """
    Electricity retail tariff from TotalEnergies PDF.

    One row per tariff period (deduplicated by valid_from date).
    Prices in €/kWh (source PDF is in c€/kWh).
      price_day   — Heures Pleines / Jour
      price_night — Heures Creuses / Nuit
    """

    __tablename__ = "elec_prices"
    __table_args__ = (UniqueConstraint("valid_from", name="uq_elec_valid_from"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    price_day: Mapped[float] = mapped_column(Float)    # €/kWh (Heures Pleines)
    price_night: Mapped[float] = mapped_column(Float)  # €/kWh (Heures Creuses)
    source_url: Mapped[str] = mapped_column(String(300), default="")

    def __repr__(self) -> str:
        return (
            f"ElecPrice(valid_from={self.valid_from}, "
            f"jour={self.price_day:.4f}, nuit={self.price_night:.4f} €/kWh)"
        )


class GasPrice(Base):
    """
    Quarterly natural gas social tariff from CREG.

    Period format: "YYYY-QN" (e.g. "2026-Q1").
    total_kwh_ttc: full all-inclusive price in €/kWh TTC.
    """

    __tablename__ = "gas_prices"
    __table_args__ = (UniqueConstraint("period", name="uq_gas_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    period: Mapped[str] = mapped_column(String(10), index=True)   # "2026-Q1"
    total_kwh_ttc: Mapped[float] = mapped_column(Float)           # €/kWh TTC (all components)
    source_url: Mapped[str] = mapped_column(String(200), default="")

    def __repr__(self) -> str:
        return f"GasPrice(period={self.period}, price={self.total_kwh_ttc:.5f} €/kWh)"


# ── Engine / Session factory ──────────────────────────────────────────────────

def get_engine(db_path: str = "data/energy.db"):
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine) -> None:
    # Auto-migrate: drop elec_prices if it has the old Elia hourly schema
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(elec_prices)"))
            columns = {row[1] for row in result}
            if "dayahead_price" in columns:
                log.warning("Migrating elec_prices: old Elia schema detected — dropping table.")
                conn.execute(text("DROP TABLE elec_prices"))
                conn.commit()
    except Exception as exc:
        log.debug("Migration check skipped (elec): %s", exc)

    # Auto-migrate: drop gas_prices if it contains old CREG quarterly data (period "YYYY-QN")
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT period FROM gas_prices LIMIT 1")).fetchone()
            if row and row[0] and "Q" in str(row[0]):
                log.warning("Migrating gas_prices: old CREG quarterly data detected — dropping table.")
                conn.execute(text("DROP TABLE gas_prices"))
                conn.commit()
    except Exception as exc:
        log.debug("Migration check skipped (gas): %s", exc)

    Base.metadata.create_all(engine)
    log.info("Database initialised at %s", engine.url)


def make_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


# ── Upsert helpers ────────────────────────────────────────────────────────────

def upsert_oil_price(session: Session, record: OilPrice) -> bool:
    existing = session.query(OilPrice).filter(OilPrice.valid_from == record.valid_from).first()
    if existing:
        return False
    session.add(record)
    session.commit()
    log.info("Stored oil price: %s", record)
    return True


def upsert_fuel_price(session: Session, record: FuelPrice) -> bool:
    existing = session.query(FuelPrice).filter(FuelPrice.period == record.period).first()
    if existing:
        return False
    session.add(record)
    session.commit()
    log.info("Stored fuel price: %s", record)
    return True


def upsert_elec_price(session: Session, record: ElecPrice) -> bool:
    existing = session.query(ElecPrice).filter(ElecPrice.valid_from == record.valid_from).first()
    if existing:
        return False
    session.add(record)
    session.commit()
    log.info("Stored elec tariff: %s", record)
    return True


def upsert_gas_price(session: Session, record: GasPrice) -> bool:
    existing = session.query(GasPrice).filter(GasPrice.period == record.period).first()
    if existing:
        return False
    session.add(record)
    session.commit()
    log.info("Stored gas price: %s", record)
    return True


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_oil_7day_avg(session: Session) -> float | None:
    cutoff = (datetime.now(UTC) - timedelta(days=7)).date()
    rows = session.query(OilPrice).filter(OilPrice.valid_from >= cutoff).all()
    if not rows:
        return None
    return sum(r.price_below_2000 for r in rows) / len(rows)


def get_oil_last_30days(session: Session) -> list[OilPrice]:
    """Kept for backward compatibility — calls get_oil_last_n_months(1)."""
    return get_oil_last_n_months(session, months=1)


def get_oil_last_n_months(session: Session, months: int) -> list[OilPrice]:
    """Return oil price records for the last `months` months, ordered by date."""
    cutoff = (datetime.now(UTC) - timedelta(days=months * 31)).date()
    return (
        session.query(OilPrice)
        .filter(OilPrice.valid_from >= cutoff)
        .order_by(OilPrice.valid_from)
        .all()
    )


def get_fuel_last_30days(session: Session) -> list[FuelPrice]:
    """Kept for backward compatibility — calls get_fuel_last_n_months(6)."""
    return get_fuel_last_n_months(session, months=6)


def get_fuel_last_n_months(session: Session, months: int) -> list[FuelPrice]:
    """Return fuel price records (monthly) for the last `months` months."""
    cutoff = (datetime.now(UTC) - timedelta(days=months * 31)).date()
    cutoff_period = cutoff.strftime("%Y-%m")
    return (
        session.query(FuelPrice)
        .filter(FuelPrice.period >= cutoff_period)
        .order_by(FuelPrice.period)
        .all()
    )


def get_elec_last_n_months(session: Session, months: int) -> list[ElecPrice]:
    """Return TotalEnergies tariff records for the last `months` months, ordered by date."""
    cutoff = (datetime.now(UTC) - timedelta(days=months * 31)).date()
    return (
        session.query(ElecPrice)
        .filter(ElecPrice.valid_from >= cutoff)
        .order_by(ElecPrice.valid_from)
        .all()
    )


def get_all_gas_prices(session: Session) -> list[GasPrice]:
    """Return all stored quarterly gas prices ordered chronologically."""
    return session.query(GasPrice).order_by(GasPrice.period).all()


def get_latest_elec_price(session: Session) -> ElecPrice | None:
    return session.query(ElecPrice).order_by(ElecPrice.valid_from.desc()).first()


def get_latest_oil_price(session: Session) -> OilPrice | None:
    return session.query(OilPrice).order_by(OilPrice.valid_from.desc()).first()


def get_latest_fuel_price(session: Session) -> FuelPrice | None:
    return session.query(FuelPrice).order_by(FuelPrice.period.desc()).first()


def get_latest_gas_price(session: Session) -> GasPrice | None:
    return session.query(GasPrice).order_by(GasPrice.period.desc()).first()

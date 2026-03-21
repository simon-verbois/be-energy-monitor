"""
visualizer.py — Chart generation for Belgian energy price trends.

IMPORTANT: matplotlib.use("Agg") is called at module load time to prevent
"cannot connect to X server" errors in headless Docker containers.
All chart functions return PNG bytes (via io.BytesIO) — no disk I/O.
"""

from __future__ import annotations

import io
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")  # Must be set before any other matplotlib import

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

log = logging.getLogger(__name__)

BRUSSELS_TZ = ZoneInfo("Europe/Brussels")

# ── Design tokens ─────────────────────────────────────────────────────────────
COLOR_BLUE    = "#1565C0"   # Oil <2000L / Essence 95
COLOR_RED     = "#E53935"   # Oil ≥2000L / alert threshold
COLOR_GREEN   = "#2E7D32"   # Electricity
COLOR_ORANGE  = "#E65100"   # Diesel B7
COLOR_PURPLE  = "#6A1B9A"   # Essence 98
COLOR_TEAL    = "#00695C"   # Natural gas
COLOR_BG      = "#FAFAFA"   # Axes background
COLOR_GRID    = "#E0E0E0"   # Grid lines
COLOR_TEXT    = "#333333"   # Axis labels

FIGURE_SIZE  = (10, 4)
FIGURE_DPI   = 150


# ── Shared styling helpers ────────────────────────────────────────────────────

def _style_axes(ax: plt.Axes, y_label: str) -> None:
    """Apply a consistent, clean style to an axes object."""
    ax.set_facecolor(COLOR_BG)
    ax.yaxis.set_label_text(y_label, color=COLOR_TEXT, fontsize=11)
    ax.tick_params(colors=COLOR_TEXT, labelsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color(COLOR_GRID)
    ax.grid(axis="y", color=COLOR_GRID, linewidth=0.8, linestyle="--")
    ax.grid(axis="x", color=COLOR_GRID, linewidth=0.4, linestyle=":")


def _auto_date_fmt(ax: plt.Axes, fig: plt.Figure, dates) -> None:
    """Choose date tick format and locator based on the data span."""
    if not dates:
        return
    span_days = (max(dates) - min(dates)).days if hasattr(max(dates) - min(dates), "days") else 0
    if span_days <= 60:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    elif span_days <= 180:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    fig.autofmt_xdate(rotation=30, ha="right")


def _to_bytes(fig: plt.Figure) -> bytes:
    """Render a matplotlib figure to PNG bytes and close the figure."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=FIGURE_DPI)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ── Oil trend chart ───────────────────────────────────────────────────────────

def generate_oil_chart(oil_records, months: int = 3) -> bytes:
    """
    Heating oil (mazout) trend chart.

    Args:
        oil_records: list of OilPrice ORM objects (ordered by valid_from ASC).
        months:      number of months shown in the chart title.
    """
    if not oil_records:
        return _empty_chart(f"Pas de données mazout sur {months} mois.")

    dates  = [r.valid_from for r in oil_records]
    below  = [r.price_below_2000 for r in oil_records]
    above  = [r.price_above_2000 for r in oil_records]

    fig, ax = plt.subplots(figsize=FIGURE_SIZE, facecolor="white")

    ax.plot(dates, below, color=COLOR_BLUE, linewidth=2, marker="o", markersize=4,
            label="< 2 000 L (TTC)")
    ax.plot(dates, above, color=COLOR_RED,  linewidth=2, marker="s", markersize=4,
            label="≥ 2 000 L (TTC)")

    _style_axes(ax, "€ / L")
    _auto_date_fmt(ax, fig, dates)

    all_prices = below + above
    ax.set_ylim(min(all_prices) * 0.99, max(all_prices) * 1.01)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))

    ax.set_title(f"Gasoil de Chauffage — {months} dernier(s) mois (TTC)",
                 color=COLOR_TEXT, fontsize=13, pad=12)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
    fig.tight_layout()
    log.debug("Oil chart: %d points, %d months", len(dates), months)
    return _to_bytes(fig)


# ── Electricity tariff chart (TotalEnergies — Jour / Nuit) ───────────────────

def generate_elec_chart(elec_records, ceiling: float | None = None, months: int = 3) -> bytes:
    """
    Electricity tariff trend chart showing day and night prices over N months.

    Args:
        elec_records: list of ElecPrice ORM objects (ordered by valid_from ASC).
        ceiling:      optional ELEC_PRICE_CEILING reference line in €/kWh.
        months:       number of months shown in the chart title.
    """
    if not elec_records:
        return _empty_chart(f"Pas de données électricité sur {months} mois.")

    labels      = [r.valid_from.strftime("%b %Y") for r in elec_records]
    day_prices  = [r.price_day   for r in elec_records]
    night_prices= [r.price_night for r in elec_records]

    x = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=FIGURE_SIZE, facecolor="white")

    ax.plot(x, day_prices, color=COLOR_ORANGE, linewidth=2,
            marker="o", markersize=5, label="Jour — HP")
    ax.plot(x, night_prices, color=COLOR_BLUE, linewidth=2,
            marker="s", markersize=5, label="Nuit — HC")

    if ceiling is not None:
        ax.axhline(y=ceiling, color=COLOR_RED, linewidth=1.5, linestyle="--",
                   label=f"Seuil : {ceiling * 100:.2f} c€/kWh", zorder=2)

    _style_axes(ax, "€ / kWh")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)

    all_prices = day_prices + night_prices
    ref = [ceiling] if ceiling else []
    y_min = min(all_prices + ref) * 0.97
    y_max = max(all_prices + ref) * 1.03
    ax.set_ylim(y_min, y_max)

    ax.set_title(f"Électricité TotalEnergies — {months} dernier(s) mois",
                 color=COLOR_TEXT, fontsize=13, pad=12)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
    fig.tight_layout()
    log.debug("Elec chart: %d tariff records, %d months", len(labels), months)
    return _to_bytes(fig)


# ── Fuel trend chart ──────────────────────────────────────────────────────────

def generate_fuel_chart(fuel_records, months: int = 3) -> bytes:
    """
    Fuel (Essence 95/98 E5, Diesel B7) monthly trend chart.

    Args:
        fuel_records: list of FuelPrice ORM objects (ordered by period ASC).
        months:       number of months shown in the title.
    """
    if not fuel_records:
        return _empty_chart(f"Pas de données carburants sur {months} mois.")

    periods = [r.period for r in fuel_records]
    ess_95  = [r.essence_95_e5 for r in fuel_records]
    ess_98  = [r.essence_98_e5 for r in fuel_records]
    diesel  = [r.diesel_b7     for r in fuel_records]

    x = list(range(len(periods)))

    fig, ax = plt.subplots(figsize=FIGURE_SIZE, facecolor="white")
    ax.plot(x, ess_95, color=COLOR_BLUE,   linewidth=2, marker="o", markersize=5,
            label="Essence 95 E5 (TTC)")
    ax.plot(x, ess_98, color=COLOR_PURPLE, linewidth=2, marker="s", markersize=5,
            label="Essence 98 E5 (TTC)")
    ax.plot(x, diesel, color=COLOR_ORANGE, linewidth=2, marker="^", markersize=5,
            label="Diesel B7 (TTC)")

    _style_axes(ax, "€ / L")
    ax.set_xticks(x)
    ax.set_xticklabels(periods, rotation=30, ha="right", fontsize=8)

    all_prices = ess_95 + ess_98 + diesel
    ax.set_ylim(min(all_prices) * 0.98, max(all_prices) * 1.02)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))

    ax.set_title(f"Carburants — {months} dernier(s) mois (TTC)",
                 color=COLOR_TEXT, fontsize=13, pad=12)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
    fig.tight_layout()
    log.debug("Fuel chart: %d months", len(periods))
    return _to_bytes(fig)


# ── Gas trend chart (all quarters) ───────────────────────────────────────────

def generate_gas_chart(gas_records, months: int = 0) -> bytes:
    """
    Natural gas tariff trend chart (TotalEnergies monthly data).

    Args:
        gas_records: list of GasPrice ORM objects (ordered by period ASC).
        months:      number of months shown in the chart title (0 = all data).
    """
    if not gas_records:
        return _empty_chart("Pas de données gaz naturel disponibles.")

    periods = [r.period for r in gas_records]
    prices  = [r.total_kwh_ttc * 100 for r in gas_records]   # display in c€/kWh

    x = list(range(len(periods)))

    fig, ax = plt.subplots(figsize=FIGURE_SIZE, facecolor="white")

    ax.plot(x, prices, color=COLOR_TEAL, linewidth=2, marker="o", markersize=5,
            label="Gaz naturel (TTC)")

    _style_axes(ax, "c€ / kWh (TTC)")
    ax.set_xticks(x)
    ax.set_xticklabels(periods, rotation=30, ha="right", fontsize=8)

    all_prices = prices
    ax.set_ylim(min(all_prices) * 0.97, max(all_prices) * 1.03)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))

    title_suffix = f"{months} dernier(s) mois" if months else "historique complet"
    ax.set_title(f"Gaz Naturel — {title_suffix} (TTC)",
                 color=COLOR_TEXT, fontsize=13, pad=12)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
    fig.tight_layout()
    log.debug("Gas chart: %d months", len(periods))
    return _to_bytes(fig)


# ── Empty / fallback chart ─────────────────────────────────────────────────────

def _empty_chart(message: str) -> bytes:
    """Return a minimal 'no data' placeholder PNG."""
    fig, ax = plt.subplots(figsize=FIGURE_SIZE, facecolor="white")
    ax.set_facecolor(COLOR_BG)
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12,
            color="#888888", transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines[:].set_visible(False)
    fig.tight_layout()
    return _to_bytes(fig)


# ── CLI smoke-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    from datetime import date, timedelta

    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    # ── Synthetic oil data ───────────────────────────────────────────────────
    class _FakeOil:
        def __init__(self, days_ago: int, b: float, a: float):
            self.valid_from = date.today() - timedelta(days=days_ago)
            self.price_below_2000 = b
            self.price_above_2000 = a

    oil_records = [_FakeOil(i, 1.35 - i * 0.005, 1.30 - i * 0.005) for i in range(30, 0, -1)]
    oil_png = generate_oil_chart(oil_records)
    out_oil = "test_oil_chart.png"
    with open(out_oil, "wb") as f:
        f.write(oil_png)
    print(f"Oil chart written to {out_oil} ({len(oil_png)} bytes)")

    # ── Synthetic electricity data ───────────────────────────────────────────
    class _FakeElec:
        def __init__(self, hours_ago: int, price: float):
            self.datetime = datetime.now(UTC) - timedelta(hours=hours_ago)
            self.dayahead_price = price

    import math
    elec_records = [
        _FakeElec(i, 45 + 20 * math.sin(i / 3))
        for i in range(24, 0, -1)
    ]
    elec_png = generate_elec_chart(elec_records, ceiling=50.0)
    out_elec = "test_elec_chart.png"
    with open(out_elec, "wb") as f:
        f.write(elec_png)
    print(f"Elec chart written to {out_elec} ({len(elec_png)} bytes)")

"""
notifier.py — Email notification module.

Builds mobile-first HTML emails with CID-embedded chart images and sends
them via SMTP. Supports two modes controlled by SMTP_AUTH:
  - "starttls" (default) : EHLO → STARTTLS → login  (e.g. Gmail, Office 365)
  - "none"               : plain SMTP relay, no authentication required

The From address is taken from SMTP_FROM (defaults to SMTP_USER when auth
is enabled, or must be set explicitly when using an unauthenticated relay).

Public API:
    send_oil_alert(cfg, result, avg_7day, oil_png)
    send_elec_alert(cfg, result, ceiling, elec_png)
    send_daily_digest(cfg, latest_oil, latest_elec, oil_records, elec_records, oil_png, elec_png)
    send_weekly_summary(cfg, oil_records, elec_records, oil_png, elec_png)
    send_system_alert(cfg, source_name, error_message)
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from src.i18n import get_t

log = logging.getLogger(__name__)

BRUSSELS_TZ = ZoneInfo("Europe/Brussels")

# ── Design constants (inline CSS values) ─────────────────────────────────────
C_PRIMARY   = "#1565C0"
C_DANGER    = "#C62828"
C_SUCCESS   = "#2E7D32"
C_WARNING   = "#F57F17"
C_BG        = "#F5F5F5"
C_WHITE     = "#FFFFFF"
C_BORDER    = "#E0E0E0"
C_TEXT      = "#212121"
C_MUTED     = "#757575"
COLOR_GAS   = "#00695C"   # teal — natural gas sections


def _format_month_year(value, t: dict) -> str:
    """Format a date or 'YYYY-MM' string as a localised 'Month YYYY' string."""
    if isinstance(value, str):
        from datetime import datetime as _dt
        value = _dt.strptime(value, "%Y-%m").date()
    return f"{t['months_long'][value.month]} {value.year}"


# ── Low-level send helper ─────────────────────────────────────────────────────

def _send(cfg, subject: str, html_body: str, images: dict[str, bytes]) -> None:
    """
    Construct and send a multipart/related HTML email with CID-embedded images.

    SMTP behaviour is controlled by cfg.SMTP_AUTH:
      "starttls"  — EHLO → STARTTLS → login (requires SMTP_USER / SMTP_PASSWORD)
      "none"      — plain relay, no authentication (SMTP_USER / SMTP_PASSWORD ignored)

    The From header always uses cfg.SMTP_FROM.
    """
    sender = cfg.SMTP_FROM

    # Outer container: multipart/related (body + inline images)
    msg = MIMEMultipart("related")
    msg["Subject"]  = subject
    msg["From"]     = sender
    msg["To"]       = cfg.ALERT_EMAIL_TO
    msg["X-Mailer"] = "BelgianEnergyMonitor/1.0"

    # Alternative wrapper (text/html inside multipart/alternative for compatibility)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    # Attach chart images with Content-ID headers (RFC 2387)
    for cid_key, png_bytes in images.items():
        img = MIMEImage(png_bytes, "png")
        img.add_header("Content-ID", f"<{cid_key}>")          # angle brackets in header
        img.add_header("Content-Disposition", "inline", filename=f"{cid_key}.png")
        msg.attach(img)

    log.info("Sending email '%s' to %s via %s:%s (auth=%s)",
             subject, cfg.ALERT_EMAIL_TO, cfg.SMTP_SERVER, cfg.SMTP_PORT, cfg.SMTP_AUTH)

    try:
        with smtplib.SMTP(cfg.SMTP_SERVER, cfg.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            if cfg.SMTP_AUTH == "starttls":
                server.starttls()
                server.ehlo()
                server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            # "none": relay without authentication — skip TLS and login entirely
            server.sendmail(sender, [cfg.ALERT_EMAIL_TO], msg.as_string())
        log.info("Email sent successfully.")
    except smtplib.SMTPException as exc:
        log.error("SMTP error while sending email: %s", exc)
        raise


# ── HTML building blocks ──────────────────────────────────────────────────────

def _now_brussels(t: dict) -> str:
    return datetime.now(BRUSSELS_TZ).strftime(t["datetime_fmt"]) + f" ({t['tz_label']})"


def _html_shell(content: str, t: dict) -> str:
    """Wrap content in the full email HTML skeleton (full-width, no grey background)."""
    now = _now_brussels(t)
    return f"""<!DOCTYPE html>
<html lang="{t['html_lang']}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Belgian Energy Monitor</title>
</head>
<body style="margin:0;padding:0;background-color:{C_WHITE};font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;mso-line-height-rule:exactly;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:{C_WHITE};">
    <tr>
      <td>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="background-color:{C_WHITE};">

          <!-- Header -->
          <tr>
            <td style="background-color:{C_PRIMARY};padding:22px 24px;text-align:center;">
              <h1 style="margin:0;font-size:20px;font-weight:700;color:{C_WHITE};
                         letter-spacing:0.5px;">
                🇧🇪 Belgian Energy Monitor
              </h1>
            </td>
          </tr>

          <!-- Dynamic content -->
          {content}

          <!-- Footer -->
          <tr>
            <td style="padding:14px 24px;text-align:center;
                       border-top:1px solid {C_BORDER};">
              <p style="margin:0;font-size:11px;color:{C_MUTED};">
                {t['footer'].format(ts=now)}
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _alert_banner(color: str, emoji: str, title: str, body: str) -> str:
    return f"""
  <tr>
    <td style="padding:20px 24px 0;">
      <div style="background-color:{color}15;border-left:4px solid {color};
                  border-radius:0 4px 4px 0;padding:14px 16px;">
        <p style="margin:0 0 4px;font-size:15px;font-weight:700;color:{color};">
          {emoji}&nbsp; {title}
        </p>
        <p style="margin:0;font-size:14px;color:{C_TEXT};">{body}</p>
      </div>
    </td>
  </tr>"""


def _section_title(title: str, color: str = C_PRIMARY) -> str:
    return f"""
  <tr>
    <td style="padding:20px 24px 8px;">
      <h2 style="margin:0;font-size:16px;font-weight:700;color:{color};
                 border-bottom:2px solid {color};padding-bottom:6px;">
        {title}
      </h2>
    </td>
  </tr>"""


def _price_table(rows: list[tuple[str, str, str]]) -> str:
    """
    rows: list of (label, value, note) tuples.
    Alternating row background for readability.
    """
    html_rows = ""
    for i, (label, value, note) in enumerate(rows):
        bg = C_BG if i % 2 == 0 else C_WHITE
        note_html = f'<span style="font-size:11px;color:{C_MUTED};"> {note}</span>' if note else ""
        html_rows += f"""
        <tr style="background-color:{bg};">
          <td style="padding:9px 12px;border:1px solid {C_BORDER};font-size:13px;
                     color:{C_TEXT};width:60%;">{label}</td>
          <td style="padding:9px 12px;border:1px solid {C_BORDER};font-size:14px;
                     color:{C_TEXT};font-weight:700;">{value}{note_html}</td>
        </tr>"""
    return f"""
  <tr>
    <td style="padding:0 24px 16px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;">
        {html_rows}
      </table>
    </td>
  </tr>"""


def _chart_row(cid: str, alt_text: str) -> str:
    return f"""
  <tr>
    <td style="padding:0 24px 20px;">
      <img src="cid:{cid}" alt="{alt_text}"
           style="width:100%;height:auto;display:block;
                  border:1px solid {C_BORDER};border-radius:4px;" />
    </td>
  </tr>"""


def _divider() -> str:
    return f'<tr><td style="padding:0 24px;"><hr style="border:none;border-top:1px solid {C_BORDER};margin:4px 0;"></td></tr>'


# ── Public email builders ─────────────────────────────────────────────────────

def send_oil_alert(cfg, result, avg_7day: float, oil_png: bytes) -> None:
    """Send an alert email when the oil price drops significantly below the 7-day average."""
    t = get_t(cfg.LANGUAGE)
    drop_pct = (avg_7day - result.price_below_2000) / avg_7day * 100
    banner = _alert_banner(
        C_DANGER, "🛢️",
        t["banner_oil_alert"],
        t["body_oil_alert"].format(
            price=f"{result.price_below_2000:.4f}",
            drop=drop_pct,
            avg=f"{avg_7day:.4f}",
        ),
    )
    table = _price_table([
        (t["lbl_oil_below"],  f"{result.price_below_2000:.4f} €/L", t["lbl_oil_current"]),
        (t["lbl_oil_above"],  f"{result.price_above_2000:.4f} €/L", t["lbl_oil_current"]),
        (t["lbl_oil_avg_7d"], f"{avg_7day:.4f} €/L", ""),
        (t["lbl_oil_drop"],   f"{drop_pct:.1f}%", ""),
        (t["lbl_valid_from"], result.valid_from.strftime("%d/%m/%Y"), ""),
    ])
    chart = _chart_row("oil_chart", t["alt_oil_alert"])
    content = (
        banner
        + _section_title(t["sec_oil_detail"])
        + table
        + _section_title(t["sec_oil_trend_30d"])
        + chart
    )
    html = _html_shell(content, t)
    _send(cfg, t["subj_oil_alert"].format(drop=drop_pct), html, {"oil_chart": oil_png})


def send_elec_alert(cfg, result, ceiling: float, elec_png: bytes) -> None:
    """Send an alert email when the TotalEnergies day tariff drops below the ceiling."""
    t = get_t(cfg.LANGUAGE)
    day   = result.price_day    # €/kWh
    night = result.price_night  # €/kWh
    banner = _alert_banner(
        C_SUCCESS, "⚡",
        t["banner_elec_alert"],
        t["body_elec_alert"].format(price=day * 100, ceiling=ceiling * 100),
    )
    table = _price_table([
        (t["lbl_elec_day"],     f"{day:.5f} €/kWh",   f"({day * 100:.2f} c€/kWh)"),
        (t["lbl_elec_night"],   f"{night:.5f} €/kWh", f"({night * 100:.2f} c€/kWh)"),
        (t["lbl_elec_ceiling"], f"{ceiling:.5f} €/kWh", f"({ceiling * 100:.2f} c€/kWh)"),
        (t["lbl_valid_from"],   _format_month_year(result.valid_from, t), "TotalEnergies"),
    ])
    chart = _chart_row("elec_chart", t["alt_elec_trend"])
    content = (
        banner
        + _section_title(t["sec_elec_detail"], C_SUCCESS)
        + table
        + _section_title(t["sec_elec_history"], C_SUCCESS)
        + chart
    )
    html = _html_shell(content, t)
    _send(cfg, t["subj_elec_alert"].format(price=day * 100), html, {"elec_chart": elec_png})


def send_daily_digest(cfg, latest_oil, latest_fuel, latest_elec, latest_gas,
                      oil_records, fuel_records,
                      oil_png: bytes, fuel_png: bytes, elec_png: bytes,
                      gas_png: bytes | None = None) -> None:
    """Send the 09:00 daily digest with current prices and trend charts."""
    t = get_t(cfg.LANGUAGE)

    # Oil section
    if latest_oil:
        oil_rows: list[tuple[str, str, str]] = [
            (t["lbl_oil_below"], f"{latest_oil.price_below_2000:.4f} €/L", ""),
            (t["lbl_oil_above"], f"{latest_oil.price_above_2000:.4f} €/L", ""),
            (t["lbl_valid_from"], latest_oil.valid_from.strftime("%d/%m/%Y"), ""),
        ]
    else:
        oil_rows = [(t["lbl_no_data"], "—", "")]

    # Fuel section
    if latest_fuel:
        fuel_rows: list[tuple[str, str, str]] = [
            (t["lbl_fuel_95e5"],  f"{latest_fuel.essence_95_e5:.4f} €/L", ""),
            (t["lbl_fuel_98e5"],  f"{latest_fuel.essence_98_e5:.4f} €/L", ""),
            (t["lbl_fuel_diesel"], f"{latest_fuel.diesel_b7:.4f} €/L", ""),
            (t["lbl_period"],     latest_fuel.period, ""),
        ]
    else:
        fuel_rows = [(t["lbl_no_data"], "—", "")]

    # Electricity section
    if latest_elec:
        elec_rows: list[tuple[str, str, str]] = [
            (t["lbl_elec_day"],   f"{latest_elec.price_day:.5f} €/kWh",
             f"({latest_elec.price_day * 100:.2f} c€/kWh)"),
            (t["lbl_elec_night"], f"{latest_elec.price_night:.5f} €/kWh",
             f"({latest_elec.price_night * 100:.2f} c€/kWh)"),
            (t["lbl_source"], "TotalEnergies", _format_month_year(latest_elec.valid_from, t)),
        ]
    else:
        elec_rows = [(t["lbl_no_data"], "—", "")]

    # Gas section
    if latest_gas:
        gas_rows: list[tuple[str, str, str]] = [
            (t["lbl_gas_total"], f"{latest_gas.total_kwh_ttc:.5f} €/kWh", ""),
            (t["lbl_gas_cents"], f"{latest_gas.total_kwh_ttc * 100:.3f} c€/kWh", ""),
            (t["lbl_source"], "TotalEnergies", _format_month_year(latest_gas.period, t)),
        ]
    else:
        gas_rows = [(t["lbl_no_data"], "—", "")]

    content = (
        _section_title(t["src_oil"])
        + _price_table(oil_rows)
        + _chart_row("oil_chart", t["alt_oil_trend"])
        + _divider()
        + _section_title(t["src_fuel"])
        + _price_table(fuel_rows)
        + _chart_row("fuel_chart", t["alt_fuel_trend"])
        + _divider()
        + _section_title(t["src_elec"], C_SUCCESS)
        + _price_table(elec_rows)
        + _chart_row("elec_chart", t["alt_elec_trend"])
        + _divider()
        + _section_title(t["src_gas"], COLOR_GAS)
        + _price_table(gas_rows)
        + (_chart_row("gas_chart", t["alt_gas_history"]) if gas_png else "")
    )
    html = _html_shell(content, t)
    date_str = datetime.now(BRUSSELS_TZ).strftime("%d/%m/%Y")
    images = {"oil_chart": oil_png, "fuel_chart": fuel_png, "elec_chart": elec_png}
    if gas_png:
        images["gas_chart"] = gas_png
    _send(cfg, t["subj_daily"].format(date=date_str), html, images)


def send_weekly_summary(cfg, oil_records, fuel_records, latest_elec, latest_gas,
                        oil_png: bytes, fuel_png: bytes, elec_png: bytes,
                        gas_png: bytes | None = None) -> None:
    """Send the Sunday 18:00 weekly summary with trend analysis."""
    t = get_t(cfg.LANGUAGE)

    # Oil
    if oil_records:
        prices = [r.price_below_2000 for r in oil_records]
        oil_rows: list[tuple[str, str, str]] = [
            (t["lbl_oil_rate_on"].format(date=oil_records[-1].valid_from.strftime("%d/%m/%Y")),
             f"{oil_records[-1].price_below_2000:.4f} €/L", t["lbl_oil_qty"]),
            (t["lbl_oil_min_30d"], f"{min(prices):.4f} €/L", ""),
            (t["lbl_oil_max_30d"], f"{max(prices):.4f} €/L", ""),
            (t["lbl_oil_net_chg"],
             f"{((oil_records[-1].price_below_2000 - oil_records[0].price_below_2000) / oil_records[0].price_below_2000 * 100):+.2f}%",
             t["lbl_oil_vs_30d"]),
        ]
    else:
        oil_rows = [(t["lbl_no_data_weekly"], "—", "")]

    # Fuel
    if fuel_records:
        latest = fuel_records[-1]
        fuel_rows: list[tuple[str, str, str]] = [
            (t["lbl_fuel_95e5"],  f"{latest.essence_95_e5:.4f} €/L", latest.period),
            (t["lbl_fuel_98e5"],  f"{latest.essence_98_e5:.4f} €/L", latest.period),
            (t["lbl_fuel_diesel"], f"{latest.diesel_b7:.4f} €/L",    latest.period),
        ]
    else:
        fuel_rows = [(t["lbl_no_data_weekly"], "—", "")]

    # Electricity
    if latest_elec:
        elec_rows: list[tuple[str, str, str]] = [
            (t["lbl_elec_day"],   f"{latest_elec.price_day:.5f} €/kWh",
             f"({latest_elec.price_day * 100:.2f} c€/kWh)"),
            (t["lbl_elec_night"], f"{latest_elec.price_night:.5f} €/kWh",
             f"({latest_elec.price_night * 100:.2f} c€/kWh)"),
            (t["lbl_source"], "TotalEnergies", _format_month_year(latest_elec.valid_from, t)),
        ]
    else:
        elec_rows = [(t["lbl_no_data_weekly"], "—", "")]

    # Gas
    if latest_gas:
        gas_rows: list[tuple[str, str, str]] = [
            (t["lbl_gas_total"], f"{latest_gas.total_kwh_ttc:.5f} €/kWh", ""),
            (t["lbl_gas_cents"], f"{latest_gas.total_kwh_ttc * 100:.3f} c€/kWh", ""),
            (t["lbl_source"], "TotalEnergies", _format_month_year(latest_gas.period, t)),
        ]
    else:
        gas_rows = [(t["lbl_no_data_weekly"], "—", "")]

    content = (
        _section_title(t["src_oil"])
        + _price_table(oil_rows)
        + _chart_row("oil_chart", t["alt_oil_trend"])
        + _divider()
        + _section_title(t["src_fuel"])
        + _price_table(fuel_rows)
        + _chart_row("fuel_chart", t["alt_fuel_trend"])
        + _divider()
        + _section_title(t["src_elec"], C_SUCCESS)
        + _price_table(elec_rows)
        + _chart_row("elec_chart", t["alt_elec_trend"])
        + _divider()
        + _section_title(t["src_gas"], COLOR_GAS)
        + _price_table(gas_rows)
        + (_chart_row("gas_chart", t["alt_gas_history"]) if gas_png else "")
    )
    html = _html_shell(content, t)
    date_str = datetime.now(BRUSSELS_TZ).strftime("%d/%m/%Y")
    images = {"oil_chart": oil_png, "fuel_chart": fuel_png, "elec_chart": elec_png}
    if gas_png:
        images["gas_chart"] = gas_png
    _send(cfg, t["subj_weekly"].format(date=date_str), html, images)


def send_system_alert(cfg, source_name: str, error_message: str) -> None:
    """Send a system alert email when a data source fails after 3 retries."""
    t = get_t(cfg.LANGUAGE)
    banner = _alert_banner(
        C_DANGER, "🚨",
        t["banner_sys_error"].format(source=source_name),
        t["body_sys_error"].format(
            source=source_name,
            bg=C_BG,
            error=_escape_html(error_message),
        ),
    )
    table = _price_table([
        (t["lbl_sys_source"],   source_name, ""),
        (t["lbl_sys_time"],     _now_brussels(t), ""),
        (t["lbl_sys_attempts"], "3 / 3", ""),
    ])
    content = banner + _section_title(t["sec_sys_error"], C_DANGER) + table
    html = _html_shell(content, t)
    try:
        _send(cfg, t["subj_sys_alert"].format(source=source_name), html, {})
    except Exception as exc:
        # Do not re-raise system alert failures — log only
        log.error("Failed to send system alert email: %s", exc)


def send_startup_report(cfg,
                        oil_result, oil_error: str | None,
                        fuel_result, fuel_error: str | None,
                        elec_result, elec_error: str | None,
                        gas_result, gas_error: str | None,
                        oil_png: bytes | None = None,
                        fuel_png: bytes | None = None,
                        elec_png: bytes | None = None,
                        gas_png: bytes | None = None) -> None:
    """
    Send a single consolidated startup status email covering all four data sources.
    """
    t = get_t(cfg.LANGUAGE)
    errors = {
        t["src_oil_short"]:  oil_error,
        t["src_fuel_short"]: fuel_error,
        t["src_elec_short"]: elec_error,
        t["src_gas_short"]:  gas_error,
    }
    failed_sources = [k for k, v in errors.items() if v]
    has_error = bool(failed_sources)

    if has_error:
        banner = _alert_banner(
            C_DANGER, "🚨",
            t["banner_startup_err"],
            t["body_startup_err"].format(sources=", ".join(failed_sources)),
        )
    else:
        banner = ""

    def _status_rows(result, error, fields: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        if error:
            return [(t["lbl_status"], t["lbl_fail"], ""), (t["lbl_error"], _escape_html(error[:200]), "")]
        return fields + [(t["lbl_status"], t["lbl_ok"], "")]

    oil_rows = _status_rows(oil_result, oil_error, [
        (t["lbl_oil_below"],  f"{oil_result.price_below_2000:.4f} €/L", ""),
        (t["lbl_oil_above"],  f"{oil_result.price_above_2000:.4f} €/L", ""),
        (t["lbl_valid_from"], oil_result.valid_from.strftime("%d/%m/%Y"),
         f"{t['lbl_tariff']} {oil_result.tariff_no}"),
    ] if oil_result else [])

    fuel_rows = _status_rows(fuel_result, fuel_error, [
        (t["lbl_fuel_95e5"],  f"{fuel_result.essence_95_e5:.4f} €/L", ""),
        (t["lbl_fuel_98e5"],  f"{fuel_result.essence_98_e5:.4f} €/L", ""),
        (t["lbl_fuel_diesel"], f"{fuel_result.diesel_b7:.4f} €/L", ""),
        (t["lbl_period"],     fuel_result.period, ""),
    ] if fuel_result else [])

    elec_rows = _status_rows(elec_result, elec_error, [
        (t["lbl_elec_day"],   f"{elec_result.price_day:.5f} €/kWh",
         f"({elec_result.price_day * 100:.2f} c€/kWh)"),
        (t["lbl_elec_night"], f"{elec_result.price_night:.5f} €/kWh",
         f"({elec_result.price_night * 100:.2f} c€/kWh)"),
        (t["lbl_source"], "TotalEnergies", _format_month_year(elec_result.valid_from, t)),
    ] if elec_result else [])

    gas_rows = _status_rows(gas_result, gas_error, [
        (t["lbl_gas_total"], f"{gas_result.total_kwh_ttc:.5f} €/kWh", ""),
        (t["lbl_gas_cents"], f"{gas_result.total_kwh_ttc * 100:.3f} c€/kWh", ""),
        (t["lbl_source"], "TotalEnergies", _format_month_year(gas_result.period, t)),
    ] if gas_result else [])

    content = (
        banner
        + _section_title(t["src_oil"], C_DANGER if oil_error else C_PRIMARY)
        + _price_table(oil_rows)
        + ((_chart_row("oil_chart", t["alt_oil_startup"])) if oil_png and not oil_error else "")
        + _divider()
        + _section_title(t["src_fuel"], C_DANGER if fuel_error else C_PRIMARY)
        + _price_table(fuel_rows)
        + ((_chart_row("fuel_chart", t["alt_fuel_startup"])) if fuel_png and not fuel_error else "")
        + _divider()
        + _section_title(t["src_elec"], C_DANGER if elec_error else C_SUCCESS)
        + _price_table(elec_rows)
        + ((_chart_row("elec_chart", t["alt_elec_startup"])) if elec_png and not elec_error else "")
        + _divider()
        + _section_title(t["src_gas"], C_DANGER if gas_error else COLOR_GAS)
        + _price_table(gas_rows)
        + ((_chart_row("gas_chart", t["alt_gas_startup"])) if gas_png and not gas_error else "")
    )
    html = _html_shell(content, t)
    subject = (
        t["subj_startup_err"].format(sources=", ".join(failed_sources))
        if has_error else
        t["subj_startup_ok"]
    )
    images = {}
    if oil_png and not oil_error:
        images["oil_chart"] = oil_png
    if fuel_png and not fuel_error:
        images["fuel_chart"] = fuel_png
    if elec_png and not elec_error:
        images["elec_chart"] = elec_png
    if gas_png and not gas_error:
        images["gas_chart"] = gas_png
    try:
        _send(cfg, subject, html, images)
    except Exception as exc:
        log.error("Failed to send startup report email: %s", exc)


def _escape_html(text: str) -> str:
    """Minimal HTML escaping for user-facing error messages."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )

"""
scrapers.py — Data acquisition modules for Belgian energy prices.

PetroleumScraper (replaces OilScraper):
  Downloads the SPF Economie tariff PDF once and parses:
  - Gasoil de chauffage (mazout) TTC prices for <2000L and ≥2000L  → OilPriceResult
  - Essence 95/98 RON E5 and Diesel B7 TTC prices                  → FuelPriceResult

ElecScraper:
  TotalEnergies electricity tariff PDF.
  Returns day (Heures Pleines) and night (Heures Creuses) prices in €/kWh.

GasScraper:
  TotalEnergies gas tariff PDF.
  Returns monthly TTC price in €/kWh.

All scrapers use a shared requests.Session with urllib3 retry:
  3 retries, exponential backoff (2 s → 4 s → 8 s), on 429/5xx.
"""

from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pdfplumber
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SPF_LANDING_URL = (
    "https://economie.fgov.be/fr/themes/energie/prix-de-lenergie/"
    "prix-maximum-des-produits/tarif-officiel-des-produits"
)
SPF_BASE_URL   = "https://economie.fgov.be"
SPF_PDF_FILENAME = "Tarifs-officiels-produits-petroliers.pdf"

# TotalEnergies PDF URLs — overridable via environment variables
TOTALENERGIES_ELEC_PDF_URL = os.environ.get(
    "TOTALENERGIES_ELEC_PDF_URL",
    "https://totalenergies.be/static/marketing-documents/b2c/tariff-card/latest/"
    "MYESSENTIAL_ELECTRICITY_WAL_FR.pdf",
)
TOTALENERGIES_GAS_PDF_URL = os.environ.get(
    "TOTALENERGIES_GAS_PDF_URL",
    "https://totalenergies.be/static/marketing-documents/b2c/tariff-card/latest/"
    "MYESSENTIAL_GAS_WAL_FR.pdf",
)

OIL_PRICE_MIN  = 0.50
OIL_PRICE_MAX  = 3.00
FUEL_PRICE_MIN = 0.50
FUEL_PRICE_MAX = 3.50
ELEC_PRICE_MIN = 0.03   # €/kWh (3 c€/kWh)
ELEC_PRICE_MAX = 0.50   # €/kWh (50 c€/kWh)
GAS_PRICE_MIN  = 0.02   # €/kWh
GAS_PRICE_MAX  = 0.50   # €/kWh

REQUEST_TIMEOUT = 30


# ── Custom exception ──────────────────────────────────────────────────────────

class ScraperError(Exception):
    """Raised when a scraper fails after all retries or produces invalid data."""


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class OilPriceResult:
    price_below_2000: float    # TTC €/L, < 2 000 L
    price_above_2000: float    # TTC €/L, ≥ 2 000 L
    valid_from: datetime       # UTC midnight
    tariff_no: str


@dataclass
class FuelPriceResult:
    essence_95_e5: float       # TTC €/L
    essence_98_e5: float       # TTC €/L
    diesel_b7: float           # TTC €/L
    period: str                # "YYYY-MM", e.g. "2026-02"


@dataclass
class ElecPriceResult:
    price_day: float           # €/kWh (Heures Pleines / Jour)
    price_night: float         # €/kWh (Heures Creuses / Nuit)
    valid_from: "date"         # date the tariff was retrieved
    source_url: str


@dataclass
class GasPriceResult:
    total_kwh_ttc: float       # €/kWh TTC
    period: str                # "YYYY-MM", e.g. "2026-03"
    source_url: str


# ── Shared helpers ────────────────────────────────────────────────────────────

_FR_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
_FR_MONTH_RE = re.compile(
    r"\b(" + "|".join(_FR_MONTHS) + r")\s+(\d{4})\b", re.IGNORECASE
)


def _parse_tariff_month(text: str) -> date | None:
    """
    Extract the tariff month from a TotalEnergies PDF (e.g. 'mars 2026').
    Returns the first day of that month as a date, or None if not found.
    """
    m = _FR_MONTH_RE.search(text)
    if m:
        month = _FR_MONTHS[m.group(1).lower()]
        year  = int(m.group(2))
        return date(year, month, 1)
    return None


# ── Shared HTTP session with retry ───────────────────────────────────────────

def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "BelgianEnergyMonitor/1.0"})
    return session


# ── Petroleum scraper (oil + fuel from same PDF) ──────────────────────────────

class PetroleumScraper:
    """
    Downloads the SPF Economie tariff PDF once and returns both:
    - OilPriceResult  (heating oil / mazout)
    - FuelPriceResult (Essence 95/98, Diesel B7)

    PDF table formats:
      Mazout section:
        Product | HT | (±Δ) | 21 | TTC | (±Δ)   ← extract the value AFTER "21"
      Fuel section:
        Product | hors TVA | TVA incluse           ← extract the LAST decimal on the line
    """

    def __init__(self) -> None:
        self._session = build_session()

    def fetch(self) -> tuple[OilPriceResult, FuelPriceResult]:
        """
        Returns (OilPriceResult, FuelPriceResult).
        Raises ScraperError on any failure.
        """
        try:
            pdf_url   = self._discover_pdf_url()
            pdf_bytes = self._download_pdf(pdf_url)
            text      = self._extract_text(pdf_bytes)
            oil       = self._parse_oil(text)
            fuel      = self._parse_fuel(text)
            return oil, fuel
        except ScraperError:
            raise
        except Exception as exc:
            raise ScraperError(f"PetroleumScraper failed unexpectedly: {exc}") from exc

    # ── private helpers ───────────────────────────────────────────────────────

    def _discover_pdf_url(self) -> str:
        try:
            resp = self._session.get(SPF_LANDING_URL, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ScraperError(f"Cannot reach SPF landing page: {exc}") from exc

        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup.find_all("a", href=True):
            href: str = tag["href"]
            if SPF_PDF_FILENAME in href:
                url = href if href.startswith("http") else SPF_BASE_URL + href
                log.info("Found tariff PDF URL: %s", url)
                return url
        # Fallback
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.lower().endswith(".pdf") and "energie" in href.lower():
                url = href if href.startswith("http") else SPF_BASE_URL + href
                log.warning("Using fallback PDF URL: %s", url)
                return url

        raise ScraperError(
            "Could not locate the tariff PDF on the SPF Economie page."
        )

    def _download_pdf(self, url: str) -> bytes:
        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ScraperError(f"Failed to download tariff PDF: {exc}") from exc
        return resp.content

    @staticmethod
    def _extract_text(pdf_bytes: bytes) -> str:
        buf = io.BytesIO(pdf_bytes)
        try:
            with pdfplumber.open(buf) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            raise ScraperError(f"pdfplumber failed: {exc}") from exc
        if not text.strip():
            raise ScraperError("PDF text extraction returned empty content.")
        return text

    # ── Oil (mazout) parsing ──────────────────────────────────────────────────

    def _parse_oil(self, text: str) -> OilPriceResult:
        price_below = self._extract_mazout_price(text, "moins de 2000")
        price_above = self._extract_mazout_price(text, "partir de 2000")
        valid_from  = self._extract_oil_valid_from(text)
        tariff_no   = self._extract_tariff_no(text)

        for label, price in (("below_2000", price_below), ("above_2000", price_above)):
            if not (OIL_PRICE_MIN < price < OIL_PRICE_MAX):
                raise ScraperError(
                    f"Oil {label} price {price:.4f} €/L outside expected range "
                    f"[{OIL_PRICE_MIN}, {OIL_PRICE_MAX}]."
                )
        result = OilPriceResult(price_below, price_above, valid_from, tariff_no)
        log.debug("Parsed oil tariff: %s", result)
        return result

    @staticmethod
    def _extract_mazout_price(text: str, quantity_marker: str) -> float:
        """
        Mazout table format: Product | HT | (±Δ) | 21 | TTC | (±Δ)
        Strategy: find the value that immediately follows the VAT column "21".
        Fallback: take the second-to-last decimal on the line.
        """
        lines = text.splitlines()
        in_chauffage = False
        for line in lines:
            if "Gasoil de chauffage" in line and ":" in line:
                in_chauffage = True
            if not in_chauffage:
                continue
            if quantity_marker.lower() in line.lower():
                m = re.search(r"\b21\b\s+([\d]{1,2},[\d]{2,4})", line)
                if m:
                    return float(m.group(1).replace(",", "."))
                # Fallback: second-to-last decimal token
                matches = re.findall(r"\b(\d{1,2},\d{2,4})\b", line)
                if len(matches) >= 2:
                    log.debug("VAT-pattern fallback for mazout '%s': tokens=%s", quantity_marker, matches)
                    return float(matches[-2].replace(",", "."))
                raise ScraperError(f"No price token for '{quantity_marker}': {line!r}")

        raise ScraperError(
            f"Line '{quantity_marker}' not found in 'Gasoil de chauffage' section."
        )

    @staticmethod
    def _extract_oil_valid_from(text: str) -> datetime:
        for pattern in [
            r"valable\s+[àa]\s+partir\s+du\s*:?\s*(\d{2}/\d{2}/\d{4})",
            r"(?:applicable|en vigueur)\s+[àa]\s+partir\s+du\s*:?\s*(\d{2}/\d{2}/\d{4})",
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return datetime.strptime(m.group(1), "%d/%m/%Y").replace(tzinfo=UTC)
        log.warning("Could not extract mazout validity date; using today.")
        return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _extract_tariff_no(text: str) -> str:
        m = re.search(r"(?:liste|tarif)\s+n[o°]\s*[:\.]?\s*([\d/\-]+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    # ── Fuel (carburants) parsing ─────────────────────────────────────────────

    def _parse_fuel(self, text: str) -> FuelPriceResult:
        """
        Fuel table format: Product | hors TVA | TVA incluse
        The last decimal on the line is the TTC price (TVA incluse).
        """
        ess_95 = self._extract_fuel_price(text, "Essence 95 RON E5")
        ess_98 = self._extract_fuel_price(text, "Essence 98 RON E5")
        diesel = self._extract_fuel_price(text, "Diesel B7")
        period = self._extract_fuel_period(text)

        for label, price in (("Ess95", ess_95), ("Ess98", ess_98), ("DieselB7", diesel)):
            if not (FUEL_PRICE_MIN < price < FUEL_PRICE_MAX):
                raise ScraperError(
                    f"Fuel {label} price {price:.4f} €/L outside expected range "
                    f"[{FUEL_PRICE_MIN}, {FUEL_PRICE_MAX}]."
                )

        result = FuelPriceResult(ess_95, ess_98, diesel, period)
        log.debug("Parsed fuel prices: %s", result)
        return result

    @staticmethod
    def _extract_fuel_price(text: str, product_marker: str) -> float:
        """
        Find the line that contains `product_marker` and return the last
        decimal number on it (= TVA incluse column in the fuel table).
        """
        for line in text.splitlines():
            if product_marker.lower() in line.lower():
                matches = re.findall(r"\b(\d{1,2},\d{4})\b", line)
                if matches:
                    return float(matches[-1].replace(",", "."))
                # Fallback: any decimal with 2-4 dp
                matches = re.findall(r"\b(\d{1,2},\d{2,4})\b", line)
                if matches:
                    return float(matches[-1].replace(",", "."))
                raise ScraperError(f"No price token on fuel line for '{product_marker}': {line!r}")

        raise ScraperError(f"Product '{product_marker}' not found in PDF.")

    @staticmethod
    def _extract_fuel_period(text: str) -> str:
        """
        Extract the publication month from the PDF title.
        Title example: "Prix moyens maximaux produits pétroliers 02/2026"
        Returns "YYYY-MM", e.g. "2026-02".
        """
        m = re.search(r"\b(\d{2})/(\d{4})\b", text)
        if m:
            return f"{m.group(2)}-{m.group(1)}"
        return datetime.now(UTC).strftime("%Y-%m")


# Backward-compatible alias
OilScraper = PetroleumScraper


# ── Electricity scraper (TotalEnergies tariff PDF) ───────────────────────────

class ElecScraper:
    """
    Downloads the TotalEnergies electricity tariff PDF and extracts day
    (Heures Pleines / Jour) and night (Heures Creuses / Nuit) prices.

    PDF shows prices in c€/kWh (Belgian comma format); stored in €/kWh.
    Typical values: Jour ~12 c€/kWh, Nuit ~10 c€/kWh.
    """

    DAY_KEYWORDS   = ("jour", "heures pleines", " hp ", "heure pleine")
    NIGHT_KEYWORDS = ("nuit", "heures creuses", " hc ", "heure creuse")

    def __init__(self) -> None:
        self._session = build_session()

    def fetch(self) -> ElecPriceResult:
        try:
            pdf_bytes = self._download_pdf()
            text = self._extract_text(pdf_bytes)
            price_day, price_night = self._parse_prices(text)
            valid_from = _parse_tariff_month(text) or datetime.now(UTC).date()
            result = ElecPriceResult(
                price_day=price_day,
                price_night=price_night,
                valid_from=valid_from,
                source_url=TOTALENERGIES_ELEC_PDF_URL,
            )
            log.debug("TotalEnergies tariff: jour=%.4f €/kWh (%.2f c€/kWh), "
                      "nuit=%.4f €/kWh (%.2f c€/kWh)",
                      price_day, price_day * 100, price_night, price_night * 100)
            return result
        except ScraperError:
            raise
        except Exception as exc:
            raise ScraperError(f"ElecScraper failed unexpectedly: {exc}") from exc

    def _download_pdf(self) -> bytes:
        try:
            resp = self._session.get(TOTALENERGIES_ELEC_PDF_URL, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ScraperError(f"Failed to download TotalEnergies tariff PDF: {exc}") from exc
        return resp.content

    @staticmethod
    def _extract_text(pdf_bytes: bytes) -> str:
        buf = io.BytesIO(pdf_bytes)
        try:
            with pdfplumber.open(buf) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            raise ScraperError(f"pdfplumber failed on TotalEnergies PDF: {exc}") from exc
        if not text.strip():
            raise ScraperError("TotalEnergies PDF text extraction returned empty content.")
        log.debug("TotalEnergies PDF text (first 500 chars): %s", text[:500])
        return text

    @classmethod
    def _parse_prices(cls, text: str) -> tuple[float, float]:
        """
        Extract day (Heures Pleines) and night (Heures Creuses) prices from the PDF.

        Strategy: find the "Tarif mensuel" anchor line, then take the next line that
        contains ≥3 plausible c€/kWh values. The table layout is:
          [0] Compteur simple  [1] Heures Pleines  [2] Heures Creuses  [3] Excl. nuit
        so price_day=vals[1], price_night=vals[2].

        This avoids the "À titre indicatif" section lower in the document which
        shows estimated prices based on the previous month's BELPEX index.
        """
        lines = text.splitlines()

        # Primary strategy: anchor on "Tarif mensuel"
        for i, line in enumerate(lines):
            if "tarif mensuel" in line.lower():
                for j in range(i + 1, min(i + 6, len(lines))):
                    nums = re.findall(r"\b(\d{1,2}[,\.]\d{2})\b", lines[j])
                    vals = [float(n.replace(",", ".")) for n in nums
                            if 3 < float(n.replace(",", ".")) < 50]
                    if len(vals) >= 3:
                        price_day   = vals[1] / 100.0   # Heures Pleines
                        price_night = vals[2] / 100.0   # Heures Creuses
                        log.debug(
                            "ElecScraper tariff row: %s  →  jour=%.2f  nuit=%.2f c€/kWh",
                            vals, price_day * 100, price_night * 100,
                        )
                        return price_day, price_night

        # Fallback: header line containing both "heures pleines" and "heures creuses"
        for i, line in enumerate(lines):
            line_low = line.lower()
            if "heures pleines" in line_low and "heures creuses" in line_low:
                for j in range(i + 1, min(i + 8, len(lines))):
                    nums = re.findall(r"\b(\d{1,2}[,\.]\d{2})\b", lines[j])
                    vals = [float(n.replace(",", ".")) for n in nums
                            if 3 < float(n.replace(",", ".")) < 50]
                    if len(vals) >= 3:
                        price_day   = vals[1] / 100.0
                        price_night = vals[2] / 100.0
                        log.warning(
                            "ElecScraper fallback (header anchor): jour=%.2f nuit=%.2f c€/kWh",
                            price_day * 100, price_night * 100,
                        )
                        return price_day, price_night

        raise ScraperError(
            "Could not extract day/night electricity prices from TotalEnergies PDF "
            "(neither 'Tarif mensuel' anchor nor column header found)."
        )


# ── Natural gas scraper (TotalEnergies tariff PDF) ───────────────────────────

class GasScraper:
    """
    Downloads the TotalEnergies gas tariff PDF and extracts the monthly
    price in €/kWh.

    PDF URL is read from TOTALENERGIES_GAS_PDF_URL env var.
    PDF shows prices in c€/kWh (Belgian comma format); stored in €/kWh.
    Typical value: ~4 c€/kWh.

    Parsing strategy: find the "Tarif mensuel" anchor row, then take the
    first plausible c€/kWh value (range 1–30) from the following lines.
    """

    def __init__(self) -> None:
        self._session = build_session()

    def fetch(self) -> GasPriceResult:
        try:
            pdf_bytes = self._download_pdf()
            text      = self._extract_text(pdf_bytes)
            price      = self._parse_price(text)
            tariff_date = _parse_tariff_month(text)
            period     = tariff_date.strftime("%Y-%m") if tariff_date else datetime.now(UTC).strftime("%Y-%m")
            result    = GasPriceResult(
                total_kwh_ttc=price,
                period=period,
                source_url=TOTALENERGIES_GAS_PDF_URL,
            )
            log.debug("TotalEnergies gas tariff: %.5f €/kWh (%.2f c€/kWh)",
                      price, price * 100)
            return result
        except ScraperError:
            raise
        except Exception as exc:
            raise ScraperError(f"GasScraper failed unexpectedly: {exc}") from exc

    def _download_pdf(self) -> bytes:
        try:
            resp = self._session.get(TOTALENERGIES_GAS_PDF_URL, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ScraperError(
                f"Failed to download TotalEnergies gas tariff PDF: {exc}"
            ) from exc
        return resp.content

    @staticmethod
    def _extract_text(pdf_bytes: bytes) -> str:
        buf = io.BytesIO(pdf_bytes)
        try:
            with pdfplumber.open(buf) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            raise ScraperError(f"pdfplumber failed on TotalEnergies gas PDF: {exc}") from exc
        if not text.strip():
            raise ScraperError("TotalEnergies gas PDF text extraction returned empty content.")
        log.debug("TotalEnergies gas PDF text (first 500 chars): %s", text[:500])
        return text

    @staticmethod
    def _parse_price(text: str) -> float:
        """
        Extract the monthly gas price from the PDF.

        Strategy: find the "Tarif mensuel" anchor, then scan the following
        lines for the first plausible c€/kWh value (range 1–30).
        Falls back to scanning the whole document for a single plausible value.
        Returns price in €/kWh.
        """
        lines = text.splitlines()

        # Primary: anchor on "Tarif mensuel"
        for i, line in enumerate(lines):
            if "tarif mensuel" in line.lower():
                for j in range(i, min(i + 6, len(lines))):
                    nums = re.findall(r"\b(\d{1,2}[,\.]\d{2})\b", lines[j])
                    for n in nums:
                        val = float(n.replace(",", "."))
                        if 1 < val < 30:            # plausible c€/kWh range for gas
                            price = val / 100.0
                            log.debug("GasScraper anchor match: %.2f c€/kWh on line: %r",
                                      val, lines[j])
                            return price

        # Fallback: first plausible value in the whole document
        all_nums = re.findall(r"\b(\d{1,2}[,\.]\d{2})\b", text)
        candidates = [float(n.replace(",", ".")) for n in all_nums if 1 < float(n.replace(",", ".")) < 30]
        if candidates:
            price = candidates[0] / 100.0
            log.warning("GasScraper: used full-document fallback, price=%.2f c€/kWh", price * 100)
            return price

        raise ScraperError(
            "Could not extract gas price from TotalEnergies PDF "
            "(no plausible value found in range 1–30 c€/kWh)."
        )


# ── CLI smoke-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    print("\n=== PetroleumScraper ===")
    try:
        oil, fuel = PetroleumScraper().fetch()
        print(f"  [Oil]  Tariff {oil.tariff_no} valid from {oil.valid_from.date()}")
        print(f"         < 2000 L : {oil.price_below_2000:.4f} €/L")
        print(f"         ≥ 2000 L : {oil.price_above_2000:.4f} €/L")
        print(f"  [Fuel] Period: {fuel.period}")
        print(f"         Ess 95 E5 : {fuel.essence_95_e5:.4f} €/L")
        print(f"         Ess 98 E5 : {fuel.essence_98_e5:.4f} €/L")
        print(f"         Diesel B7 : {fuel.diesel_b7:.4f} €/L")
    except ScraperError as e:
        print(f"  ERROR: {e}")

    print("\n=== ElecScraper (TotalEnergies PDF) ===")
    try:
        elec = ElecScraper().fetch()
        print(f"  Valid from : {elec.valid_from}")
        print(f"  Jour (HP)  : {elec.price_day:.5f} €/kWh  ({elec.price_day * 100:.2f} c€/kWh)")
        print(f"  Nuit (HC)  : {elec.price_night:.5f} €/kWh  ({elec.price_night * 100:.2f} c€/kWh)")
        print(f"  Source     : {elec.source_url}")
    except ScraperError as e:
        print(f"  ERROR: {e}")

    print("\n=== GasScraper (TotalEnergies PDF) ===")
    try:
        gas = GasScraper().fetch()
        print(f"  Period   : {gas.period}")
        print(f"  Prix TTC : {gas.total_kwh_ttc:.5f} €/kWh  ({gas.total_kwh_ttc * 100:.2f} c€/kWh)")
        print(f"  Source   : {gas.source_url}")
    except ScraperError as e:
        print(f"  ERROR: {e}")

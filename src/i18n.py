"""
i18n.py — Translation strings for email notifications and charts.

Supported locales: fr (French), en (English), nl (Dutch/Flemish).
Controlled by the LANGUAGE environment variable (default: fr).
"""

from __future__ import annotations

TRANSLATIONS: dict[str, dict] = {
    "fr": {
        # HTML
        "html_lang": "fr",

        # Date/time
        "months_long": [
            "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
        ],
        "tz_label": "Bruxelles",
        "datetime_fmt": "%d/%m/%Y, %H:%M",

        # Footer
        "footer": "Généré le {ts} · Sources : SPF Économie · TotalEnergies",

        # Energy source names
        "src_oil":        "Gasoil de chauffage",
        "src_fuel":       "Carburants",
        "src_elec":       "Électricité",
        "src_gas":        "Gaz naturel",
        "src_oil_short":  "Mazout",
        "src_fuel_short": "Carburants",
        "src_elec_short": "Électricité",
        "src_gas_short":  "Gaz naturel",

        # Common labels
        "lbl_no_data":        "Données non disponibles",
        "lbl_no_data_weekly": "Données insuffisantes",
        "lbl_valid_from":     "Valable depuis",
        "lbl_period":         "Période",
        "lbl_source":         "Source",
        "lbl_status":         "Statut",
        "lbl_error":          "Erreur",
        "lbl_ok":             "✅ OK",
        "lbl_fail":           "❌ Échec",
        "lbl_tariff":         "Tarif",

        # Oil labels
        "lbl_oil_below":   "Moins de 2 000 L (TTC)",
        "lbl_oil_above":   "À partir de 2 000 L (TTC)",
        "lbl_oil_avg_7d":  "Moyenne 7 jours (< 2 000 L)",
        "lbl_oil_drop":    "Baisse constatée",
        "lbl_oil_current": "actuel",
        "lbl_oil_rate_on": "Tarif au {date}",
        "lbl_oil_min_30d": "Minimum 30j",
        "lbl_oil_max_30d": "Maximum 30j",
        "lbl_oil_net_chg": "Variation nette",
        "lbl_oil_vs_30d":  "vs il y a 30 jours",
        "lbl_oil_qty":     "< 2 000 L",

        # Fuel labels
        "lbl_fuel_95e5":  "Essence 95 RON E5 (TTC)",
        "lbl_fuel_98e5":  "Essence 98 RON E5 (TTC)",
        "lbl_fuel_diesel": "Diesel B7 (TTC)",

        # Electricity labels
        "lbl_elec_day":     "Tarif Jour (HP)",
        "lbl_elec_night":   "Tarif Nuit (HC)",
        "lbl_elec_ceiling": "Seuil d'alerte",

        # Gas labels
        "lbl_gas_total": "Prix total TTC",
        "lbl_gas_cents": "En centimes",

        # System alert labels
        "lbl_sys_source":   "Source défaillante",
        "lbl_sys_time":     "Heure de l'erreur (Bruxelles)",
        "lbl_sys_attempts": "Tentatives effectuées",

        # Chart alt texts
        "alt_oil_alert":   "Évolution du prix du mazout — 30 jours",
        "alt_oil_trend":   "Tendance mazout",
        "alt_fuel_trend":  "Tendance carburants",
        "alt_elec_trend":  "Tendance électricité",
        "alt_gas_history": "Historique gaz naturel",
        "alt_oil_startup":  "Évolution mazout",
        "alt_fuel_startup": "Évolution carburants",
        "alt_elec_startup": "Évolution électricité",
        "alt_gas_startup":  "Évolution gaz naturel",

        # Section titles
        "sec_oil_detail":    "📊 Détail du Tarif Mazout",
        "sec_oil_trend_30d": "📈 Évolution — 30 jours",
        "sec_elec_detail":   "⚡ Détail du Tarif Électricité",
        "sec_elec_history":  "📈 Évolution — historique",
        "sec_sys_error":     "🔧 Détails de l'Erreur",

        # Email subjects
        "subj_oil_alert":   "Alerte mazout — Baisse de {drop:.1f}%",
        "subj_elec_alert":  "Alerte électricité — Jour {price:.2f} c€/kWh",
        "subj_daily":       "Rapport quotidien — {date}",
        "subj_weekly":      "Résumé hebdomadaire — semaine du {date}",
        "subj_sys_alert":   "Erreur système — {source}",
        "subj_startup_ok":  "Démarrage — Energy Monitor",
        "subj_startup_err": "Démarrage — Erreur ({sources})",

        # Banner titles
        "banner_oil_alert":   "Baisse du prix du mazout",
        "banner_elec_alert":  "Tarif électricité sous le seuil",
        "banner_sys_error":   "Erreur Système — Source : {source}",
        "banner_startup_err": "Démarrage — Erreur(s) détectée(s)",

        # Banner / message bodies
        "body_oil_alert": (
            "Le prix actuel (<strong>{price} €/L</strong>) est "
            "<strong>{drop:.1f}%</strong> inférieur à la moyenne des 7 derniers jours "
            "({avg} €/L)."
        ),
        "body_elec_alert": (
            "Le tarif Jour (<strong>{price:.2f} c€/kWh</strong>) "
            "est passé sous votre seuil d'alerte de {ceiling:.2f} c€/kWh."
        ),
        "body_sys_error": (
            "La source de données <strong>{source}</strong> a échoué après 3 tentatives.<br>"
            "<code style='font-family:monospace;font-size:12px;background:{bg};"
            "padding:2px 4px;border-radius:3px;'>{error}</code>"
        ),
        "body_startup_err": "Sources en erreur : <strong>{sources}</strong>.",

        # Visualizer — chart titles & legends
        "chart_oil_title":        "Gasoil de Chauffage — {months} dernier(s) mois (TTC)",
        "chart_oil_empty":        "Pas de données mazout sur {months} mois.",
        "chart_oil_legend_below": "< 2 000 L (TTC)",
        "chart_oil_legend_above": "≥ 2 000 L (TTC)",
        "chart_elec_title":       "Électricité TotalEnergies — {months} dernier(s) mois",
        "chart_elec_empty":       "Pas de données électricité sur {months} mois.",
        "chart_elec_legend_day":     "Jour — HP",
        "chart_elec_legend_night":   "Nuit — HC",
        "chart_elec_legend_ceiling": "Seuil : {price:.2f} c€/kWh",
        "chart_fuel_title":        "Carburants — {months} dernier(s) mois (TTC)",
        "chart_fuel_empty":        "Pas de données carburants sur {months} mois.",
        "chart_fuel_legend_95":    "Essence 95 E5 (TTC)",
        "chart_fuel_legend_98":    "Essence 98 E5 (TTC)",
        "chart_fuel_legend_diesel": "Diesel B7 (TTC)",
        "chart_gas_title_months":  "Gaz Naturel — {months} dernier(s) mois (TTC)",
        "chart_gas_title_all":     "Gaz Naturel — historique complet (TTC)",
        "chart_gas_empty":         "Pas de données gaz naturel disponibles.",
        "chart_gas_legend":        "Gaz naturel (TTC)",
    },

    "en": {
        "html_lang": "en",
        "months_long": [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        "tz_label": "Brussels",
        "datetime_fmt": "%d/%m/%Y, %H:%M",
        "footer": "Generated on {ts} · Sources: SPF Economy · TotalEnergies",
        "src_oil":        "Heating Oil",
        "src_fuel":       "Fuels",
        "src_elec":       "Electricity",
        "src_gas":        "Natural Gas",
        "src_oil_short":  "Heating Oil",
        "src_fuel_short": "Fuels",
        "src_elec_short": "Electricity",
        "src_gas_short":  "Natural Gas",
        "lbl_no_data":        "Data not available",
        "lbl_no_data_weekly": "Insufficient data",
        "lbl_valid_from":     "Valid from",
        "lbl_period":         "Period",
        "lbl_source":         "Source",
        "lbl_status":         "Status",
        "lbl_error":          "Error",
        "lbl_ok":             "✅ OK",
        "lbl_fail":           "❌ Failed",
        "lbl_tariff":         "Tariff",
        "lbl_oil_below":   "Below 2,000 L (incl. VAT)",
        "lbl_oil_above":   "From 2,000 L (incl. VAT)",
        "lbl_oil_avg_7d":  "7-day average (< 2,000 L)",
        "lbl_oil_drop":    "Observed drop",
        "lbl_oil_current": "current",
        "lbl_oil_rate_on": "Rate on {date}",
        "lbl_oil_min_30d": "30d Minimum",
        "lbl_oil_max_30d": "30d Maximum",
        "lbl_oil_net_chg": "Net change",
        "lbl_oil_vs_30d":  "vs 30 days ago",
        "lbl_oil_qty":     "< 2,000 L",
        "lbl_fuel_95e5":   "Petrol 95 RON E5 (incl. VAT)",
        "lbl_fuel_98e5":   "Petrol 98 RON E5 (incl. VAT)",
        "lbl_fuel_diesel": "Diesel B7 (incl. VAT)",
        "lbl_elec_day":     "Day Rate (Peak Hours)",
        "lbl_elec_night":   "Night Rate (Off-Peak)",
        "lbl_elec_ceiling": "Alert threshold",
        "lbl_gas_total": "Total price (incl. VAT)",
        "lbl_gas_cents": "In cents",
        "lbl_sys_source":   "Failing source",
        "lbl_sys_time":     "Error time (Brussels)",
        "lbl_sys_attempts": "Attempts made",
        "alt_oil_alert":   "Heating oil price trend — 30 days",
        "alt_oil_trend":   "Heating oil trend",
        "alt_fuel_trend":  "Fuels trend",
        "alt_elec_trend":  "Electricity trend",
        "alt_gas_history": "Natural gas history",
        "alt_oil_startup":  "Heating oil trend",
        "alt_fuel_startup": "Fuels trend",
        "alt_elec_startup": "Electricity trend",
        "alt_gas_startup":  "Natural gas trend",
        "sec_oil_detail":    "📊 Heating Oil Rate Details",
        "sec_oil_trend_30d": "📈 Trend — 30 days",
        "sec_elec_detail":   "⚡ Electricity Rate Details",
        "sec_elec_history":  "📈 Trend — history",
        "sec_sys_error":     "🔧 Error Details",
        "subj_oil_alert":   "Heating oil alert — Drop of {drop:.1f}%",
        "subj_elec_alert":  "Electricity alert — Day {price:.2f} c€/kWh",
        "subj_daily":       "Daily report — {date}",
        "subj_weekly":      "Weekly summary — week of {date}",
        "subj_sys_alert":   "System error — {source}",
        "subj_startup_ok":  "Startup — Energy Monitor",
        "subj_startup_err": "Startup — Error ({sources})",
        "banner_oil_alert":   "Heating oil price drop",
        "banner_elec_alert":  "Electricity rate below threshold",
        "banner_sys_error":   "System Error — Source: {source}",
        "banner_startup_err": "Startup — Error(s) detected",
        "body_oil_alert": (
            "The current price (<strong>{price} €/L</strong>) is "
            "<strong>{drop:.1f}%</strong> below the 7-day average ({avg} €/L)."
        ),
        "body_elec_alert": (
            "The day rate (<strong>{price:.2f} c€/kWh</strong>) "
            "has dropped below your alert threshold of {ceiling:.2f} c€/kWh."
        ),
        "body_sys_error": (
            "Data source <strong>{source}</strong> failed after 3 retries.<br>"
            "<code style='font-family:monospace;font-size:12px;background:{bg};"
            "padding:2px 4px;border-radius:3px;'>{error}</code>"
        ),
        "body_startup_err": "Failed sources: <strong>{sources}</strong>.",
        "chart_oil_title":        "Heating Oil — last {months} month(s) (incl. VAT)",
        "chart_oil_empty":        "No heating oil data for the past {months} months.",
        "chart_oil_legend_below": "< 2,000 L (incl. VAT)",
        "chart_oil_legend_above": "≥ 2,000 L (incl. VAT)",
        "chart_elec_title":       "Electricity TotalEnergies — last {months} month(s)",
        "chart_elec_empty":       "No electricity data for the past {months} months.",
        "chart_elec_legend_day":     "Day — Peak",
        "chart_elec_legend_night":   "Night — Off-peak",
        "chart_elec_legend_ceiling": "Threshold: {price:.2f} c€/kWh",
        "chart_fuel_title":        "Fuels — last {months} month(s) (incl. VAT)",
        "chart_fuel_empty":        "No fuel data for the past {months} months.",
        "chart_fuel_legend_95":    "Petrol 95 E5 (incl. VAT)",
        "chart_fuel_legend_98":    "Petrol 98 E5 (incl. VAT)",
        "chart_fuel_legend_diesel": "Diesel B7 (incl. VAT)",
        "chart_gas_title_months":  "Natural Gas — last {months} month(s) (incl. VAT)",
        "chart_gas_title_all":     "Natural Gas — full history (incl. VAT)",
        "chart_gas_empty":         "No natural gas data available.",
        "chart_gas_legend":        "Natural Gas (incl. VAT)",
    },

    "nl": {
        "html_lang": "nl",
        "months_long": [
            "", "Januari", "Februari", "Maart", "April", "Mei", "Juni",
            "Juli", "Augustus", "September", "Oktober", "November", "December",
        ],
        "tz_label": "Brussel",
        "datetime_fmt": "%d/%m/%Y, %H:%M",
        "footer": "Gegenereerd op {ts} · Bronnen: FOD Economie · TotalEnergies",
        "src_oil":        "Stookolie",
        "src_fuel":       "Brandstoffen",
        "src_elec":       "Elektriciteit",
        "src_gas":        "Aardgas",
        "src_oil_short":  "Stookolie",
        "src_fuel_short": "Brandstoffen",
        "src_elec_short": "Elektriciteit",
        "src_gas_short":  "Aardgas",
        "lbl_no_data":        "Gegevens niet beschikbaar",
        "lbl_no_data_weekly": "Onvoldoende gegevens",
        "lbl_valid_from":     "Geldig vanaf",
        "lbl_period":         "Periode",
        "lbl_source":         "Bron",
        "lbl_status":         "Status",
        "lbl_error":          "Fout",
        "lbl_ok":             "✅ OK",
        "lbl_fail":           "❌ Mislukt",
        "lbl_tariff":         "Tarief",
        "lbl_oil_below":   "Minder dan 2.000 L (incl. BTW)",
        "lbl_oil_above":   "Vanaf 2.000 L (incl. BTW)",
        "lbl_oil_avg_7d":  "7-daags gemiddelde (< 2.000 L)",
        "lbl_oil_drop":    "Vastgestelde daling",
        "lbl_oil_current": "huidig",
        "lbl_oil_rate_on": "Tarief per {date}",
        "lbl_oil_min_30d": "Minimum 30d",
        "lbl_oil_max_30d": "Maximum 30d",
        "lbl_oil_net_chg": "Netto variatie",
        "lbl_oil_vs_30d":  "vs 30 dagen geleden",
        "lbl_oil_qty":     "< 2.000 L",
        "lbl_fuel_95e5":   "Benzine 95 RON E5 (incl. BTW)",
        "lbl_fuel_98e5":   "Benzine 98 RON E5 (incl. BTW)",
        "lbl_fuel_diesel": "Diesel B7 (incl. BTW)",
        "lbl_elec_day":     "Dagtarief (Piekuren)",
        "lbl_elec_night":   "Nachttarief (Daluren)",
        "lbl_elec_ceiling": "Alarmdrempel",
        "lbl_gas_total": "Totale prijs incl. BTW",
        "lbl_gas_cents": "In centiemen",
        "lbl_sys_source":   "Defecte bron",
        "lbl_sys_time":     "Tijdstip fout (Brussel)",
        "lbl_sys_attempts": "Aantal pogingen",
        "alt_oil_alert":   "Evolutie stookolieprijs — 30 dagen",
        "alt_oil_trend":   "Trend stookolie",
        "alt_fuel_trend":  "Trend brandstoffen",
        "alt_elec_trend":  "Trend elektriciteit",
        "alt_gas_history": "Historiek aardgas",
        "alt_oil_startup":  "Evolutie stookolie",
        "alt_fuel_startup": "Evolutie brandstoffen",
        "alt_elec_startup": "Evolutie elektriciteit",
        "alt_gas_startup":  "Evolutie aardgas",
        "sec_oil_detail":    "📊 Detail Stookolietarief",
        "sec_oil_trend_30d": "📈 Evolutie — 30 dagen",
        "sec_elec_detail":   "⚡ Detail Elektriciteitstarief",
        "sec_elec_history":  "📈 Evolutie — historiek",
        "sec_sys_error":     "🔧 Foutdetails",
        "subj_oil_alert":   "Stookolie alarm — Daling van {drop:.1f}%",
        "subj_elec_alert":  "Elektriciteit alarm — Dag {price:.2f} c€/kWh",
        "subj_daily":       "Dagelijks rapport — {date}",
        "subj_weekly":      "Wekelijks overzicht — week van {date}",
        "subj_sys_alert":   "Systeemfout — {source}",
        "subj_startup_ok":  "Opstarten — Energy Monitor",
        "subj_startup_err": "Opstarten — Fout ({sources})",
        "banner_oil_alert":   "Daling stookolieprijs",
        "banner_elec_alert":  "Elektriciteitstarief onder drempel",
        "banner_sys_error":   "Systeemfout — Bron: {source}",
        "banner_startup_err": "Opstarten — Fout(en) gedetecteerd",
        "body_oil_alert": (
            "De huidige prijs (<strong>{price} €/L</strong>) is "
            "<strong>{drop:.1f}%</strong> lager dan het 7-daags gemiddelde ({avg} €/L)."
        ),
        "body_elec_alert": (
            "Het dagtarief (<strong>{price:.2f} c€/kWh</strong>) "
            "is gedaald onder uw alarmdrempel van {ceiling:.2f} c€/kWh."
        ),
        "body_sys_error": (
            "Databron <strong>{source}</strong> heeft na 3 pogingen gefaald.<br>"
            "<code style='font-family:monospace;font-size:12px;background:{bg};"
            "padding:2px 4px;border-radius:3px;'>{error}</code>"
        ),
        "body_startup_err": "Bronnen in fout: <strong>{sources}</strong>.",
        "chart_oil_title":        "Stookolie — laatste {months} maand(en) (incl. BTW)",
        "chart_oil_empty":        "Geen stookoliegegevens voor de afgelopen {months} maanden.",
        "chart_oil_legend_below": "< 2.000 L (incl. BTW)",
        "chart_oil_legend_above": "≥ 2.000 L (incl. BTW)",
        "chart_elec_title":       "Elektriciteit TotalEnergies — laatste {months} maand(en)",
        "chart_elec_empty":       "Geen elektriciteitsgegevens voor de afgelopen {months} maanden.",
        "chart_elec_legend_day":     "Dag — Piekuren",
        "chart_elec_legend_night":   "Nacht — Daluren",
        "chart_elec_legend_ceiling": "Drempel: {price:.2f} c€/kWh",
        "chart_fuel_title":        "Brandstoffen — laatste {months} maand(en) (incl. BTW)",
        "chart_fuel_empty":        "Geen brandstofgegevens voor de afgelopen {months} maanden.",
        "chart_fuel_legend_95":    "Benzine 95 E5 (incl. BTW)",
        "chart_fuel_legend_98":    "Benzine 98 E5 (incl. BTW)",
        "chart_fuel_legend_diesel": "Diesel B7 (incl. BTW)",
        "chart_gas_title_months":  "Aardgas — laatste {months} maand(en) (incl. BTW)",
        "chart_gas_title_all":     "Aardgas — volledige historiek (incl. BTW)",
        "chart_gas_empty":         "Geen aardgasgegevens beschikbaar.",
        "chart_gas_legend":        "Aardgas (incl. BTW)",
    },
}


def get_t(lang: str) -> dict:
    """Return the translation dict for the given language code (defaults to 'fr')."""
    return TRANSLATIONS.get(lang.lower(), TRANSLATIONS["fr"])

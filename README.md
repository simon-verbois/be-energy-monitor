# Belgian Energy Monitor

Microservice Python qui surveille les prix de l'énergie en Belgique et envoie des alertes et rapports par email.

## Sources de données

| Énergie | Source | Fréquence |
|---------|--------|-----------|
| Gasoil de chauffage | SPF Économie (PDF) | Quotidien (08h30) |
| Carburants (95/98/B7) | SPF Économie (PDF) | Quotidien (08h30) |
| Électricité (HP/HC) | TotalEnergies (PDF) | Quotidien (08h35) |
| Gaz naturel | TotalEnergies (PDF) | Quotidien (08h35) |

## Fonctionnalités

- Alertes email lors d'une baisse de prix significative (mazout, électricité)
- Rapport quotidien avec graphiques d'évolution
- Résumé hebdomadaire complet
- Historique persisté dans SQLite

## Structure

```
price-fetched/
├── main.py              # Point d'entrée, scheduler APScheduler
├── src/
│   ├── scrapers.py      # Téléchargement et parsing des PDFs
│   ├── database.py      # Modèles SQLAlchemy + helpers
│   ├── visualizer.py    # Génération des graphiques (matplotlib)
│   └── notifier.py      # Envoi des emails (SMTP)
├── data/                # Base de données SQLite (bind mount Docker)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Configuration

Copier `.env.example` en `.env` et remplir les valeurs :

```bash
cp .env.example .env
```

Variables principales :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `SMTP_SERVER` | Adresse du serveur SMTP | *requis* |
| `SMTP_PORT` | Port SMTP | `25` |
| `SMTP_AUTH` | Mode auth : `starttls` ou `none` | `starttls` |
| `ALERT_EMAIL_TO` | Destinataire des alertes | *requis* |
| `OIL_ALERT_THRESHOLD_PERCENT` | Baisse mazout pour alerte (%) | `5` |
| `ELEC_PRICE_CEILING` | Seuil électricité pour alerte (€/kWh) | `0.10` |
| `CHART_MONTHS` | Mois d'historique dans les graphiques | `3` |
| `LOG_LEVEL` | Niveau de log (`INFO` ou `DEBUG`) | `INFO` |

## Lancement

```bash
docker-compose up -d
```

Les données sont persistées dans `./data/energy.db`.

## Développement

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

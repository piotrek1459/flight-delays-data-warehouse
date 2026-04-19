# Flight Delays Data Warehouse

Academic data warehouse project for the **Data Warehouses and Data Mining Systems (DWADMS)** course.  
The project analyses US domestic flight delays and cancellations using a star-schema dimensional model built on PostgreSQL, populated via a Python ETL pipeline, and queried through OLAP SQL analyses.

---

## Project Overview

| Phase | Lab | Topic | Status |
|-------|-----|-------|--------|
| 1 | Lab 1–2 (Sec 1) | Topic selection, dataset description, initial analysis | ✅ Complete |
| 2 | Lab 2 (Sec 2–3) | Operational database model + conceptual model | ✅ Complete |
| 3 | Lab 3 | Logical data warehouse model (star schema) | ✅ Complete |
| 4 | Lab 4 | Physical model + DDL SQL statements | ✅ Complete |
| 5 | Lab 5 | ETL pipeline (Python, psycopg2) | ✅ Complete |
| 6 | Lab 6 | OLAP analysis + SQL queries + visualisations | ✅ Complete |

---

## Datasets

| Dataset | Source | Coverage | Size | Usage |
|---------|--------|----------|------|-------|
| Dataset 3 | Kaggle — *Flight Delays and Cancellations 2015* | Full year 2015, ~5.8M flights, 14 airlines, 322 airports | 565 MB | **Primary source** — provides fact data + all dimension reference tables |
| Dataset 1 | BTS / DOT modern sample | 2019–2023, ~3M flights | 586 MB | **Supplement** — extends temporal coverage for trend analysis |
| Dataset 2 | Historical archive | Multi-decade shuffled records | 11 GB | **Excluded** — non-UTF-8 encoding, no reference tables, no data dictionary |

> **Note:** The `data/` directory is excluded from git (`.gitignore`). Download datasets separately and place them as described in the [Setup](#setup) section.

---

## Data Warehouse Schema

**Star schema** with one central fact table and five dimension tables:

```
                    Dim_Date
                       │
Dim_Cancellation ──────┤
                       │
Dim_Airline ──── Fact_Flight_Operations ──── Dim_Airport (origin)
                       │                          │
                  Dim_Plane               Dim_Airport (destination)
```

| Table | Rows (approx.) | Description |
|-------|---------------|-------------|
| `Fact_Flight_Operations` | ~8.8M | One row per flight — delays, flags, FK references |
| `Dim_Date` | 2,192 | One row per calendar day (2015 + 2019–2023) |
| `Dim_Airline` | 20+ | IATA carrier codes and names |
| `Dim_Airport` | 322 | Airport IATA codes, city, country, coordinates |
| `Dim_Plane` | ~4,800 | Unique tail numbers (aircraft metadata unavailable in source data) |
| `Dim_Cancellation_Reason` | 5 | A=Carrier, B=Weather, C=NAS, D=Security, N=Not Applicable |

ERD diagrams (dbdiagram.io DBML) are available in:
- Operational model: [docs/phase2/phase2.md](docs/phase2/phase2.md)
- Star schema: [docs/phase3/phase3.md](docs/phase3/phase3.md)

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Database | PostgreSQL 14 (Docker) |
| Containerisation | Docker Compose with persistent volume |
| ETL | Python 3.9+, pandas ≥ 2.0, psycopg2-binary ≥ 2.9 |
| Analysis | SQL (Variant B — manual queries) |
| Visualisation | matplotlib ≥ 3.7, seaborn ≥ 0.12 |
| Notebook | Jupyter |

---

## Repository Structure

```
flight-delays-data-warehouse/
├── data/                         # Datasets (gitignored — download separately)
│   ├── dataset1/
│   │   └── flights_sample_3m.csv
│   └── dataset3/
│       ├── flights.csv
│       ├── airlines.csv
│       └── airports.csv
├── docs/
│   ├── phase1/                   # Initial analysis report
│   ├── phase2/                   # Operational DB model + ERD (DBML)
│   ├── phase3/                   # Logical star schema + DBML diagram
│   ├── phase4/                   # Physical model documentation
│   ├── phase5/                   # ETL process documentation
│   ├── phase6/                   # OLAP analysis & SQL queries
│   └── requirements/             # Lab assignment PDFs (Lab 1–6)
├── sql/
│   └── ddl.sql                   # PostgreSQL CREATE TABLE + indexes
├── etl/
│   ├── etl.py                    # Main ETL orchestrator
│   ├── extract.py                # CSV extraction (chunked)
│   ├── transform.py              # Data transformations
│   └── load.py                   # PostgreSQL loaders (COPY FROM STDIN)
├── notebooks/
│   └── analysis.ipynb            # OLAP queries + matplotlib charts
├── docker-compose.yml            # PostgreSQL container with persistent volume
├── requirements.txt              # Python dependencies
└── README.md
```

---

## Setup

### Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or [Rancher Desktop](https://rancherdesktop.io/) (Docker engine must be running)
- Python 3.9 or higher
- ~15 GB free disk space (datasets + PostgreSQL volume)

### Step 1 — Download the datasets

Place files in the following locations (create directories if needed):

```
data/dataset3/flights.csv         (~565 MB)
data/dataset3/airlines.csv        (~4 KB)
data/dataset3/airports.csv        (~24 KB)
data/dataset1/flights_sample_3m.csv  (~586 MB)
```

- **Dataset 3:** [Kaggle — Flight Delays and Cancellations 2015](https://www.kaggle.com/datasets/usdot/flight-delays)
- **Dataset 1:** [BTS Airline On-Time Performance](https://www.transtats.bts.gov/DL_SelectFields.aspx)

### Step 2 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 3 — Start PostgreSQL

```bash
docker compose up -d
```

This starts a PostgreSQL 14 container named `flight_dw_postgres`.  
**On first run**, the schema is created automatically from `sql/ddl.sql` via the Docker entrypoint init script.  
The database is stored in a named Docker volume (`pgdata`) — data **persists across container restarts**.

Verify the database is ready:

```bash
docker compose ps
# Status should be "healthy"
```

### Step 4 — Run the ETL pipeline

```bash
python etl/etl.py
```

The pipeline loads all dimensions and ~8.8M fact rows. Expected runtime: **15–30 minutes** depending on hardware.

Progress is logged to stdout:

```
09:12:03  INFO      Step 1/8: Creating schema from sql/ddl.sql
09:12:04  INFO      Step 2/8: Building Dim_Date for years [2015, 2019, 2020, 2021, 2022, 2023]
09:12:05  INFO      Step 3/8: Loading Dim_Airline from data/dataset3/airlines.csv
...
09:28:41  INFO      ETL finished in 16.6 minutes. Total rows: 5819079 (dataset3) + 2967203 (dataset1) = 8786282
```

### Step 5 — Explore the data

To run queries manually:

```bash
psql -h localhost -U postgres -d flight_dw
```

Default password: `postgres`

### Step 6 — Open the analysis notebook

```bash
jupyter notebook notebooks/analysis.ipynb
```

Run all cells. Charts are also saved as PNG files in `notebooks/`.

---

## Restarting After a Break

The database data is stored in the Docker volume `pgdata`. To resume work:

```bash
docker compose up -d     # restore PostgreSQL — data is already there
jupyter notebook notebooks/analysis.ipynb
```

**No need to re-run the ETL.** The ETL only needs to run once.  
If you need a clean reset (e.g. to reload data after schema changes):

```bash
docker compose down -v   # removes the pgdata volume
docker compose up -d     # fresh container, empty DB
python etl/etl.py        # reload all data
```

---

## Configuration

Default database connection settings (can be overridden with environment variables):

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `flight_dw` | Database name |
| `DB_USER` | `postgres` | Username |
| `DB_PASSWORD` | `postgres` | Password |
| `DATASET3_DIR` | `data/dataset3` | Path to Dataset 3 files |
| `DATASET1_DIR` | `data/dataset1` | Path to Dataset 1 files |
| `CHUNK_SIZE` | `100000` | Rows per processing chunk |

Example override:

```bash
DB_PASSWORD=mysecret CHUNK_SIZE=50000 python etl/etl.py
```

---

## Phase Documentation

| Phase | Document | Contents |
|-------|----------|----------|
| 1 | [docs/phase1/](docs/phase1/) | Analysis report (PDF + DOCX) |
| 2 | [docs/phase2/phase2.md](docs/phase2/phase2.md) | Operational DB model, ERD in dbdiagram.io DBML |
| 3 | [docs/phase3/phase3.md](docs/phase3/phase3.md) | Logical star schema, DBML diagram |
| 4 | [docs/phase4/phase4.md](docs/phase4/phase4.md) | Physical model tables, DDL embedded |
| 5 | [docs/phase5/phase5.md](docs/phase5/phase5.md) | Data quality analysis, ETL design, transformations |
| 6 | [docs/phase6/phase6.md](docs/phase6/phase6.md) | 6 OLAP SQL analyses, expected results, chart descriptions |

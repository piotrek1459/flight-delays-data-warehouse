# Phase 5 – ETL Process

## 1. Analysis of Data Sources

Before loading data into the warehouse, each source dataset was analysed for quality issues. The findings and their resolutions are listed below.

### Dataset 3 — `data/dataset3/` (Primary Source, 2015)

| Issue | Column(s) | Rows Affected | Resolution |
|-------|-----------|---------------|------------|
| Missing departure / arrival delays | `DEPARTURE_DELAY`, `ARRIVAL_DELAY` | ~86,153 (cancelled flights) | Store as `NULL` — expected for cancelled operations |
| Missing tail number | `TAIL_NUMBER` | ~14,721 | Map to `UNKNOWN` sentinel row in `Dim_Plane` |
| All delay breakdown fields empty | `AIR_SYSTEM_DELAY` … `WEATHER_DELAY` | ~4,755,640 (non-delayed) | Store as `0` — absence of delay is not a data defect |
| Cancellation code absent | `CANCELLATION_REASON` | ~5,729,195 (non-cancelled) | Map to sentinel code `N` (Not Applicable) in `Dim_Cancellation_Reason` |
| Times stored as HHMM integer strings | `SCHEDULED_DEPARTURE`, `DEPARTURE_TIME`, `ARRIVAL_TIME`, `SCHEDULED_ARRIVAL` | All rows | Convert to `HH:MM:00` string for PostgreSQL `TIME` columns; handle edge case `2400` → `00:00:00` |
| Date split across three columns | `YEAR`, `MONTH`, `DAY` | All rows | Construct `DATE` and compute `date_key = YEAR * 10000 + MONTH * 100 + DAY` |
| No aircraft metadata | `TAIL_NUMBER` only | All rows | `Dim_Plane` contains only `tail_number`; columns `model`, `manufacturer`, `issue_date` are `NULL` for all loaded rows |

### Dataset 1 — `data/dataset1/` (Supplement, 2019–2023)

| Issue | Column(s) | Rows Affected | Resolution |
|-------|-----------|---------------|------------|
| Different column names | All | All | Normalised to unified internal names before transformation |
| No `TAIL_NUMBER` column | — | All | Set `plane_key` to `UNKNOWN` sentinel for all Dataset 1 rows |
| Airlines not present in `airlines.csv` | `AIRLINE_CODE` | Varies | Scan Dataset 1 before loading fact rows; insert any missing airlines into `Dim_Airline` using the `AIRLINE` full-name column |
| Flight date as `YYYY-MM-DD` string | `FL_DATE` | All | Parse directly; no HHMM conversion needed for date |
| Delay breakdowns named differently | `DELAY_DUE_CARRIER` vs `AIRLINE_DELAY` | All | Unified by column rename in `normalize_dataset1_chunk()` |

### Dataset 2 — **Excluded**

Dataset 2 (`data/dataset2/airline.csv.shuffle`, 11 GB) was evaluated and excluded from the ETL process for the following reasons:

1. **File size:** 11 GB exceeds practical processing limits for a local academic setup without a distributed computing framework.
2. **Encoding:** Non-UTF-8 (latin-1) encoding creates normalisation complexity.
3. **Missing reference data:** No accompanying airport or airline lookup tables are provided, making it impossible to enrich the data with geographic or carrier metadata required by the dimensional model.
4. **No data dictionary:** Column semantics are partially ambiguous without documentation.
5. **Sufficient coverage:** Datasets 1 and 3 together cover ~8.8M flight records spanning 2015 and 2019–2023, providing adequate volume and temporal range for all planned analyses.

Only `data/dataset2/carriers.csv` (1,492 airline codes) is retained as a potential future supplement for extending `Dim_Airline`.

---

## 2. ETL Approach

**Chosen approach:** Self-developed Python ETL (Approach 2 from the lab specification)

**Rationale:**
- Full control over transformation logic, NULL handling, and chunk-based memory management
- Python libraries (`pandas`, `psycopg2`) are well-suited to the CSV + PostgreSQL stack
- No additional licensed software required
- Easy to inspect, debug, and extend

**No data staging area is used.** The source CSV files act as the staging layer directly. Since the datasets are static snapshots (not live feeds), there is no need for an intermediate staging database. An ELT approach (Approach 3) was considered but rejected because it would require loading ~12 GB of raw data into PostgreSQL before transformations, which is less efficient than the chunked Python approach.

**Technology stack:**

| Component | Tool | Version |
|-----------|------|---------|
| Extraction | `pandas.read_csv` with chunked iteration | pandas ≥ 2.0 |
| Transformation | Python, pandas in-memory | Python 3.9+ |
| Loading | `psycopg2` `execute_values` + `COPY FROM STDIN` | psycopg2-binary ≥ 2.9 |
| Database | PostgreSQL 14 (Docker container) | PostgreSQL 14 |
| Orchestration | `etl/etl.py` | — |

---

## 3. Data Staging Area

No staging area is used. The raw CSV files serve as the source directly. The ETL reads data in memory-efficient chunks of 100,000 rows without first materialising the full dataset in a database.

---

## 4. Transformations

### 4.1 Dim_Date Generation

`Dim_Date` is **generated programmatically** (not read from any source file). For each year in `[2015, 2019, 2020, 2021, 2022, 2023]`, all calendar days are enumerated and the following attributes are computed:

| Attribute | Derivation |
|-----------|-----------|
| `date_key` | `YEAR * 10000 + MONTH * 100 + DAY` (e.g. `20150115`) |
| `full_date` | Python `date` object |
| `year` | `date.year` |
| `month` | `date.month` |
| `month_name` | Lookup table (e.g. `1 → 'January'`) |
| `quarter` | `(month - 1) // 3 + 1` |
| `day_of_month` | `date.day` |
| `day_of_week` | `date.isoweekday()` — 1=Monday, 7=Sunday |
| `day_name` | Lookup table (e.g. `3 → 'Wednesday'`) |
| `is_weekend` | `day_of_week >= 6` |
| `season` | Month → season mapping: Dec/Jan/Feb=Winter, Mar/Apr/May=Spring, Jun/Jul/Aug=Summer, Sep/Oct/Nov=Autumn |

### 4.2 Dim_Airline

Source: `data/dataset3/airlines.csv` (14 rows), supplemented by airline codes found in Dataset 1.

Transformations applied:
- Strip whitespace from `IATA_CODE` and `AIRLINE`
- Rename to internal schema column names
- Set `country_of_origin = 'USA'` (all carriers in the dataset are US domestic)
- Deduplicate by `iata_code`

### 4.3 Dim_Airport

Source: `data/dataset3/airports.csv` (322 rows).

Transformations applied:
- Strip whitespace from all string columns
- Truncate `airport_name` to 100 characters (maximum observed: 78)
- Convert `latitude` and `longitude` to `DECIMAL(9,5)` (coerce errors to `NULL`)

### 4.4 Dim_Plane

Source: `TAIL_NUMBER` column scanned from `data/dataset3/flights.csv` in chunks.

Transformations applied:
- Extract all unique non-null tail numbers (~4,800 distinct values)
- Insert `UNKNOWN` sentinel as the first row (used for rows with no tail number)
- All columns except `tail_number` are set to `NULL` / `'Unknown'` — the dataset provides no aircraft metadata

### 4.5 Dim_Cancellation_Reason

Seeded directly in the DDL with five static values. No CSV extraction needed.

### 4.6 Fact Table — Per-Chunk Transformations

Each chunk of 100,000 rows goes through the following steps:

1. **Date key construction:** `YEAR * 10000 + MONTH * 100 + DAY` (Dataset 3) or parse `FL_DATE` string (Dataset 1)
2. **Dimension key lookups:** in-memory dictionaries resolve IATA codes to surrogate keys
3. **NULL handling:**
   - Missing tail number → UNKNOWN plane_key
   - Missing cancellation code → 'N' cancel_reason_key
   - Cancelled flights → `dep_delay`, `arr_delay` = NULL; delay breakdowns = NULL
   - Non-delayed non-cancelled flights → delay breakdowns = 0
4. **HHMM time parsing:** `"0005"` → `"00:05:00"`, edge case `"2400"` → `"00:00:00"`
5. **Type casting:** all delay and distance values cast to `int` (dropping float precision that exceeds SMALLINT range only for outlier rows, which are skipped)
6. **Skipped rows:** any row where origin or destination airport IATA code cannot be resolved in `Dim_Airport` is skipped and counted in the skip log

---

## 5. Loading Phase

### Dimension Loading

Dimension tables are loaded using `psycopg2.extras.execute_values`, which batches multiple `INSERT` statements into one round-trip. `ON CONFLICT DO NOTHING` ensures idempotency — the ETL can be safely re-run without duplicating dimension data.

Loading order (no cross-dimension FK dependencies):
1. `Dim_Date` (2,192 rows — all days for 6 years)
2. `Dim_Airline` (14+ rows)
3. `Dim_Airport` (322 rows)
4. `Dim_Plane` (~4,800+ rows)
5. `Dim_Cancellation_Reason` (seeded by DDL, no ETL step needed)

### Fact Table Loading

The fact table is loaded using PostgreSQL's `COPY FROM STDIN` protocol via `psycopg2`'s `copy_expert` method. Each chunk is serialised to a tab-separated in-memory buffer (`io.StringIO`) with `\N` representing SQL `NULL`. A transaction is committed per chunk.

**Performance comparison:**

| Method | ~5.8M rows estimated time |
|--------|--------------------------|
| `execute_values` (batched INSERT) | 2–4 hours |
| `COPY FROM STDIN` | 10–20 minutes |

**Split operations required:**

The source schemas differ from the warehouse schema in the following ways, requiring split/join operations during loading:

| Transformation | Description |
|----------------|-------------|
| Airport used as two FK roles | A single `Dim_Airport` row is referenced twice from the fact table — once as `origin_airport_key` and once as `destination_airport_key` |
| Date split from row | `YEAR`, `MONTH`, `DAY` are stored separately in Dataset 3; combined to `DATE` and `date_key` during loading |
| Airline dimension join | Source files store only IATA code; surrogate key looked up from in-memory dict |
| Plane dimension join | Tail numbers mapped to surrogate keys via in-memory dict; missing = UNKNOWN |
| Cancellation reason join | Single-character code mapped to surrogate key |
| Source dataset label | Added as `source_dataset = 'dataset3'` or `'dataset1'` — not present in source files |

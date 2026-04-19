"""
etl.py — Main ETL orchestrator for the Flight Delays Data Warehouse.

Pipeline order:
  1. Create schema (DDL)
  2. Load Dim_Date (generated, not read from CSV)
  3. Load Dim_Airline (from airlines.csv)
  4. Load Dim_Airport (from airports.csv)
  5. Load Dim_Plane (scan TAIL_NUMBER from flights.csv)
  6. Build in-memory lookup dicts from loaded dimensions
  7. Load Fact — dataset3 (2015, ~5.8M rows)
  8. Load Fact — dataset1 (2019–2023, ~3M rows)

Usage:
    python etl.py

Configuration can be overridden via environment variables:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    DATASET3_DIR, DATASET1_DIR, CHUNK_SIZE
"""
import logging
import os
import sys
import time
from pathlib import Path

# Allow imports from the etl/ directory regardless of working dir
sys.path.insert(0, str(Path(__file__).parent))

from extract import (
    extract_airlines,
    extract_airports,
    extract_dataset3_chunked,
    extract_dataset1_chunked,
    extract_unique_tail_numbers,
)
from transform import (
    build_dim_date,
    transform_dim_airline,
    transform_dim_airport,
    build_dim_plane,
    normalize_dataset3_chunk,
    normalize_dataset1_chunk,
    transform_fact_chunk,
)
from load import (
    get_connection,
    create_schema,
    load_dim_date,
    load_dim_airline,
    load_dim_airport,
    load_dim_plane,
    load_fact_chunk,
    build_dimension_lookup_dicts,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — override with environment variables if needed
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent  # repo root

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME",     "flight_dw"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

DATASET3_DIR = Path(os.getenv("DATASET3_DIR", ROOT / "data" / "dataset3"))
DATASET1_DIR = Path(os.getenv("DATASET1_DIR", ROOT / "data" / "dataset1"))
DDL_PATH     = ROOT / "sql" / "ddl.sql"
CHUNK_SIZE   = int(os.getenv("CHUNK_SIZE", "100000"))

# Years present across both datasets (used for Dim_Date generation)
YEARS = [2015, 2019, 2020, 2021, 2022, 2023]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_postgres(config: dict, retries: int = 30, delay: float = 2.0):
    """Retry connection until PostgreSQL is ready (useful after docker compose up)."""
    import psycopg2
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(connect_timeout=3, **config)
            conn.close()
            log.info("PostgreSQL is ready.")
            return
        except psycopg2.OperationalError:
            log.info("Waiting for PostgreSQL... attempt %d/%d", attempt, retries)
            time.sleep(delay)
    raise RuntimeError("PostgreSQL did not become available in time.")


# ---------------------------------------------------------------------------
# Main ETL
# ---------------------------------------------------------------------------

def run_etl():
    t0 = time.time()

    _wait_for_postgres(DB_CONFIG)
    conn = get_connection(DB_CONFIG)

    # ------------------------------------------------------------------
    # Step 1: Schema
    # ------------------------------------------------------------------
    log.info("Step 1/8: Creating schema from %s", DDL_PATH)
    create_schema(conn, str(DDL_PATH))

    # ------------------------------------------------------------------
    # Step 2: Dim_Date
    # ------------------------------------------------------------------
    log.info("Step 2/8: Building Dim_Date for years %s", YEARS)
    dim_date_df = build_dim_date(YEARS)
    load_dim_date(conn, dim_date_df)

    # ------------------------------------------------------------------
    # Step 3: Dim_Airline
    # ------------------------------------------------------------------
    log.info("Step 3/8: Loading Dim_Airline from %s", DATASET3_DIR / "airlines.csv")
    airlines_raw = extract_airlines(str(DATASET3_DIR / "airlines.csv"))
    dim_airline_df = transform_dim_airline(airlines_raw)
    load_dim_airline(conn, dim_airline_df)

    # ------------------------------------------------------------------
    # Step 4: Dim_Airport
    # ------------------------------------------------------------------
    log.info("Step 4/8: Loading Dim_Airport from %s", DATASET3_DIR / "airports.csv")
    airports_raw = extract_airports(str(DATASET3_DIR / "airports.csv"))
    dim_airport_df = transform_dim_airport(airports_raw)
    load_dim_airport(conn, dim_airport_df)

    # Also enrich with any airports that appear only in dataset1
    # (dataset3 airports.csv covers 322; dataset1 uses the same IATA universe)

    # ------------------------------------------------------------------
    # Step 5: Dim_Plane (scan dataset3 for unique tail numbers)
    # ------------------------------------------------------------------
    flights3_path = str(DATASET3_DIR / "flights.csv")
    log.info("Step 5/8: Scanning %s for unique tail numbers...", flights3_path)
    tails = extract_unique_tail_numbers(flights3_path, chunk_size=CHUNK_SIZE)
    log.info("Found %d unique tail numbers", len(tails))
    dim_plane_df = build_dim_plane(tails)
    load_dim_plane(conn, dim_plane_df)

    # ------------------------------------------------------------------
    # Step 6: Build lookup dicts (in-memory, fast key resolution)
    # ------------------------------------------------------------------
    log.info("Step 6/8: Building dimension lookup dicts...")
    lookups = build_dimension_lookup_dicts(conn)

    # ------------------------------------------------------------------
    # Step 7: Fact — Dataset 3 (2015, ~5.8M rows)
    # ------------------------------------------------------------------
    log.info("Step 7/8: Loading Fact from Dataset 3 (%s)...", flights3_path)
    total3_loaded, total3_skipped = 0, 0

    for chunk_num, raw_chunk in enumerate(
        extract_dataset3_chunked(flights3_path, CHUNK_SIZE), start=1
    ):
        norm = normalize_dataset3_chunk(raw_chunk)
        fact_rows, skipped = transform_fact_chunk(
            norm, lookups, source_label="dataset3", is_dataset3=True
        )
        load_fact_chunk(conn, fact_rows)
        total3_loaded += len(fact_rows)
        total3_skipped += skipped
        if chunk_num % 10 == 0:
            log.info(
                "Dataset3 chunk %d: cumulative loaded=%d skipped=%d",
                chunk_num, total3_loaded, total3_skipped,
            )

    log.info(
        "Dataset3 complete: loaded=%d, skipped=%d",
        total3_loaded, total3_skipped,
    )

    # ------------------------------------------------------------------
    # Step 8: Fact — Dataset 1 (2019–2023, ~3M rows)
    # ------------------------------------------------------------------
    flights1_path = str(DATASET1_DIR / "flights_sample_3m.csv")
    log.info("Step 8/8: Loading Fact from Dataset 1 (%s)...", flights1_path)

    # Dataset1 may contain airlines not in dataset3's airlines.csv.
    # Build a supplementary airline set from the AIRLINE_CODE column and
    # insert any missing airlines using the AIRLINE (full name) column.
    _ensure_dataset1_airlines(conn, flights1_path, lookups)
    lookups = build_dimension_lookup_dicts(conn)  # refresh after potential inserts

    total1_loaded, total1_skipped = 0, 0

    for chunk_num, raw_chunk in enumerate(
        extract_dataset1_chunked(flights1_path, CHUNK_SIZE), start=1
    ):
        norm = normalize_dataset1_chunk(raw_chunk)
        fact_rows, skipped = transform_fact_chunk(
            norm, lookups, source_label="dataset1", is_dataset3=False
        )
        load_fact_chunk(conn, fact_rows)
        total1_loaded += len(fact_rows)
        total1_skipped += skipped
        if chunk_num % 10 == 0:
            log.info(
                "Dataset1 chunk %d: cumulative loaded=%d skipped=%d",
                chunk_num, total1_loaded, total1_skipped,
            )

    log.info(
        "Dataset1 complete: loaded=%d, skipped=%d",
        total1_loaded, total1_skipped,
    )

    conn.close()
    elapsed = time.time() - t0
    log.info(
        "ETL finished in %.1f minutes. Total rows: %d (dataset3) + %d (dataset1) = %d",
        elapsed / 60,
        total3_loaded, total1_loaded, total3_loaded + total1_loaded,
    )


def _ensure_dataset1_airlines(conn, flights1_path: str, lookups: dict) -> None:
    """
    Scan dataset1 for any airline IATA codes not yet in Dim_Airline,
    and insert them using the full airline name from the AIRLINE column.
    """
    import pandas as pd
    import psycopg2.extras

    known = set(lookups["airline"].keys())
    new_airlines: dict[str, str] = {}  # iata_code → full_name

    for chunk in pd.read_csv(
        flights1_path,
        usecols=["AIRLINE_CODE", "AIRLINE"],
        dtype={"AIRLINE_CODE": str, "AIRLINE": str},
        keep_default_na=False,
        chunksize=100_000,
    ):
        chunk = chunk.dropna(subset=["AIRLINE_CODE"])
        for _, row in chunk.drop_duplicates("AIRLINE_CODE").iterrows():
            code = str(row["AIRLINE_CODE"]).strip()
            name = str(row["AIRLINE"]).strip()
            if code and code not in known and code not in new_airlines:
                new_airlines[code] = name

    if not new_airlines:
        return

    rows = [
        (None, code, code, name[:50], "USA")
        for code, name in new_airlines.items()
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO Dim_Airline
               (airline_id, iata_code, airline_code, airline_name, country_of_origin)
               VALUES %s
               ON CONFLICT (iata_code) DO NOTHING""",
            rows,
        )
    conn.commit()
    log.info("Inserted %d new airlines from dataset1", len(new_airlines))


if __name__ == "__main__":
    run_etl()

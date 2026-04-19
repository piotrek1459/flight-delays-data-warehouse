"""
load.py — PostgreSQL loading functions for the Flight Delays ETL pipeline.

Uses psycopg2 execute_values for small dimension tables and
COPY FROM STDIN (via StringIO) for the large fact table.
"""
import logging
from io import StringIO
from typing import Any

import pandas as pd
import psycopg2
import psycopg2.extras

log = logging.getLogger(__name__)


def get_connection(config: dict) -> psycopg2.extensions.connection:
    """Return an open psycopg2 connection from a config dict."""
    conn = psycopg2.connect(**config)
    conn.autocommit = False
    return conn


def create_schema(conn: psycopg2.extensions.connection, ddl_path: str) -> None:
    """Execute the DDL file to (re-)create all tables and indexes."""
    with open(ddl_path, "r") as f:
        ddl = f.read()
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    log.info("Schema created from %s", ddl_path)


# ---------------------------------------------------------------------------
# Dimension loaders
# ---------------------------------------------------------------------------

def load_dim_date(conn: psycopg2.extensions.connection, df: pd.DataFrame) -> None:
    rows = df[
        ["date_key", "full_date", "year", "month", "month_name",
         "quarter", "day_of_month", "day_of_week", "day_name",
         "is_weekend", "season"]
    ].itertuples(index=False, name=None)
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO Dim_Date
               (date_key, full_date, year, month, month_name,
                quarter, day_of_month, day_of_week, day_name,
                is_weekend, season)
               VALUES %s
               ON CONFLICT (date_key) DO NOTHING""",
            list(rows),
        )
    conn.commit()
    log.info("Loaded %d rows into Dim_Date", len(df))


def load_dim_airline(conn: psycopg2.extensions.connection, df: pd.DataFrame) -> None:
    rows = df[
        ["airline_id", "iata_code", "airline_code", "airline_name", "country_of_origin"]
    ].itertuples(index=False, name=None)
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO Dim_Airline
               (airline_id, iata_code, airline_code, airline_name, country_of_origin)
               VALUES %s
               ON CONFLICT (iata_code) DO NOTHING""",
            list(rows),
        )
    conn.commit()
    log.info("Loaded %d rows into Dim_Airline", len(df))


def load_dim_airport(conn: psycopg2.extensions.connection, df: pd.DataFrame) -> None:
    rows = df[
        ["airport_id", "iata_code", "airport_name", "city", "country",
         "latitude", "longitude"]
    ].itertuples(index=False, name=None)
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO Dim_Airport
               (airport_id, iata_code, airport_name, city, country, latitude, longitude)
               VALUES %s
               ON CONFLICT (iata_code) DO NOTHING""",
            list(rows),
        )
    conn.commit()
    log.info("Loaded %d rows into Dim_Airport", len(df))


def load_dim_plane(conn: psycopg2.extensions.connection, df: pd.DataFrame) -> None:
    rows = df[
        ["plane_id", "tail_number", "model", "manufacturer", "issue_date", "status"]
    ].itertuples(index=False, name=None)
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO Dim_Plane
               (plane_id, tail_number, model, manufacturer, issue_date, status)
               VALUES %s
               ON CONFLICT (tail_number) DO NOTHING""",
            list(rows),
        )
    conn.commit()
    log.info("Loaded %d rows into Dim_Plane", len(df))


# ---------------------------------------------------------------------------
# Fact table bulk loader
# ---------------------------------------------------------------------------

_FACT_COPY_SQL = """COPY Fact_Flight_Operations (
    date_key, airline_key, origin_airport_key, destination_airport_key,
    plane_key, cancel_reason_key, flight_number, source_dataset,
    departure_delay_min, arrival_delay_min,
    carrier_delay_min, weather_delay_min, nas_delay_min,
    security_delay_min, late_aircraft_delay_min,
    taxi_out_min, taxi_in_min, air_time_min, distance_miles,
    flight_count, cancelled_flag, diverted_flag
) FROM STDIN WITH (FORMAT TEXT, NULL '\\N', DELIMITER '\\t')"""


def _row_to_tsv(row: tuple) -> str:
    """Serialise a fact row tuple to a TSV line, using \\N for None."""
    parts = []
    for v in row:
        if v is None:
            parts.append("\\N")
        elif isinstance(v, bool):
            parts.append("t" if v else "f")
        else:
            parts.append(str(v))
    return "\t".join(parts)


def load_fact_chunk(
    conn: psycopg2.extensions.connection, rows: list[tuple]
) -> None:
    """Bulk-load a list of fact tuples via COPY FROM STDIN."""
    if not rows:
        return
    buffer = StringIO()
    for row in rows:
        buffer.write(_row_to_tsv(row) + "\n")
    buffer.seek(0)
    with conn.cursor() as cur:
        cur.copy_expert(_FACT_COPY_SQL, buffer)
    conn.commit()


# ---------------------------------------------------------------------------
# Lookup dict builder (called after dimensions are loaded)
# ---------------------------------------------------------------------------

def build_dimension_lookup_dicts(
    conn: psycopg2.extensions.connection,
) -> dict[str, Any]:
    """
    Query all dimension PKs and business keys from the DB.
    Returns a nested dict used by transform_fact_chunk for fast lookups.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT iata_code, airline_key FROM Dim_Airline")
        airline = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute("SELECT iata_code, airport_key FROM Dim_Airport")
        airport = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute("SELECT tail_number, plane_key FROM Dim_Plane")
        plane = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute("SELECT cancellation_code, cancel_reason_key FROM Dim_Cancellation_Reason")
        cancel_reason = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute("SELECT date_key FROM Dim_Date")
        date_keys = {row[0] for row in cur.fetchall()}

    log.info(
        "Lookups built: %d airlines, %d airports, %d planes, %d cancel reasons, %d dates",
        len(airline), len(airport), len(plane), len(cancel_reason), len(date_keys),
    )
    return {
        "airline":       airline,
        "airport":       airport,
        "plane":         plane,
        "cancel_reason": cancel_reason,
        "date":          date_keys,
    }

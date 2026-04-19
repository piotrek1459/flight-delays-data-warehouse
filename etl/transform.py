"""
transform.py — Transformation functions for the Flight Delays ETL pipeline.

Builds dimension DataFrames and transforms raw flight chunks into
fact table rows ready for bulk loading into PostgreSQL.
"""
import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Season lookup: month number → season name
# ---------------------------------------------------------------------------
_SEASON_MAP = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Autumn", 10: "Autumn", 11: "Autumn",
}

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_DAY_NAMES = [
    "", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


# ---------------------------------------------------------------------------
# Dim_Date
# ---------------------------------------------------------------------------

def build_dim_date(years: list[int]) -> pd.DataFrame:
    """
    Generate one row per calendar day for each year in *years*.
    Returns a DataFrame matching the Dim_Date schema.
    """
    rows = []
    for year in years:
        current = date(year, 1, 1)
        end = date(year, 12, 31)
        while current <= end:
            m = current.month
            dow = current.isoweekday()  # 1=Mon, 7=Sun
            rows.append({
                "date_key":     int(current.strftime("%Y%m%d")),
                "full_date":    current,
                "year":         current.year,
                "month":        m,
                "month_name":   _MONTH_NAMES[m],
                "quarter":      (m - 1) // 3 + 1,
                "day_of_month": current.day,
                "day_of_week":  dow,
                "day_name":     _DAY_NAMES[dow],
                "is_weekend":   dow >= 6,
                "season":       _SEASON_MAP[m],
            })
            current += timedelta(days=1)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Dim_Airline
# ---------------------------------------------------------------------------

def transform_dim_airline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: DataFrame with columns IATA_CODE, AIRLINE (from airlines.csv).
    Output: DataFrame matching Dim_Airline schema (without airline_key — SERIAL).
    """
    result = pd.DataFrame({
        "airline_id":       None,
        "iata_code":        df["IATA_CODE"].str.strip(),
        "airline_code":     df["IATA_CODE"].str.strip(),
        "airline_name":     df["AIRLINE"].str.strip(),
        "country_of_origin": "USA",
    })
    return result.drop_duplicates(subset=["iata_code"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Dim_Airport
# ---------------------------------------------------------------------------

def transform_dim_airport(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: DataFrame from airports.csv.
    Output: DataFrame matching Dim_Airport schema.
    """
    result = pd.DataFrame({
        "airport_id":   None,
        "iata_code":    df["IATA_CODE"].str.strip(),
        "airport_name": df["AIRPORT"].str.strip().str[:100],
        "city":         df["CITY"].str.strip(),
        "country":      df["COUNTRY"].str.strip(),
        "latitude":     pd.to_numeric(df["LATITUDE"], errors="coerce"),
        "longitude":    pd.to_numeric(df["LONGITUDE"], errors="coerce"),
    })
    return result.drop_duplicates(subset=["iata_code"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Dim_Plane
# ---------------------------------------------------------------------------

def build_dim_plane(tail_numbers: set) -> pd.DataFrame:
    """
    Build Dim_Plane from a set of unique tail numbers.
    All metadata columns are NULL — dataset provides tail numbers only.
    An 'UNKNOWN' sentinel is always included for flights with no tail number.
    """
    tails = sorted(tail_numbers - {"UNKNOWN", ""})
    tails.insert(0, "UNKNOWN")
    return pd.DataFrame({
        "plane_id":     None,
        "tail_number":  tails,
        "model":        None,
        "manufacturer": None,
        "issue_date":   None,
        "status":       "Unknown",
    })


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------

def parse_hhmm(value) -> Optional[str]:
    """
    Convert an HHMM value (int, float, or string) to 'HH:MM:00'.
    Returns None for missing values.
    Edge case: '2400' is treated as '00:00:00' (midnight).
    """
    if value is None or value != value:  # NaN / None check
        return None
    s = str(value).strip().split(".")[0]  # strip float decimals
    if not s or s in ("", "nan", "NA"):
        return None
    s = s.zfill(4)
    if s == "2400":
        return "00:00:00"
    hour, minute = int(s[:2]), int(s[2:])
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}:00"


def _to_int_or_none(value) -> Optional[int]:
    """Convert float/string to int, returning None for NaN."""
    if value is None or value != value:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Dataset normalisation — unify column names before fact transformation
# ---------------------------------------------------------------------------

def normalize_dataset3_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Rename dataset3 columns to unified internal names."""
    return chunk.rename(columns={
        "AIRLINE":              "airline_iata",
        "FLIGHT_NUMBER":        "flight_number",
        "TAIL_NUMBER":          "tail_number",
        "ORIGIN_AIRPORT":       "origin_iata",
        "DESTINATION_AIRPORT":  "dest_iata",
        "SCHEDULED_DEPARTURE":  "sched_dep",
        "DEPARTURE_TIME":       "act_dep",
        "DEPARTURE_DELAY":      "dep_delay",
        "TAXI_OUT":             "taxi_out",
        "TAXI_IN":              "taxi_in",
        "SCHEDULED_ARRIVAL":    "sched_arr",
        "ARRIVAL_TIME":         "act_arr",
        "ARRIVAL_DELAY":        "arr_delay",
        "AIR_TIME":             "air_time",
        "DISTANCE":             "distance",
        "CANCELLED":            "cancelled",
        "DIVERTED":             "diverted",
        "CANCELLATION_REASON":  "cancel_code",
        "AIR_SYSTEM_DELAY":     "nas_delay",
        "SECURITY_DELAY":       "security_delay",
        "AIRLINE_DELAY":        "carrier_delay",
        "LATE_AIRCRAFT_DELAY":  "late_aircraft_delay",
        "WEATHER_DELAY":        "weather_delay",
    })


def normalize_dataset1_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Rename dataset1 columns to unified internal names."""
    renamed = chunk.rename(columns={
        "AIRLINE_CODE":          "airline_iata",
        "FL_NUMBER":             "flight_number",
        "ORIGIN":                "origin_iata",
        "DEST":                  "dest_iata",
        "CRS_DEP_TIME":          "sched_dep",
        "DEP_TIME":              "act_dep",
        "DEP_DELAY":             "dep_delay",
        "TAXI_OUT":              "taxi_out",
        "TAXI_IN":               "taxi_in",
        "CRS_ARR_TIME":          "sched_arr",
        "ARR_TIME":              "act_arr",
        "ARR_DELAY":             "arr_delay",
        "AIR_TIME":              "air_time",
        "DISTANCE":              "distance",
        "CANCELLED":             "cancelled",
        "DIVERTED":              "diverted",
        "CANCELLATION_CODE":     "cancel_code",
        "DELAY_DUE_CARRIER":     "carrier_delay",
        "DELAY_DUE_WEATHER":     "weather_delay",
        "DELAY_DUE_NAS":         "nas_delay",
        "DELAY_DUE_SECURITY":    "security_delay",
        "DELAY_DUE_LATE_AIRCRAFT": "late_aircraft_delay",
    })
    # Dataset1 has no TAIL_NUMBER
    renamed["tail_number"] = None
    # Build flight_date from FL_DATE (already 'YYYY-MM-DD')
    renamed["flight_date_str"] = renamed["FL_DATE"]
    return renamed


# ---------------------------------------------------------------------------
# Fact transformation
# ---------------------------------------------------------------------------

def transform_fact_chunk(
    chunk: pd.DataFrame,
    lookups: dict,
    source_label: str,
    is_dataset3: bool = True,
) -> tuple[list[tuple], int]:
    """
    Transform a normalised chunk into a list of tuples for COPY FROM STDIN.

    Returns (rows, skipped_count).
    A row is skipped if origin or destination airport cannot be resolved.

    Tuple column order matches the COPY statement in load.py:
    (date_key, airline_key, origin_airport_key, destination_airport_key,
     plane_key, cancel_reason_key, flight_number, source_dataset,
     departure_delay_min, arrival_delay_min,
     carrier_delay_min, weather_delay_min, nas_delay_min,
     security_delay_min, late_aircraft_delay_min,
     taxi_out_min, taxi_in_min, air_time_min, distance_miles,
     flight_count, cancelled_flag, diverted_flag)
    """
    airline_lookup   = lookups["airline"]
    airport_lookup   = lookups["airport"]
    plane_lookup     = lookups["plane"]
    cancel_lookup    = lookups["cancel_reason"]

    rows = []
    skipped = 0

    for _, row in chunk.iterrows():
        # --- Build flight date -----------------------------------------------
        if is_dataset3:
            try:
                y = int(row["YEAR"])
                m = int(row["MONTH"])
                d = int(row["DAY"])
                date_key = y * 10000 + m * 100 + d
            except (ValueError, TypeError):
                skipped += 1
                continue
        else:
            try:
                parts = str(row.get("flight_date_str", "")).split("-")
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                date_key = y * 10000 + m * 100 + d
            except (ValueError, TypeError, IndexError):
                skipped += 1
                continue

        if date_key not in lookups["date"]:
            skipped += 1
            continue

        # --- Airline ---------------------------------------------------------
        airline_iata = str(row.get("airline_iata", "")).strip()
        airline_key = airline_lookup.get(airline_iata)
        if airline_key is None:
            skipped += 1
            continue

        # --- Airports --------------------------------------------------------
        origin_iata = str(row.get("origin_iata", "")).strip()
        dest_iata   = str(row.get("dest_iata", "")).strip()

        origin_key = airport_lookup.get(origin_iata)
        dest_key   = airport_lookup.get(dest_iata)

        if origin_key is None or dest_key is None:
            skipped += 1
            continue

        # --- Plane -----------------------------------------------------------
        tail = str(row.get("tail_number", "")).strip()
        if not tail or tail in ("nan", "None", ""):
            plane_key = plane_lookup.get("UNKNOWN")
        else:
            plane_key = plane_lookup.get(tail, plane_lookup.get("UNKNOWN"))

        # --- Cancellation reason ---------------------------------------------
        cancelled = int(float(row.get("cancelled", 0) or 0))
        cancel_code = str(row.get("cancel_code", "")).strip()
        if cancelled and cancel_code in cancel_lookup:
            cancel_reason_key = cancel_lookup[cancel_code]
        else:
            cancel_reason_key = cancel_lookup.get("N")

        # --- Flight number ---------------------------------------------------
        fn = _to_int_or_none(row.get("flight_number"))
        flight_number = str(fn) if fn is not None else "0"

        # --- Delays ----------------------------------------------------------
        dep_delay   = _to_int_or_none(row.get("dep_delay"))
        arr_delay   = _to_int_or_none(row.get("arr_delay"))
        carrier_d   = _to_int_or_none(row.get("carrier_delay")) or 0
        weather_d   = _to_int_or_none(row.get("weather_delay")) or 0
        nas_d       = _to_int_or_none(row.get("nas_delay")) or 0
        security_d  = _to_int_or_none(row.get("security_delay")) or 0
        late_d      = _to_int_or_none(row.get("late_aircraft_delay")) or 0
        taxi_out    = _to_int_or_none(row.get("taxi_out"))
        taxi_in     = _to_int_or_none(row.get("taxi_in"))
        air_time    = _to_int_or_none(row.get("air_time"))
        distance    = _to_int_or_none(row.get("distance"))

        diverted = int(float(row.get("diverted", 0) or 0))

        rows.append((
            date_key,
            airline_key,
            origin_key,
            dest_key,
            plane_key,
            cancel_reason_key,
            flight_number,
            source_label,
            dep_delay,
            arr_delay,
            carrier_d,
            weather_d,
            nas_d,
            security_d,
            late_d,
            taxi_out,
            taxi_in,
            air_time,
            distance,
            1,               # flight_count
            bool(cancelled),
            bool(diverted),
        ))

    return rows, skipped

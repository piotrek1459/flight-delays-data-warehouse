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
    if value is None or pd.isna(value):
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
    """Convert float/string to int, returning None for NaN/NA."""
    if value is None or pd.isna(value):
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

def _int_col(series: pd.Series) -> pd.Series:
    """Convert a pandas Series to nullable Int64, coercing errors to pd.NA."""
    return pd.to_numeric(series, errors="coerce").astype("Int64")


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
    df = chunk.copy()

    # --- Build date_key -------------------------------------------------------
    if is_dataset3:
        y = _int_col(df["YEAR"])
        m = _int_col(df["MONTH"])
        d = _int_col(df["DAY"])
        df["date_key"] = y * 10000 + m * 100 + d
    else:
        def _parse_date(s):
            try:
                parts = str(s).split("-")
                return int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
            except Exception:
                return pd.NA
        df["date_key"] = df["flight_date_str"].apply(_parse_date).astype("Int64")

    valid_dates = set(lookups["date"])
    df = df[df["date_key"].notna() & df["date_key"].isin(valid_dates)]

    # --- Airline lookup -------------------------------------------------------
    df["airline_iata"] = df["airline_iata"].astype(str).str.strip()
    df["airline_key"] = df["airline_iata"].map(lookups["airline"])
    df = df[df["airline_key"].notna()]

    # --- Airport lookups (role-playing) ---------------------------------------
    df["origin_iata"] = df["origin_iata"].astype(str).str.strip()
    df["dest_iata"]   = df["dest_iata"].astype(str).str.strip()
    df["origin_key"]  = df["origin_iata"].map(lookups["airport"])
    df["dest_key"]    = df["dest_iata"].map(lookups["airport"])
    df = df[df["origin_key"].notna() & df["dest_key"].notna()]

    if df.empty:
        return [], len(chunk) - len(df)

    skipped = len(chunk) - len(df)

    # --- Plane lookup ---------------------------------------------------------
    tail_col = df["tail_number"].astype(str).str.strip()
    tail_col = tail_col.where(~tail_col.isin(["nan", "None", ""]), "UNKNOWN")
    unknown_key = lookups["plane"].get("UNKNOWN")
    df["plane_key"] = tail_col.map(lookups["plane"]).fillna(unknown_key)

    # --- Cancellation reason --------------------------------------------------
    cancelled = _int_col(df["cancelled"]).fillna(0)
    cancel_code = df["cancel_code"].astype(str).str.strip()
    n_key = lookups["cancel_reason"].get("N")
    def _cancel_key(row_cancelled, code):
        if row_cancelled and code in lookups["cancel_reason"]:
            return lookups["cancel_reason"][code]
        return n_key
    df["cancel_reason_key"] = [
        _cancel_key(c, code)
        for c, code in zip(cancelled, cancel_code)
    ]

    # --- Flight number --------------------------------------------------------
    df["flight_number_str"] = _int_col(df["flight_number"]).fillna(0).astype(str)

    # --- Delay columns --------------------------------------------------------
    dep_delay  = _int_col(df["dep_delay"])
    arr_delay  = _int_col(df["arr_delay"])
    carrier_d  = _int_col(df["carrier_delay"]).fillna(0)
    weather_d  = _int_col(df["weather_delay"]).fillna(0)
    nas_d      = _int_col(df["nas_delay"]).fillna(0)
    security_d = _int_col(df["security_delay"]).fillna(0)
    late_d     = _int_col(df["late_aircraft_delay"]).fillna(0)
    taxi_out   = _int_col(df["taxi_out"])
    taxi_in    = _int_col(df["taxi_in"])
    air_time   = _int_col(df["air_time"])
    distance   = _int_col(df["distance"])
    diverted   = _int_col(df["diverted"]).fillna(0)

    def _py(val):
        """Convert pandas NA / numpy int to Python int or None."""
        if pd.isna(val):
            return None
        return int(val)

    rows = [
        (
            int(row.date_key),
            int(row.airline_key),
            int(row.origin_key),
            int(row.dest_key),
            _py(row.plane_key),
            _py(row.cancel_reason_key),
            row.flight_number_str,
            source_label,
            _py(dep),
            _py(arr),
            int(car), int(wea), int(nas), int(sec), int(lat),
            _py(tout), _py(tin), _py(air), _py(dist),
            1,
            bool(can),
            bool(div),
        )
        for row, dep, arr, car, wea, nas, sec, lat, tout, tin, air, dist, can, div in zip(
            df.itertuples(index=False),
            dep_delay, arr_delay,
            carrier_d, weather_d, nas_d, security_d, late_d,
            taxi_out, taxi_in, air_time, distance,
            cancelled, diverted,
        )
    ]

    return rows, skipped


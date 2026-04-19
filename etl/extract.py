"""
extract.py — CSV extraction functions for the Flight Delays ETL pipeline.

Reads raw data from all source CSV files without transformations.
Each function returns either a full DataFrame or a generator of chunks.
"""
import pandas as pd
from typing import Generator


def extract_airlines(path: str) -> pd.DataFrame:
    """Read dataset3 airlines.csv (14 rows)."""
    return pd.read_csv(path, dtype={"IATA_CODE": str, "AIRLINE": str})


def extract_airports(path: str) -> pd.DataFrame:
    """Read dataset3 airports.csv (322 rows)."""
    return pd.read_csv(
        path,
        dtype={
            "IATA_CODE": str,
            "AIRPORT": str,
            "CITY": str,
            "STATE": str,
            "COUNTRY": str,
        },
    )


# Explicit dtypes prevent pandas from misinterpreting HHMM times as floats
# or converting airport codes like "0055" to integers.
_D3_DTYPES = {
    "YEAR": "Int16",
    "MONTH": "Int8",
    "DAY": "Int8",
    "DAY_OF_WEEK": "Int8",
    "AIRLINE": str,
    "FLIGHT_NUMBER": "Int32",
    "TAIL_NUMBER": str,
    "ORIGIN_AIRPORT": str,
    "DESTINATION_AIRPORT": str,
    "SCHEDULED_DEPARTURE": str,
    "DEPARTURE_TIME": str,
    "DEPARTURE_DELAY": "Float32",
    "TAXI_OUT": "Float32",
    "WHEELS_OFF": str,
    "SCHEDULED_TIME": "Float32",
    "ELAPSED_TIME": "Float32",
    "AIR_TIME": "Float32",
    "DISTANCE": "Float32",
    "WHEELS_ON": str,
    "TAXI_IN": "Float32",
    "SCHEDULED_ARRIVAL": str,
    "ARRIVAL_TIME": str,
    "ARRIVAL_DELAY": "Float32",
    "DIVERTED": "Int8",
    "CANCELLED": "Int8",
    "CANCELLATION_REASON": str,
    "AIR_SYSTEM_DELAY": "Float32",
    "SECURITY_DELAY": "Float32",
    "AIRLINE_DELAY": "Float32",
    "LATE_AIRCRAFT_DELAY": "Float32",
    "WEATHER_DELAY": "Float32",
}

_D1_DTYPES = {
    "FL_DATE": str,
    "AIRLINE": str,
    "AIRLINE_DOT": str,
    "AIRLINE_CODE": str,
    "DOT_CODE": "Int32",
    "FL_NUMBER": "Int32",
    "ORIGIN": str,
    "ORIGIN_CITY": str,
    "DEST": str,
    "DEST_CITY": str,
    "CRS_DEP_TIME": str,
    "DEP_TIME": str,
    "DEP_DELAY": "Float32",
    "TAXI_OUT": "Float32",
    "WHEELS_OFF": str,
    "WHEELS_ON": str,
    "TAXI_IN": "Float32",
    "CRS_ARR_TIME": str,
    "ARR_TIME": str,
    "ARR_DELAY": "Float32",
    "CANCELLED": "Float32",
    "CANCELLATION_CODE": str,
    "DIVERTED": "Float32",
    "CRS_ELAPSED_TIME": "Float32",
    "ELAPSED_TIME": "Float32",
    "AIR_TIME": "Float32",
    "DISTANCE": "Float32",
    "DELAY_DUE_CARRIER": "Float32",
    "DELAY_DUE_WEATHER": "Float32",
    "DELAY_DUE_NAS": "Float32",
    "DELAY_DUE_SECURITY": "Float32",
    "DELAY_DUE_LATE_AIRCRAFT": "Float32",
}


def extract_dataset3_chunked(
    path: str, chunk_size: int = 100_000
) -> Generator[pd.DataFrame, None, None]:
    """Yield chunks of dataset3/flights.csv."""
    yield from pd.read_csv(
        path,
        dtype=_D3_DTYPES,
        keep_default_na=False,
        na_values=["", "NA"],
        chunksize=chunk_size,
    )


def extract_dataset1_chunked(
    path: str, chunk_size: int = 100_000
) -> Generator[pd.DataFrame, None, None]:
    """Yield chunks of dataset1/flights_sample_3m.csv."""
    yield from pd.read_csv(
        path,
        dtype=_D1_DTYPES,
        keep_default_na=False,
        na_values=["", "NA"],
        chunksize=chunk_size,
    )


def extract_unique_tail_numbers(path: str, chunk_size: int = 100_000) -> set:
    """Single-pass scan for unique TAIL_NUMBER values in dataset3."""
    tails: set = set()
    for chunk in pd.read_csv(
        path,
        usecols=["TAIL_NUMBER"],
        dtype={"TAIL_NUMBER": str},
        keep_default_na=False,
        na_values=["", "NA"],
        chunksize=chunk_size,
    ):
        valid = chunk["TAIL_NUMBER"].dropna()
        valid = valid[valid.str.strip() != ""]
        tails.update(valid.str.strip().tolist())
    return tails

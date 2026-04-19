-- ============================================================
-- Flight Delays Data Warehouse
-- Phase 4: Physical Model DDL
-- Database: PostgreSQL 14
-- ============================================================

-- Drop tables in reverse FK dependency order (safe for re-runs)
DROP TABLE IF EXISTS Fact_Flight_Operations CASCADE;
DROP TABLE IF EXISTS Dim_Date CASCADE;
DROP TABLE IF EXISTS Dim_Airline CASCADE;
DROP TABLE IF EXISTS Dim_Airport CASCADE;
DROP TABLE IF EXISTS Dim_Plane CASCADE;
DROP TABLE IF EXISTS Dim_Cancellation_Reason CASCADE;

-- ============================================================
-- DIMENSION: Dim_Date
-- Grain: one row per calendar day covering all years loaded
-- date_key uses YYYYMMDD integer format for fast integer joins
-- ============================================================
CREATE TABLE Dim_Date (
    date_key        INT             PRIMARY KEY,
    full_date       DATE            NOT NULL UNIQUE,
    year            SMALLINT        NOT NULL,
    month           SMALLINT        NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name      VARCHAR(10)     NOT NULL,
    quarter         SMALLINT        NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    day_of_month    SMALLINT        NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week     SMALLINT        NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    day_name        VARCHAR(10)     NOT NULL,
    is_weekend      BOOLEAN         NOT NULL,
    season          VARCHAR(10)     NOT NULL
                    CHECK (season IN ('Winter', 'Spring', 'Summer', 'Autumn'))
);

-- ============================================================
-- DIMENSION: Dim_Airline
-- Grain: one row per airline carrier (IATA code)
-- ============================================================
CREATE TABLE Dim_Airline (
    airline_key         SERIAL          PRIMARY KEY,
    airline_id          INT,
    iata_code           CHAR(2)         NOT NULL UNIQUE,
    airline_code        CHAR(2),
    airline_name        VARCHAR(50)     NOT NULL,
    country_of_origin   VARCHAR(50)     DEFAULT 'USA'
);

-- ============================================================
-- DIMENSION: Dim_Airport
-- Grain: one row per airport (IATA code)
-- Role-playing: used twice in Fact as origin and destination
-- ============================================================
CREATE TABLE Dim_Airport (
    airport_key     SERIAL          PRIMARY KEY,
    airport_id      INT,
    iata_code       CHAR(3)         NOT NULL UNIQUE,
    airport_name    VARCHAR(100),
    city            VARCHAR(50),
    country         VARCHAR(50),
    latitude        DECIMAL(9,5),
    longitude       DECIMAL(9,5)
);

-- ============================================================
-- DIMENSION: Dim_Plane
-- Grain: one row per unique tail number
-- Note: dataset contains only TAIL_NUMBER; model/manufacturer
--       fields are NULL because source data lacks aircraft metadata.
-- ============================================================
CREATE TABLE Dim_Plane (
    plane_key       SERIAL          PRIMARY KEY,
    plane_id        INT,
    tail_number     VARCHAR(10)     NOT NULL UNIQUE,
    model           VARCHAR(50),
    manufacturer    VARCHAR(50),
    issue_date      DATE,
    status          VARCHAR(20)     DEFAULT 'Unknown'
);

-- ============================================================
-- DIMENSION: Dim_Cancellation_Reason
-- Static lookup: 4 known IATA/BTS codes + 1 sentinel
-- ============================================================
CREATE TABLE Dim_Cancellation_Reason (
    cancel_reason_key   SERIAL          PRIMARY KEY,
    cancellation_code   CHAR(1)         NOT NULL UNIQUE,
    description         VARCHAR(50)     NOT NULL
);

-- Seed: known cancellation codes
INSERT INTO Dim_Cancellation_Reason (cancellation_code, description) VALUES
    ('A', 'Carrier'),
    ('B', 'Weather'),
    ('C', 'National Air System'),
    ('D', 'Security'),
    ('N', 'Not Applicable');

-- ============================================================
-- FACT TABLE: Fact_Flight_Operations
-- Grain: one row per flight on a specific flight date
-- Covers both Dataset 1 (2019–2023) and Dataset 3 (2015)
-- source_dataset column identifies the row's origin
-- ============================================================
CREATE TABLE Fact_Flight_Operations (
    flight_operation_id     BIGSERIAL       PRIMARY KEY,

    -- Dimension foreign keys
    date_key                INT             NOT NULL
                            REFERENCES Dim_Date(date_key),
    airline_key             INT             NOT NULL
                            REFERENCES Dim_Airline(airline_key),
    origin_airport_key      INT             NOT NULL
                            REFERENCES Dim_Airport(airport_key),
    destination_airport_key INT             NOT NULL
                            REFERENCES Dim_Airport(airport_key),
    plane_key               INT
                            REFERENCES Dim_Plane(plane_key),
    cancel_reason_key       INT
                            REFERENCES Dim_Cancellation_Reason(cancel_reason_key),

    -- Degenerate dimension
    flight_number           VARCHAR(6)      NOT NULL,

    -- Data source tracking
    source_dataset          VARCHAR(20)     NOT NULL
                            CHECK (source_dataset IN ('dataset1', 'dataset3')),

    -- Delay measures (minutes; NULL for cancelled flights)
    departure_delay_min     SMALLINT,
    arrival_delay_min       SMALLINT,

    -- Delay breakdown (0 for non-delayed flights; NULL if dataset lacks breakdown)
    carrier_delay_min       SMALLINT,
    weather_delay_min       SMALLINT,
    nas_delay_min           SMALLINT,
    security_delay_min      SMALLINT,
    late_aircraft_delay_min SMALLINT,

    -- Operational measures
    taxi_out_min            SMALLINT,
    taxi_in_min             SMALLINT,
    air_time_min            SMALLINT,
    distance_miles          SMALLINT,

    -- Counters and flags
    flight_count            SMALLINT        NOT NULL DEFAULT 1
                            CHECK (flight_count > 0),
    cancelled_flag          BOOLEAN         NOT NULL DEFAULT FALSE,
    diverted_flag           BOOLEAN         NOT NULL DEFAULT FALSE
);

-- ============================================================
-- INDEXES — optimised for analytical query patterns
-- ============================================================

-- Most common GROUP BY / WHERE dimensions
CREATE INDEX idx_fact_date       ON Fact_Flight_Operations(date_key);
CREATE INDEX idx_fact_airline    ON Fact_Flight_Operations(airline_key);
CREATE INDEX idx_fact_origin     ON Fact_Flight_Operations(origin_airport_key);
CREATE INDEX idx_fact_dest       ON Fact_Flight_Operations(destination_airport_key);
CREATE INDEX idx_fact_plane      ON Fact_Flight_Operations(plane_key);
CREATE INDEX idx_fact_cancel_key ON Fact_Flight_Operations(cancel_reason_key);
CREATE INDEX idx_fact_source     ON Fact_Flight_Operations(source_dataset);

-- Partial index — cancellation analysis queries touch only ~1.5% of rows
CREATE INDEX idx_fact_cancelled
    ON Fact_Flight_Operations(cancel_reason_key)
    WHERE cancelled_flag = TRUE;

-- Dimension natural-key indexes — used during ETL lookups
CREATE INDEX idx_dim_airport_iata   ON Dim_Airport(iata_code);
CREATE INDEX idx_dim_airline_iata   ON Dim_Airline(iata_code);
CREATE INDEX idx_dim_plane_tail     ON Dim_Plane(tail_number);
CREATE INDEX idx_dim_date_yr_mo     ON Dim_Date(year, month);

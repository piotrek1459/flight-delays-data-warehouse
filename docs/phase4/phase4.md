# Phase 4 – Physical Model and DDL

## 1. Introduction

The physical model translates the logical star schema (defined in Phase 3) into a concrete relational structure tied to a specific database management system. It adds data types, sizes, constraints, and indexing decisions that make the model operational.

---

## 2. Database Management System

**Selected DBMS:** PostgreSQL 14

**Justification:**

| Criterion | Decision |
|-----------|----------|
| License | Open-source (PostgreSQL License) — no cost |
| Scale | Handles 8M+ rows (dataset1 + dataset3 combined) without difficulty |
| Data types | Native `BOOLEAN`, `SMALLINT`, `DECIMAL`, `DATE`, `BIGSERIAL` match the model |
| Bulk loading | `COPY FROM STDIN` protocol enables loading millions of rows in minutes |
| Python integration | `psycopg2-binary` provides direct connection from the ETL scripts |
| Deployment | Dockerized via `docker-compose.yml` with a persistent named volume — start once, data survives restarts |
| Analytics | Supports window functions, `GROUPING SETS`, partial indexes — all used in Phase 6 |

**Additional components:**

| Component | Tool |
|-----------|------|
| ETL | Python 3 (pandas, psycopg2) |
| Containerization | Docker Compose |
| Analysis | SQL (Variant B) + Jupyter Notebook |
| Visualization | matplotlib, seaborn |

---

## 3. Physical Model

### 3.1 Dim_Date

| Column | Data Type | Nullable | Key | Constraint | Rationale |
|--------|-----------|----------|-----|------------|-----------|
| `date_key` | `INT` | NO | PK | — | YYYYMMDD integer; compact and fast for joins |
| `full_date` | `DATE` | NO | UNIQUE | — | Calendar date |
| `year` | `SMALLINT` | NO | — | — | 2015–2023 fits in SMALLINT |
| `month` | `SMALLINT` | NO | — | 1–12 | Month number |
| `month_name` | `VARCHAR(10)` | NO | — | — | e.g. 'January' (max 9 chars) |
| `quarter` | `SMALLINT` | NO | — | 1–4 | Quarter number |
| `day_of_month` | `SMALLINT` | NO | — | 1–31 | Day within month |
| `day_of_week` | `SMALLINT` | NO | — | 1–7 | 1 = Monday, 7 = Sunday |
| `day_name` | `VARCHAR(10)` | NO | — | — | e.g. 'Wednesday' (max 9 chars) |
| `is_weekend` | `BOOLEAN` | NO | — | — | TRUE for Saturday / Sunday |
| `season` | `VARCHAR(10)` | NO | — | IN ('Winter', 'Spring', 'Summer', 'Autumn') | Calendar season |

### 3.2 Dim_Airline

| Column | Data Type | Nullable | Key | Constraint | Rationale |
|--------|-----------|----------|-----|------------|-----------|
| `airline_key` | `SERIAL` | NO | PK | — | Surrogate key |
| `airline_id` | `INT` | YES | — | — | Business key from operational DB |
| `iata_code` | `CHAR(2)` | NO | UNIQUE | — | Always exactly 2 chars (e.g. UA, DL) |
| `airline_code` | `CHAR(2)` | YES | — | — | May differ from IATA in some sources |
| `airline_name` | `VARCHAR(50)` | NO | — | — | Longest observed: 28 chars |
| `country_of_origin` | `VARCHAR(50)` | YES | — | DEFAULT 'USA' | All carriers in dataset are US-based |

### 3.3 Dim_Airport

| Column | Data Type | Nullable | Key | Constraint | Rationale |
|--------|-----------|----------|-----|------------|-----------|
| `airport_key` | `SERIAL` | NO | PK | — | Surrogate key |
| `airport_id` | `INT` | YES | — | — | Business key from operational DB |
| `iata_code` | `CHAR(3)` | NO | UNIQUE | — | Always exactly 3 chars (e.g. LAX, ORD) |
| `airport_name` | `VARCHAR(100)` | YES | — | — | Longest observed: 78 chars |
| `city` | `VARCHAR(50)` | YES | — | — | Longest observed: 30 chars |
| `country` | `VARCHAR(50)` | YES | — | — | All USA in primary datasets |
| `latitude` | `DECIMAL(9,5)` | YES | — | — | 5 decimal places (e.g. 40.65236) |
| `longitude` | `DECIMAL(9,5)` | YES | — | — | Negative for western longitudes |

### 3.4 Dim_Plane

| Column | Data Type | Nullable | Key | Constraint | Rationale |
|--------|-----------|----------|-----|------------|-----------|
| `plane_key` | `SERIAL` | NO | PK | — | Surrogate key |
| `plane_id` | `INT` | YES | — | — | Business key from operational DB |
| `tail_number` | `VARCHAR(10)` | NO | UNIQUE | — | FAA tail number (e.g. N407AS) |
| `model` | `VARCHAR(50)` | YES | — | — | NULL — dataset lacks aircraft metadata |
| `manufacturer` | `VARCHAR(50)` | YES | — | — | NULL — dataset lacks aircraft metadata |
| `issue_date` | `DATE` | YES | — | — | NULL — dataset lacks aircraft metadata |
| `status` | `VARCHAR(20)` | YES | — | DEFAULT 'Unknown' | Operational status |

> **Note:** The source datasets contain only `TAIL_NUMBER` per flight with no additional aircraft metadata. All columns except `tail_number` are therefore NULL for all loaded rows. A future enhancement could enrich this dimension from the FAA Aircraft Registry.

### 3.5 Dim_Cancellation_Reason

| Column | Data Type | Nullable | Key | Constraint | Rationale |
|--------|-----------|----------|-----|------------|-----------|
| `cancel_reason_key` | `SERIAL` | NO | PK | — | Surrogate key |
| `cancellation_code` | `CHAR(1)` | NO | UNIQUE | — | A/B/C/D/N |
| `description` | `VARCHAR(50)` | NO | — | — | Human-readable label |

Seeded values:

| Code | Description |
|------|-------------|
| A | Carrier |
| B | Weather |
| C | National Air System |
| D | Security |
| N | Not Applicable *(sentinel for non-cancelled flights)* |

### 3.6 Fact_Flight_Operations

| Column | Data Type | Nullable | Key | Constraint | Rationale |
|--------|-----------|----------|-----|------------|-----------|
| `flight_operation_id` | `BIGSERIAL` | NO | PK | — | BIGSERIAL: future-safe beyond 2B rows |
| `date_key` | `INT` | NO | FK → Dim_Date | — | YYYYMMDD integer |
| `airline_key` | `INT` | NO | FK → Dim_Airline | — | |
| `origin_airport_key` | `INT` | NO | FK → Dim_Airport | — | Role: departure airport |
| `destination_airport_key` | `INT` | NO | FK → Dim_Airport | — | Role: arrival airport |
| `plane_key` | `INT` | YES | FK → Dim_Plane | — | NULL for Dataset 1 rows (no TAIL_NUMBER) |
| `cancel_reason_key` | `INT` | YES | FK → Dim_Cancellation_Reason | — | Set to 'N' sentinel for non-cancelled |
| `flight_number` | `VARCHAR(6)` | NO | — | — | Degenerate dimension |
| `source_dataset` | `VARCHAR(20)` | NO | — | IN ('dataset1','dataset3') | Row provenance |
| `departure_delay_min` | `SMALLINT` | YES | — | — | NULL for cancelled flights |
| `arrival_delay_min` | `SMALLINT` | YES | — | — | NULL for cancelled flights |
| `carrier_delay_min` | `SMALLINT` | YES | — | — | 0 for non-delayed; NULL if dataset lacks breakdown |
| `weather_delay_min` | `SMALLINT` | YES | — | — | Same as above |
| `nas_delay_min` | `SMALLINT` | YES | — | — | Same as above |
| `security_delay_min` | `SMALLINT` | YES | — | — | Same as above |
| `late_aircraft_delay_min` | `SMALLINT` | YES | — | — | Same as above |
| `taxi_out_min` | `SMALLINT` | YES | — | — | NULL for cancelled flights |
| `taxi_in_min` | `SMALLINT` | YES | — | — | NULL for cancelled flights |
| `air_time_min` | `SMALLINT` | YES | — | — | NULL for cancelled/diverted |
| `distance_miles` | `SMALLINT` | YES | — | — | Max observed: 4,983 miles |
| `flight_count` | `SMALLINT` | NO | — | > 0, DEFAULT 1 | Always 1; enables COUNT(*) alternatives |
| `cancelled_flag` | `BOOLEAN` | NO | — | DEFAULT FALSE | |
| `diverted_flag` | `BOOLEAN` | NO | — | DEFAULT FALSE | |

---

## 4. DDL SQL Statements

The complete DDL is stored in `sql/ddl.sql` and is automatically executed on first PostgreSQL container start via Docker Compose.

```sql
-- ============================================================
-- Flight Delays Data Warehouse
-- Phase 4: Physical Model DDL
-- Database: PostgreSQL 14
-- ============================================================

DROP TABLE IF EXISTS Fact_Flight_Operations CASCADE;
DROP TABLE IF EXISTS Dim_Date CASCADE;
DROP TABLE IF EXISTS Dim_Airline CASCADE;
DROP TABLE IF EXISTS Dim_Airport CASCADE;
DROP TABLE IF EXISTS Dim_Plane CASCADE;
DROP TABLE IF EXISTS Dim_Cancellation_Reason CASCADE;

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

CREATE TABLE Dim_Airline (
    airline_key         SERIAL          PRIMARY KEY,
    airline_id          INT,
    iata_code           CHAR(2)         NOT NULL UNIQUE,
    airline_code        CHAR(2),
    airline_name        VARCHAR(50)     NOT NULL,
    country_of_origin   VARCHAR(50)     DEFAULT 'USA'
);

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

CREATE TABLE Dim_Plane (
    plane_key       SERIAL          PRIMARY KEY,
    plane_id        INT,
    tail_number     VARCHAR(10)     NOT NULL UNIQUE,
    model           VARCHAR(50),
    manufacturer    VARCHAR(50),
    issue_date      DATE,
    status          VARCHAR(20)     DEFAULT 'Unknown'
);

CREATE TABLE Dim_Cancellation_Reason (
    cancel_reason_key   SERIAL          PRIMARY KEY,
    cancellation_code   CHAR(1)         NOT NULL UNIQUE,
    description         VARCHAR(50)     NOT NULL
);

INSERT INTO Dim_Cancellation_Reason (cancellation_code, description) VALUES
    ('A', 'Carrier'),
    ('B', 'Weather'),
    ('C', 'National Air System'),
    ('D', 'Security'),
    ('N', 'Not Applicable');

CREATE TABLE Fact_Flight_Operations (
    flight_operation_id     BIGSERIAL       PRIMARY KEY,
    date_key                INT             NOT NULL REFERENCES Dim_Date(date_key),
    airline_key             INT             NOT NULL REFERENCES Dim_Airline(airline_key),
    origin_airport_key      INT             NOT NULL REFERENCES Dim_Airport(airport_key),
    destination_airport_key INT             NOT NULL REFERENCES Dim_Airport(airport_key),
    plane_key               INT             REFERENCES Dim_Plane(plane_key),
    cancel_reason_key       INT             REFERENCES Dim_Cancellation_Reason(cancel_reason_key),
    flight_number           VARCHAR(6)      NOT NULL,
    source_dataset          VARCHAR(20)     NOT NULL
                            CHECK (source_dataset IN ('dataset1', 'dataset3')),
    departure_delay_min     SMALLINT,
    arrival_delay_min       SMALLINT,
    carrier_delay_min       SMALLINT,
    weather_delay_min       SMALLINT,
    nas_delay_min           SMALLINT,
    security_delay_min      SMALLINT,
    late_aircraft_delay_min SMALLINT,
    taxi_out_min            SMALLINT,
    taxi_in_min             SMALLINT,
    air_time_min            SMALLINT,
    distance_miles          SMALLINT,
    flight_count            SMALLINT        NOT NULL DEFAULT 1 CHECK (flight_count > 0),
    cancelled_flag          BOOLEAN         NOT NULL DEFAULT FALSE,
    diverted_flag           BOOLEAN         NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_fact_date       ON Fact_Flight_Operations(date_key);
CREATE INDEX idx_fact_airline    ON Fact_Flight_Operations(airline_key);
CREATE INDEX idx_fact_origin     ON Fact_Flight_Operations(origin_airport_key);
CREATE INDEX idx_fact_dest       ON Fact_Flight_Operations(destination_airport_key);
CREATE INDEX idx_fact_plane      ON Fact_Flight_Operations(plane_key);
CREATE INDEX idx_fact_cancel_key ON Fact_Flight_Operations(cancel_reason_key);
CREATE INDEX idx_fact_source     ON Fact_Flight_Operations(source_dataset);
CREATE INDEX idx_fact_cancelled  ON Fact_Flight_Operations(cancel_reason_key)
    WHERE cancelled_flag = TRUE;

CREATE INDEX idx_dim_airport_iata ON Dim_Airport(iata_code);
CREATE INDEX idx_dim_airline_iata ON Dim_Airline(iata_code);
CREATE INDEX idx_dim_plane_tail   ON Dim_Plane(tail_number);
CREATE INDEX idx_dim_date_yr_mo   ON Dim_Date(year, month);
```

---

## 5. SCD Strategy

Since both datasets are historical snapshots (not live feeds), **SCD Type 1 (Overwrite)** is used for all dimensions. No history tracking is required. In a production system with live airline data feeds, `Dim_Airline` and `Dim_Plane` would benefit from SCD Type 2.

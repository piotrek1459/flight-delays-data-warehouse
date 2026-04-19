# Phase 6 – OLAP Analysis and Reporting

## 1. Introduction

The data warehouse combines flight records from two sources:
- **Dataset 3:** Full year 2015 (~5.8M flights, 14 airlines, 322 airports)
- **Dataset 1:** Multi-year sample 2019–2023 (~3M flights, modern carriers)

Together they support analysis of delays, cancellations, route performance, and carrier behaviour across multiple years, including the COVID-19 period (2020–2021).

---

## 2. Analysis Approach

**Variant B — Manual SQL Queries** (no OLAP cube)

PostgreSQL does not include a built-in OLAP cube engine. All analyses are performed using SQL queries that simulate OLAP operations: `GROUP BY`, `GROUPING SETS`, window functions, `HAVING`, and conditional aggregation. Results are visualised in `notebooks/analysis.ipynb` using `matplotlib` and `seaborn`.

---

## 3. Scheduled Analyses

The following six analyses are implemented:

| # | Name | OLAP Operation | Dimensions Used |
|---|------|----------------|-----------------|
| 1 | Long-term delay trend by airline | Roll-up: Year → Month | Date, Airline |
| 2 | Top 10 most delayed routes | Slice + Sort | Airport (origin + dest) |
| 3 | Cancellation breakdown by reason and airline | Roll-up + Dice | Airline, Cancellation Reason |
| 4 | Delay cause share per airline | Drill-across | Airline |
| 5 | Weekend vs weekday delays by quarter | Drill-down: Quarter → Weekend | Date |
| 6 | Top 20 airports: volume, delay, cancellation rate | Slice + Sort | Airport |

---

## 4. SQL Queries

### Analysis 1 — Long-term Delay Trend by Airline

**Business question:** How has the average departure delay changed per airline across years and months? Does COVID-19 (2020–2021) appear as a dip in traffic and delays?

**Dimensions:** `Dim_Date` (year, month), `Dim_Airline` (airline_name)  
**Measures:** `AVG(departure_delay_min)`, `AVG(arrival_delay_min)`, `COUNT(*)`  
**Visualization:** Line chart — one line per airline, x-axis = year-month

```sql
SELECT
    d.year,
    d.month,
    d.month_name,
    a.airline_name,
    COUNT(*)                                        AS total_flights,
    ROUND(AVG(f.departure_delay_min)::NUMERIC, 2)  AS avg_dep_delay_min,
    ROUND(AVG(f.arrival_delay_min)::NUMERIC, 2)    AS avg_arr_delay_min
FROM Fact_Flight_Operations f
JOIN Dim_Date    d ON f.date_key    = d.date_key
JOIN Dim_Airline a ON f.airline_key = a.airline_key
WHERE f.cancelled_flag = FALSE
GROUP BY d.year, d.month, d.month_name, a.airline_name
ORDER BY a.airline_name, d.year, d.month;
```

---

### Analysis 2 — Top 10 Most Delayed Routes

**Business question:** Which origin–destination pairs have the highest average departure delay, considering only routes with at least 100 flights?

**Dimensions:** `Dim_Airport` (origin IATA, city), `Dim_Airport` (destination IATA, city)  
**Measures:** `AVG(departure_delay_min)`, `COUNT(*)`  
**Visualization:** Horizontal bar chart — top 10 routes by avg departure delay

```sql
SELECT
    orig.iata_code                                      AS origin_iata,
    dest.iata_code                                      AS dest_iata,
    orig.city                                           AS origin_city,
    dest.city                                           AS dest_city,
    COUNT(*)                                            AS total_flights,
    ROUND(AVG(f.departure_delay_min)::NUMERIC, 2)      AS avg_dep_delay_min,
    ROUND(AVG(f.arrival_delay_min)::NUMERIC, 2)        AS avg_arr_delay_min
FROM Fact_Flight_Operations f
JOIN Dim_Airport orig ON f.origin_airport_key      = orig.airport_key
JOIN Dim_Airport dest ON f.destination_airport_key = dest.airport_key
WHERE f.cancelled_flag = FALSE
  AND f.departure_delay_min > 0
GROUP BY orig.iata_code, dest.iata_code, orig.city, dest.city
HAVING COUNT(*) >= 100
ORDER BY avg_dep_delay_min DESC
LIMIT 10;
```

---

### Analysis 3 — Cancellation Breakdown by Reason and Airline

**Business question:** How many flights were cancelled by each airline, broken down by cancellation reason? Includes subtotals per airline and per reason using `GROUPING SETS`.

**Dimensions:** `Dim_Airline`, `Dim_Cancellation_Reason`  
**Measures:** `COUNT(*)` (cancelled flights only)  
**Visualization:** Stacked bar chart — airlines on x-axis, segments by cancellation reason

```sql
SELECT
    COALESCE(a.airline_name, 'ALL AIRLINES')       AS airline,
    COALESCE(r.description,  'ALL REASONS')        AS cancellation_reason,
    COUNT(*)                                        AS cancelled_flights
FROM Fact_Flight_Operations f
JOIN Dim_Airline              a ON f.airline_key        = a.airline_key
JOIN Dim_Cancellation_Reason  r ON f.cancel_reason_key  = r.cancel_reason_key
WHERE f.cancelled_flag = TRUE
  AND r.cancellation_code != 'N'
GROUP BY GROUPING SETS (
    (a.airline_name, r.description),
    (a.airline_name),
    (r.description),
    ()
)
ORDER BY airline, cancellation_reason;
```

---

### Analysis 4 — Delay Cause Share per Airline

**Business question:** For delayed flights, what percentage of total delay minutes is attributable to each cause (carrier, weather, NAS, security, late aircraft) per airline?

**Dimensions:** `Dim_Airline`  
**Measures:** SUM of each delay breakdown, percentage share  
**Visualization:** Stacked bar chart — one bar per airline, segments by delay type

```sql
SELECT
    a.airline_name,
    SUM(COALESCE(f.carrier_delay_min,       0))    AS carrier_delay_total,
    SUM(COALESCE(f.weather_delay_min,       0))    AS weather_delay_total,
    SUM(COALESCE(f.nas_delay_min,           0))    AS nas_delay_total,
    SUM(COALESCE(f.security_delay_min,      0))    AS security_delay_total,
    SUM(COALESCE(f.late_aircraft_delay_min, 0))    AS late_aircraft_delay_total,
    SUM(
        COALESCE(f.carrier_delay_min,       0)
      + COALESCE(f.weather_delay_min,       0)
      + COALESCE(f.nas_delay_min,           0)
      + COALESCE(f.security_delay_min,      0)
      + COALESCE(f.late_aircraft_delay_min, 0)
    )                                               AS total_delay_minutes,
    ROUND(
        100.0 * SUM(COALESCE(f.carrier_delay_min, 0))
        / NULLIF(SUM(
            COALESCE(f.carrier_delay_min,       0)
          + COALESCE(f.weather_delay_min,       0)
          + COALESCE(f.nas_delay_min,           0)
          + COALESCE(f.security_delay_min,      0)
          + COALESCE(f.late_aircraft_delay_min, 0)
        ), 0)::NUMERIC, 2
    )                                               AS carrier_delay_pct
FROM Fact_Flight_Operations f
JOIN Dim_Airline a ON f.airline_key = a.airline_key
WHERE (
    COALESCE(f.carrier_delay_min,       0)
  + COALESCE(f.weather_delay_min,       0)
  + COALESCE(f.nas_delay_min,           0)
  + COALESCE(f.security_delay_min,      0)
  + COALESCE(f.late_aircraft_delay_min, 0)
) > 0
GROUP BY a.airline_name
ORDER BY total_delay_minutes DESC;
```

---

### Analysis 5 — Weekend vs Weekday Delays by Quarter

**Business question:** Are flights significantly more delayed on weekends vs weekdays? Does this pattern change by quarter? A "significant" delay is defined as departure delay > 15 minutes.

**Dimensions:** `Dim_Date` (quarter, is_weekend)  
**Measures:** `COUNT(*)`, delayed%, `AVG(departure_delay_min)`  
**Visualization:** Grouped bar chart — quarters on x-axis, grouped by weekend/weekday

```sql
SELECT
    d.quarter,
    d.is_weekend,
    COUNT(*)                                                        AS total_flights,
    SUM(CASE WHEN f.departure_delay_min > 15 THEN 1 ELSE 0 END)    AS significantly_delayed,
    ROUND(
        100.0
        * SUM(CASE WHEN f.departure_delay_min > 15 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0)::NUMERIC, 2
    )                                                               AS delayed_pct,
    ROUND(AVG(f.departure_delay_min)::NUMERIC, 2)                  AS avg_dep_delay_min
FROM Fact_Flight_Operations f
JOIN Dim_Date d ON f.date_key = d.date_key
WHERE f.cancelled_flag = FALSE
GROUP BY d.quarter, d.is_weekend
ORDER BY d.quarter, d.is_weekend;
```

---

### Analysis 6 — Top 20 Airports: Volume, Delay and Cancellation Rate

**Business question:** Which airports have the highest outbound traffic? How does high traffic correlate with average departure delay and cancellation rate?

**Dimensions:** `Dim_Airport` (origin role)  
**Measures:** `COUNT(*)`, `AVG(departure_delay_min)`, cancellation rate %  
**Visualization:** Scatter plot — x=outbound volume, y=avg delay, bubble size=cancellations

```sql
SELECT
    ap.iata_code,
    ap.airport_name,
    ap.city,
    COUNT(*)                                                AS outbound_flights,
    ROUND(AVG(f.departure_delay_min)::NUMERIC, 2)          AS avg_dep_delay_min,
    SUM(CASE WHEN f.cancelled_flag THEN 1 ELSE 0 END)      AS total_cancellations,
    ROUND(
        100.0
        * SUM(CASE WHEN f.cancelled_flag THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0)::NUMERIC, 2
    )                                                       AS cancellation_rate_pct
FROM Fact_Flight_Operations f
JOIN Dim_Airport ap ON f.origin_airport_key = ap.airport_key
GROUP BY ap.iata_code, ap.airport_name, ap.city
ORDER BY outbound_flights DESC
LIMIT 20;
```

---

## 5. Obtaining the Results

All queries are executed against the PostgreSQL warehouse using `pandas.read_sql_query(sql, conn)` inside the Jupyter Notebook (`notebooks/analysis.ipynb`). Each query result is returned as a `DataFrame` and immediately visualised with `matplotlib` / `seaborn`.

---

## 6. Presentation of Results

Results are presented as charts in `notebooks/analysis.ipynb`:

| Analysis | Chart Type | Key Insight Expected |
|----------|------------|----------------------|
| 1 | Line chart (multi-series) | COVID-19 period (2020) visible as flight count drop |
| 2 | Horizontal bar chart | Short regional routes tend to have highest avg delays |
| 3 | Stacked bar chart | Carrier cancellations dominate over weather |
| 4 | Stacked 100% bar chart | Carrier and late-aircraft causes account for >60% of delay minutes |
| 5 | Grouped bar chart | Weekend flights are marginally more likely to be significantly delayed |
| 6 | Scatter plot (bubble) | Large hub airports (ATL, ORD, DFW) combine high volume with above-average delays |

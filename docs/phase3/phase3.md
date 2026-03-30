# Phase 3 – Logical Data Warehouse Model

## Overview

This section presents the **logical data warehouse model** for the flight delays and cancellations analysis domain.  
The model is derived from the operational database designed in Phase 2 and reorganized according to dimensional modeling principles, so that it supports analytical queries, reporting, and multidimensional analysis.

According to the laboratory requirements, the logical model should contain:
- **fact table(s)** with defined measures,
- **dimension tables** with descriptive attributes and hierarchies,
- **relationships** between facts and dimensions, typically in a **1:N** pattern,
- an overall structure organized as a **star schema** or **snowflake schema**. :contentReference[oaicite:0]{index=0}

For this project, the warehouse is modeled mainly as a **star schema**, with one central fact table describing flight operations and several surrounding dimensions.

---

## Modeling Assumptions

### Business Process
The analyzed business process is **flight execution** in the context of delays, cancellations, and operational disruptions.

### Grain of the Fact Table
The grain of the central fact table is:

> **one row per one flight on a specific flight date**

This means that each record in the fact table represents a single realized or cancelled flight instance identified by flight number and date.

This level of granularity allows the warehouse to support:
- daily and monthly delay analysis,
- airline performance comparisons,
- airport-origin and airport-destination reporting,
- aircraft-based operational analysis,
- cancellation pattern analysis.

---

## Schema Type

The model is designed as a **star schema** with limited snowflake semantics in the business interpretation of hierarchies.  
The fact table is placed in the center, while all dimensions describe the context of each flight event.

Central fact:
- `Fact_Flight_Operations`

Dimensions:
- `Dim_Date`
- `Dim_Airline`
- `Dim_Airport`
- `Dim_Plane`
- `Dim_Cancellation_Reason`

The `Dim_Airport` dimension plays two roles in the model:
- **Origin Airport**
- **Destination Airport**

This is a standard **role-playing dimension** pattern in dimensional modeling.

---

## Fact Table

### Fact_Flight_Operations

The fact table stores measurable operational indicators related to flights.

#### Measures
The following measures are included:

- `departure_delay_min`
- `arrival_delay_min`
- `carrier_delay_min`
- `weather_delay_min`
- `nas_delay_min`
- `security_delay_min`
- `late_aircraft_delay_min`
- `flight_count`

#### Descriptive / Indicator Attributes in Fact
In addition to numeric measures, the fact table contains analysis-supporting indicators:

- `flight_number` *(degenerate dimension)*
- `cancelled_flag`
- `diverted_flag`

#### Foreign Key References
The fact table references the following dimensions:

- `date_key`
- `airline_key`
- `origin_airport_key`
- `destination_airport_key`
- `plane_key`
- `cancel_reason_key`

The fact table does **not** store detailed descriptive attributes of airlines, airports, aircraft, or cancellation reasons.  
Those attributes are separated into dimensions to reduce redundancy and support analytical slicing.

---

## Dimensions

### 1. Dim_Date

The date dimension describes the temporal context of each flight.

#### Attributes
- `date_key`
- `full_date`
- `year`
- `month`
- `month_name`
- `quarter`
- `day_of_month`
- `day_of_week`
- `day_name`
- `is_weekend`
- `season`

#### Hierarchy
A typical hierarchy in this dimension is:

> **Year → Quarter → Month → Day**

This dimension enables trend analysis over time and period-based aggregations.

---

### 2. Dim_Airline

The airline dimension stores descriptive information about carriers.

#### Attributes
- `airline_key`
- `airline_id`
- `iata_code`
- `airline_code`
- `airline_name`
- `country_of_origin`

#### Analytical Use
This dimension allows users to compare operational efficiency, delays, and cancellations across carriers, including analysis by the airline’s country of origin.

---

### 3. Dim_Airport

The airport dimension stores descriptive and geographic information about airports.

#### Attributes
- `airport_key`
- `airport_id`
- `iata_code`
- `airport_name`
- `city`
- `country`
- `latitude`
- `longitude`

#### Roles in the Schema
This single logical dimension is used in two roles:
- `origin_airport_key`
- `destination_airport_key`

#### Hierarchy
A typical geographic hierarchy may be interpreted as:

> **Country → City → Airport**

This supports geographic analysis of departure and arrival patterns.
### 4. Dim_Plane

The plane dimension stores descriptive information about aircraft.

#### Attributes
- `plane_key`
- `plane_id`
- `tail_number`
- `model`
- `manufacturer`
- `issue_date`
- `status`

#### Analytical Use
This dimension enables analysis of delays and operational disruptions by aircraft model, manufacturer, or aircraft status.

---

### 5. Dim_Cancellation_Reason

This dimension stores standardized cancellation categories.

#### Attributes
- `cancel_reason_key`
- `cancellation_code`
- `description`

#### Analytical Use
This dimension is used only when flights are cancelled, but it remains part of the schema to enable consistent reporting on cancellation causes.

---

## Measures and Aggregation Behavior

The fact table contains mostly **additive measures**, especially all delay durations expressed in minutes.  
These measures can be aggregated across time, airline, airport, and aircraft dimensions.

Examples:
- total departure delay by airline,
- average arrival delay by month,
- total weather delay by airport,
- total number of cancelled flights by cancellation reason.

`flight_count` is typically modeled as a constant value equal to `1` for each row, enabling:
- total number of flights,
- counting delayed or cancelled flights using filtering conditions.

Boolean indicators such as `cancelled_flag` and `diverted_flag` are not classical measures, but they support conditional aggregation in BI tools.

---

## Mapping from Operational Model to Warehouse Model

The warehouse model is derived from the operational entities from Phase 2.  
The transformation logic is as follows:

- `Flights` → source for `Fact_Flight_Operations`
- `Airlines` → source for `Dim_Airline`
- `Airports` → source for `Dim_Airport`
- `Planes` → source for `Dim_Plane`
- `Cancellation_Reasons` → source for `Dim_Cancellation_Reason`
- calendar fields from `Flights.flight_date` → source for `Dim_Date`

In the operational model, all flight-related data was concentrated around the `Flights` table.  
In the warehouse model, this structure is reorganized into:
- one **central fact**
- multiple **descriptive dimensions**

This improves query readability and analytical usability.

The previous file content described the operational relational model centered on the `Flights` table and its supporting entities, so it corresponded to Phase 2 rather than Phase 3. :contentReference[oaicite:1]{index=1}

---

## Relationships in the Logical Model

The logical warehouse model contains the following relationships:

- `Dim_Date 1:N Fact_Flight_Operations`
- `Dim_Airline 1:N Fact_Flight_Operations`
- `Dim_Airport 1:N Fact_Flight_Operations` as **Origin Airport**
- `Dim_Airport 1:N Fact_Flight_Operations` as **Destination Airport**
- `Dim_Plane 1:N Fact_Flight_Operations`
- `Dim_Cancellation_Reason 1:N Fact_Flight_Operations`

All relationships are dimension-to-fact relationships typical for dimensional modeling.

---

## Technical Design Decisions

### Surrogate Keys
Each dimension uses a surrogate primary key:
- `date_key`
- `airline_key`
- `airport_key`
- `plane_key`
- `cancel_reason_key`

This improves integration, stability, and historical tracking in a real warehouse implementation.

### Degenerate Dimension
`flight_number` remains in the fact table as a **degenerate dimension**, because it is a business identifier useful in reporting but does not require a separate dimension table.

### Null / Optional Context
Some flights may not have a cancellation reason or even a known aircraft entry.  
In a physical implementation, such situations should be handled using:
- nullable foreign keys, or
- default “Unknown / Not Applicable” dimension members.

### Slowly Changing Dimensions
If implemented physically, some dimensions may require **Slowly Changing Dimension (SCD)** handling:
- `Dim_Airline` – usually Type 1
- `Dim_Airport` – usually Type 1
- `Dim_Plane` – potentially Type 2 if aircraft status changes should be historized

At the logical stage, these behaviors are only noted as future implementation considerations.

---

## Conclusion

The logical data warehouse model reorganizes operational flight data into a dimensional structure suitable for analytics.  
The schema is centered around the `Fact_Flight_Operations` fact table and supported by dimensions describing time, airline, airport, aircraft, and cancellation reason.

This model satisfies the laboratory requirement for a logical warehouse model by defining:
- a central fact with measures,
- descriptive dimensions with attributes and hierarchies,
- explicit 1:N relationships between dimensions and fact,
- a clear star-schema analytical structure. :contentReference[oaicite:2]{index=2}
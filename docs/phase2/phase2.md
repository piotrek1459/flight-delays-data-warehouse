
## Conceptual Model

The diagram presents a high-level conceptual view of the flight delay analysis domain.  
The central business object is **Flight**, which is described by operational, temporal, geographic, weather-related, and disruption-related elements.  

This model is intentionally non-technical.  
It does not show database tables, keys, or data types.  
Instead, it reflects how we understand the domain and which factors may influence flight delays and cancellations.

---

## Entity-Relationship Diagram (dbdiagram.io)

The following DBML definition describes the **operational (relational) database model** for the flight delays domain.  
It organizes data into five tables reflecting real-world entities, suitable for an OLTP system.

> To render this diagram interactively, paste the DBML code at **https://dbdiagram.io/d**

```dbml
Table Airlines {
  airline_id    INT          [pk, increment, note: "Surrogate primary key"]
  iata_code     CHAR(2)      [not null, unique, note: "IATA carrier code, e.g. AA, UA"]
  airline_name  VARCHAR(50)  [not null]
}

Table Airports {
  airport_id    INT           [pk, increment]
  iata_code     CHAR(3)       [not null, unique, note: "IATA airport code, e.g. LAX, ORD"]
  airport_name  VARCHAR(100)
  city          VARCHAR(50)
  state         CHAR(2)
  country       VARCHAR(50)
  latitude      DECIMAL(9,5)
  longitude     DECIMAL(9,5)
}

Table Planes {
  plane_id      INT          [pk, increment]
  tail_number   VARCHAR(10)  [not null, unique, note: "FAA tail number, e.g. N407AS"]
  model         VARCHAR(50)
  manufacturer  VARCHAR(50)
  issue_date    DATE
  status        VARCHAR(20)
}

Table Cancellation_Reasons {
  reason_id          INT         [pk, increment]
  cancellation_code  CHAR(1)     [not null, unique, note: "A=Carrier, B=Weather, C=NAS, D=Security"]
  description        VARCHAR(50) [not null]
}

Table Flights {
  flight_id              INT       [pk, increment]
  flight_date            DATE      [not null]
  flight_number          INT       [not null]
  airline_id             INT       [ref: > Airlines.airline_id, not null]
  origin_airport_id      INT       [ref: > Airports.airport_id, not null]
  destination_airport_id INT       [ref: > Airports.airport_id, not null]
  plane_id               INT       [ref: > Planes.plane_id]
  cancel_reason_id       INT       [ref: > Cancellation_Reasons.reason_id]
  scheduled_dep_time     TIME
  actual_dep_time        TIME
  scheduled_arr_time     TIME
  actual_arr_time        TIME
  dep_delay              SMALLINT
  arr_delay              SMALLINT
  carrier_delay          SMALLINT
  weather_delay          SMALLINT
  nas_delay              SMALLINT
  security_delay         SMALLINT
  late_aircraft_delay    SMALLINT
  taxi_out               SMALLINT
  taxi_in                SMALLINT
  air_time               SMALLINT
  distance               SMALLINT
  cancelled              BOOLEAN   [not null, default: false]
  diverted               BOOLEAN   [not null, default: false]
}
```

### Relationships Summary

| Relationship | Cardinality | Description |
|---|---|---|
| Airlines → Flights | 1:N | One airline operates many flights |
| Airports → Flights (origin) | 1:N | One airport is the origin of many flights |
| Airports → Flights (destination) | 1:N | One airport is the destination of many flights |
| Planes → Flights | 1:N | One aircraft performs many flights |
| Cancellation_Reasons → Flights | 1:N | One cancellation reason applies to many flights |
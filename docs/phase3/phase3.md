# Phase 2 – Operational Database Model

## Overview

This section presents the **operational database model** designed for the flight delays and cancellations project.  
The model describes the logical structure of the source database that stores operational flight data before transforming it into a data warehouse schema.

The central entity in the model is the **Flights** table, which stores information about individual flights, including scheduling data, actual execution times, delays, cancellations, diversions, and detailed delay categories.  
Supporting entities describe airlines, airports, aircraft, and cancellation reasons.

The purpose of this model is to organize raw operational data in a structured and relational way, so that it can later serve as the foundation for ETL processes and analytical warehouse design.

---

## Diagram

![Operational Database Model](./images/phase2-operational-model.png)

> Replace the path above with the actual exported image from PlantUML.

---

## Main Entities

### 1. Flights
The `Flights` table is the core of the operational model.  
It contains data about each flight, such as:

- flight date
- flight number
- departure and arrival airports
- assigned airline
- assigned aircraft
- scheduled and actual departure/arrival times
- departure and arrival delays
- cancellation and diversion status
- detailed causes of delay:
  - carrier delay
  - weather delay
  - NAS delay
  - security delay
  - late aircraft delay

This table connects all other entities and represents the main business process being analyzed.

### 2. Airlines
The `Airlines` table stores information about carriers operating the flights.  
It includes airline identifiers, airline codes, and airline names.

Each airline can operate many flights, while each flight is assigned to exactly one airline.

### 3. Airports
The `Airports` table stores information about airports, including:

- IATA code
- airport name
- city
- state
- country
- geographic coordinates

This entity is used twice in relation to flights:
- as the **origin airport**
- as the **destination airport**

One airport can therefore be associated with many flights as either departure or arrival location.

### 4. Planes
The `Planes` table stores aircraft-related information, such as:

- tail number
- aircraft model
- manufacturer
- issue date
- operational status

Each plane may be assigned to multiple flights over time, while each flight references one aircraft.

### 5. Cancellation Reasons
The `Cancellation_Reasons` table is a lookup table that describes cancellation reason codes.  
It standardizes the meaning of cancellation categories and improves data consistency.

A cancellation reason can be linked to many flights, but each cancelled flight has at most one cancellation code.

---

## Relationships Between Entities

The operational model includes the following relationships:

- **Airlines → Flights**  
  One airline operates many flights.

- **Airports → Flights (origin)**  
  One airport can be the origin of many flights.

- **Airports → Flights (destination)**  
  One airport can be the destination of many flights.

- **Planes → Flights**  
  One aircraft can be assigned to many flights over time.

- **Cancellation Reasons → Flights**  
  One cancellation reason can describe many cancelled flights.

These relationships ensure referential integrity and reduce redundancy in the operational database.

---

## Design Rationale

This model was designed as an **operational relational database**, not yet as a dimensional warehouse model.  
Its structure reflects the real-world business domain of air transportation and supports efficient storage of transactional flight data.

The model separates descriptive data into dedicated tables and keeps flight event data in the central `Flights` table.  
This approach improves consistency, readability, and maintainability, while also preparing the dataset for future transformation into a star schema.

---

## Conclusion

The operational database model provides a clean and normalized structure for storing flight delay and cancellation data.  
It captures the most important business entities and their relationships, and it serves as the starting point for the next phase of the project, where the analytical data warehouse model will be developed.
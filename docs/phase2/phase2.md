
## Conceptual Model

The diagram presents a high-level conceptual view of the flight delay analysis domain.  
The central business object is **Flight**, which is described by operational, temporal, geographic, weather-related, and disruption-related elements.  

This model is intentionally non-technical.  
It does not show database tables, keys, or data types.  
Instead, it reflects how we understand the domain and which factors may influence flight delays and cancellations.

```mermaid
mindmap
  root((Flight))
    Airline
    Flight Number
    Origin Airport
    Destination Airport
    Departure City
    Arrival City
    Departure Time
    Arrival Time
    Scheduled Time
    Actual Time
    Date
    Day of Week
    Month
    Season
    Weather
      Temperature
      Wind
      Visibility
      Rain / Snow
    Aircraft
    Delay
      Departure Delay
      Arrival Delay
      Delay Reason
      Carrier Delay
      Weather Delay
      Security Delay
      Late Aircraft Delay
      NAS Delay
    Cancellation
      Cancellation Reason
    Diversion
    Distance
    Flight Duration
    Route
    Airport Traffic
```
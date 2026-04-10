# Grass Growth Predictor — Architecture

→ [README](README.md) · [CHANGELOG](CHANGELOG.md)

## Overview

The integration estimates current grass height by accumulating a calculated daily growth rate over the time elapsed since the last mow. It is configured once via the UI config flow, runs a polling coordinator every 12 hours to refresh external data, and exposes **ten sensor entities**, **four binary sensors**, a **switch**, **two buttons**, and a `mark_mowed` service.

---

## Entities

### Sensors

| Entity | Unit | Description |
|---|---|---|
| `sensor.current_grass_height` | in | Estimated current grass height |
| `sensor.daily_growth_rate` | in/day | Fully computed daily growth rate (all active factors applied) |
| `sensor.days_since_last_mow` | d | Fractional days elapsed since the last mow |
| `sensor.growth_since_mow` | in | Grass growth above the mowed-to height since the last mow (compared against normal growth trigger and force-mow threshold) |
| `sensor.next_dry_mow_window` | timestamp | Start time of the next forecasted dry window long enough for a full mow cycle; `unknown` if none found in the lookahead period |
| `sensor.growing_degree_days` | °F·d | Today's GDD (avg temp − 50 °F base, floored at 0) |
| `sensor.rainfall` | in | Today's precipitation from OpenWeatherMap |
| `sensor.soil_moisture` | % | Volumetric soil moisture from National Soil Moisture Network |
| `sensor.soil_temperature` | °F | 2-inch soil temperature from the nearest USDA SCAN station |
| `sensor.season_factor` | *(dimensionless)* | Current month's seasonal growth multiplier (0.30 – 1.50) |

All sensors share the same **Grass Growth Predictor** device and update together on the 12-hour coordinator cycle.

### Binary Sensors

| Entity | Device class | Description |
|---|---|---|
| `binary_sensor.mow_recommended` | — | `ON` per wet-grass scheduling logic: always ON when overdue or force threshold exceeded; ON when normal trigger + dry; ON when normal trigger + wet + no dry window in lookahead |
| `binary_sensor.mow_overdue` | `problem` | `ON` when `days_since_mow ≥ max_days_between_mows` regardless of height or wet state |
| `binary_sensor.grass_wet` | `moisture` | `ON` when rainfall ≥ wet rain threshold OR current humidity ≥ wet humidity threshold |
| `binary_sensor.dry_mow_window_soon` | — | `ON` when a contiguous dry window ≥ `mow_cycle_duration_hours` exists within the hourly forecast lookahead |

### Switch

| Entity | Description |
|---|---|
| `switch.mow_session_active` | Output that represents an in-progress mow session. Turn ON to dispatch/notify; turn OFF to cancel. State is persisted across restarts. |

### Buttons

| Entity | Description |
|---|---|
| `button.mark_mowed` | Records an ad-hoc manual mow; no session interaction. |
| `button.mow_complete` | Records a completed automated mow *and* turns off `switch.mow_session_active`. |

---

## Component Diagram

```mermaid
flowchart TD
    subgraph HA["Home Assistant"]
        CF["Config Flow\n(config_flow.py)\nUI setup & options"]
        INIT["__init__.py\nasync_setup_entry\nservice registration"]
        COORD["GrassGrowthCoordinator\n(coordinator.py)\npoll every 12 h"]
        SENSOR["Sensor entities\n(sensor.py)\nCoordinatorEntity"]
        BSENSOR["Binary sensor entities\n(binary_sensor.py)\nCoordinatorEntity"]
        SWITCH["MowSessionSwitch\n(switch.py)\nCoordinatorEntity"]
        BUTTON["MarkMowedButton · MowCompleteButton\n(button.py)\nCoordinatorEntity"]
        STORE[("HA Storage\n.storage/grass_growth_predictor")]
        SVC["Service: grass_growth_predictor.mark_mowed\noptional mowed_to_height (in)"]
    end

    subgraph EXTERNAL["External APIs (fetched every 12 h)"]
        OWM["OpenWeatherMap\nOne Call API 3.0\nGDD · rainfall"]
        NSM["National Soil Moisture Network\nVolumetric soil moisture %"]
        SCAN["USDA SCAN REST API\nNearby station lookup\n2-inch soil temperature"]
    end

    CF -->|"stores config & options"| INIT
    INIT -->|"creates"| COORD
    INIT -->|"registers"| SVC
    COORD -->|"subscribes"| SENSOR
    COORD -->|"subscribes"| BSENSOR
    COORD -->|"subscribes"| SWITCH
    COORD -->|"subscribes"| BUTTON
    COORD <-->|"persist weather cache\nlast mow timestamp\nmowed-to height\nmow session state"| STORE
    COORD -->|"fetch if TTL elapsed"| OWM
    COORD -->|"fetch if TTL elapsed"| NSM
    COORD -->|"resolve once, then fetch"| SCAN
    SVC -->|"async_mark_mowed()\nthen async_refresh()"| COORD
    SWITCH -->|"async_start/end_mow_session()"| COORD
    BUTTON -->|"async_mark_mowed() or async_complete_mow()"| COORD
```

---

## Data Flow

```mermaid
sequenceDiagram
    participant HA as Home Assistant
    participant Coord as GrassGrowthCoordinator
    participant OWM as OpenWeatherMap 3.0
    participant NSM as Natl Soil Moisture
    participant SCAN as USDA SCAN
    participant Store as HA Storage

    HA->>Coord: async_setup_entry()
    Coord->>Store: load persisted data\n(last mow, weather cache, fetched_at)
    Coord->>HA: async_config_entry_first_refresh()

    loop Every 12 hours
        HA->>Coord: _async_update_data()
        alt weather TTL elapsed
            Coord->>OWM: GET /data/3.0/onecall\n(lat, lon, units=imperial, exclude=current,minutely,alerts)
            OWM-->>Coord: daily[0].temp.max/min → GDD\ndaily[0].rain → rainfall (mm→in)\nhourly[0..47] → {dt, rain_1h, humidity, pop} (mm→in per slot)
            Coord->>Store: persist weather_data + hourly_forecast + weather_fetched_at
        end
        alt soil moisture TTL elapsed
            Coord->>NSM: GET moisture at depth=5 cm
            NSM-->>Coord: volumetric soil moisture %
        end
        alt soil temp TTL elapsed
            Coord->>SCAN: GET nearest station (radius 200 mi, once)
            SCAN-->>Coord: stationTriplet
            Coord->>SCAN: GET STO element, 2-inch depth, daily
            SCAN-->>Coord: soil temperature °F
        end
        Coord->>Coord: _compute()
    end

    participant User as User / Automation
    User->>HA: call grass_growth_predictor.mark_mowed
    HA->>Coord: async_mark_mowed(mowed_to_height)
    Coord->>Store: persist last_mow_timestamp + mowed_to_height
    Coord->>Coord: async_refresh() → _compute()

    note over User,Coord: Automated mower workflow
    User->>HA: turn on switch.mow_session_active
    HA->>Coord: async_start_mow_session()
    Coord->>Store: persist mow_session_active = true
    note over User: Mowing occurs
    User->>HA: press button.mow_complete
    HA->>Coord: async_complete_mow(mowed_to_height)
    Coord->>Store: persist last_mow_timestamp + mow_session_active = false
    Coord->>Coord: async_refresh() → _compute()
```

---

## Growth Model

```mermaid
flowchart LR
    BR["Base growth rate\n(in/day, user-configured)"]
    SF["Season factor\n(monthly multiplier\n0.30 – 1.50)"]
    GF["GDD factor\n(0.05 – 2.0)\n= GDD / 20"]
    RF["Rain factor\n(0.8 – 1.5)\n= 1 + rainfall × 0.25"]
    MF["Soil moisture factor\n(0.05 – 1.0)"]
    TF["Soil temp factor\n(0.05 – 1.0)"]

    BR --> MULT["daily_rate =\nbase × season × GDD × rain\n× soil_moisture × soil_temp"]
    SF --> MULT
    GF --> MULT
    RF --> MULT
    MF --> MULT
    TF --> MULT

    MULT --> HEIGHT["current_height =\nmowed_to_height\n+ days_since_mow × daily_rate"]
```

Each multiplier can be individually **enabled or disabled** via integration options. Disabled factors default to `1.0` (no effect).

### Height Formula

```
current_height = mowed_to_height + days_since_mow × daily_rate

daily_rate = base_rate
           × season_factor   (0.30 – 1.50, by month)
           × gdd_factor      (0.05 – 2.0,  GDD / 20)
           × rain_factor     (0.80 – 1.50, 1 + rainfall_in × 0.25)
           × soil_moisture   (0.05 – 1.0,  piecewise by %)
           × soil_temp       (0.05 – 1.0,  piecewise by °F)
```

---

## Update Intervals

| Data source | Fetch interval | Notes |
|---|---|---|
| OpenWeatherMap One Call 3.0 (GDD + rainfall) | 12 hours | Cached to storage; survives HA restarts |
| National Soil Moisture Network (soil moisture %) | 12 hours | In-memory cache only |
| USDA SCAN (2-inch soil temperature) | 12 hours | Station triplet resolved once, then cached in memory |
| Height calculation (coordinator poll) | 12 hours | Pure computation — no network call |

---

## Persistence

| Key | What is stored |
|---|---|
| `last_mow_timestamp` | ISO timestamp of the most recent mow event |
| `mowed_to_height` | Height the grass was cut to (inches) |
| `mow_session_active` | Boolean — whether an automated mow session is in progress |
| `weather_fetched_at` | ISO timestamp of last OWM fetch (prevents extra API calls on restart) |
| `weather_data` | Cached `{gdd, rainfall}` from the last successful OWM response |
| `hourly_forecast` | Cached list of reduced hourly slots `{dt, rain_1h, humidity, pop}` from the last successful OWM response |

All data is written to HA's built-in `.storage/` mechanism and survives restarts.

---

## Configuration Options

| Option | Description | Default |
|---|---|---|
| Latitude / Longitude | Location for all API lookups | HA location |
| OWM API Key | OpenWeatherMap One Call 3.0 key | — |
| Mowed to height | Starting height after a mow (in) | 3.0 in |
| Base growth rate | Daily growth rate ceiling (in/day) | 0.15 in/day |
| Enable seasonal | Apply monthly growth multiplier | ✓ |
| Enable GDD | Scale by growing degree days | ✓ |
| Enable rain | Scale by daily rainfall | ✓ |
| Enable soil moisture | Scale by volumetric soil moisture | ✓ |
| Enable soil temp | Scale by 2-inch soil temperature | ✓ |
| Minimum days between mows | Lower day bound — `mow_recommended` will not fire before this | 3 days |
| Maximum days between mows | Upper day bound — `mow_overdue` fires here regardless of height | 10 days |
| Normal growth trigger | Growth above mowed-to height (in) that triggers normal mow scheduling; dry window preferred | 0.5 in |
| Force-mow growth threshold | Growth above mowed-to height (in) that forces a mow regardless of wet conditions | 1.0 in |
| Mow cycle duration | How long the automated mower takes to complete one full cycle (hours) | 12.0 h |
| Wet rain threshold | Today's accumulated rainfall (in) above which grass is considered wet | 0.1 in |
| Wet humidity threshold | Current humidity (%) above which grass is considered wet from dew/overnight moisture | 85% |
| Dry window lookahead | Hours of hourly forecast to scan for a dry mow window; falls back to mowing anyway | 48 h |

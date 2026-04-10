# Grass Growth Predictor

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/seanmahrt/hacs_grass_estimator?style=for-the-badge)](https://github.com/seanmahrt/hacs_grass_estimator/releases)
[![License](https://img.shields.io/github/license/seanmahrt/hacs_grass_estimator?style=for-the-badge)](LICENSE)
[![HA Min Version](https://img.shields.io/badge/Home%20Assistant-2024.1.0%2B-blue?style=for-the-badge)](https://www.home-assistant.io/)

A Home Assistant custom integration that estimates your current grass height based on the time since your last mow, local weather data, soil conditions, and seasonal patterns.

---

## Features

| Feature | Description |
|---|---|
| **Height tracking** | Estimates grass height in inches since the last mow |
| **Growing Degree Days** | Uses OpenWeatherMap to compute GDD-based growth acceleration |
| **Rainfall factor** | Precipitation data boosts the daily growth rate |
| **Soil moisture factor** | National Soil Moisture Network API adjusts growth for wet/dry soil |
| **Soil temperature factor** | Nearest USDA SCAN station soil temperature scales growth |
| **Seasonal factor** | Month-based multiplier tuned for Northern Hemisphere cool-season turf |
| **Toggle multipliers** | Each factor can be individually enabled or disabled |
| **Automated mower control** | Switch output to trigger a mow session, binary sensors for recommended/overdue status, growth-based trigger with configurable min/max day bounds and growth thresholds |
| **Wet-grass scheduling** | Skips mowing when grass is wet (recent rainfall or high humidity/dew). A configurable force-mow threshold overrides the wet check when the grass has grown too long. A dry-window lookahead scans the 48-hour hourly forecast to find a suitable mow window before falling back to mowing anyway. |

---

## Installation

### Via HACS (Recommended)

1. Open **HACS → Integrations** in Home Assistant.
2. Click the three-dot menu → **Custom repositories**.
3. Add `https://github.com/seanmahrt/hacs_grass_estimator` with category **Integration**.
4. Search for **Grass Growth Predictor** and click **Install**.
5. Restart Home Assistant.

### Manual

1. Download the [latest release](https://github.com/seanmahrt/hacs_grass_estimator/releases/latest).
2. Copy the `custom_components/grass_growth_predictor` folder into your
   `<config>/custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Grass Growth Predictor**.
3. Fill in the setup form:

| Field | Description | Default |
|---|---|---|
| **Latitude** | Location latitude | HA configured latitude |
| **Longitude** | Location longitude | HA configured longitude |
| **OpenWeatherMap API Key** | Free key from [openweathermap.org](https://openweathermap.org/api) | — |
| **Mowed-To Height (in)** | Height the grass was last cut to | `3.0` |
| **Base Growth Rate (in/day)** | Maximum daily growth under ideal conditions | `0.15` |
| **Enable Seasonal Factor** | Apply month-based growth multiplier | `true` |
| **Enable GDD Factor** | Apply growing degree day multiplier | `true` |
| **Enable Rainfall Factor** | Apply rainfall multiplier | `true` |
| **Enable Soil Moisture Factor** | Apply soil moisture multiplier | `true` |
| **Enable Soil Temperature Factor** | Apply soil temperature multiplier | `true` |
| **Minimum Days Between Mows** | Earliest day a growth-triggered mow can be recommended | `3` |
| **Maximum Days Between Mows** | Days after which "Mow Overdue" turns ON regardless of height | `10` |
| **Normal Growth Trigger (in)** | Growth above mowed-to height (inches) that starts looking for a dry window to mow | `0.5` |
| **Force-Mow Growth Threshold (in)** | Growth above mowed-to height (inches) that forces a mow regardless of wet conditions | `1.0` |
| **Mow Cycle Duration (hours)** | How long the automated mower takes to complete one cycle; used to find a contiguous dry window | `12.0` |
| **Wet Rain Threshold (in)** | Today's accumulated rainfall (inches) above which the grass is considered wet | `0.1` |
| **Wet Humidity Threshold (%)** | Current humidity (%) above which the grass is considered wet from dew or overnight moisture | `85` |
| **Dry Window Lookahead (hours)** | Hours of hourly forecast to scan for a dry mow window; if none found, mow anyway | `48` |

All options except location and API key can be changed later via **Configure** on the integration card.

---

## Entities

All entities appear under the **Grass Growth Predictor** device.

### Sensors

#### `sensor.current_grass_height`

Reports the estimated grass height in **inches**.

##### Attributes

| Attribute | Type | Description |
|---|---|---|
| `last_mow_timestamp` | ISO 8601 string | Date/time of the last recorded mow |
| `daily_growth_rate` | float (in/day) | Computed growth rate for today |
| `days_since_last_mow` | float | Fractional days since the last mow |
| `gdd` | float | Growing degree days for today (°F base 50) |
| `rainfall` | float (inches) | Precipitation for today |
| `soil_moisture` | float (%) | Volumetric soil moisture percentage |
| `soil_temperature` | float (°F) | 2-inch soil temperature from nearest SCAN station |
| `season_factor` | float | Current month's seasonal multiplier |
| `enabled_multipliers` | list[str] | Which factors are active |

#### Contributing factor sensors

Each input to the growth model is also exposed as its own sensor so you can monitor, graph, and use them in automations independently.

| Entity | Unit | Description |
|---|---|---|
| `sensor.daily_growth_rate` | in/day | Fully computed daily growth rate (all active factors applied) |
| `sensor.days_since_last_mow` | d | Fractional days elapsed since the last mow |
| `sensor.growth_since_mow` | in | Estimated grass growth above the mowed-to height since the last mow. Compared against the normal growth trigger and force-mow threshold to drive `mow_recommended`. |
| `sensor.next_dry_mow_window` | timestamp | Start time of the next forecasted dry window long enough to complete a full mow cycle, or `unknown` if none found in the lookahead period. |
| `sensor.growing_degree_days` | °F·d | Today's GDD (avg temp − 50 °F base, floored at 0) |
| `sensor.rainfall` | in | Today's precipitation from OpenWeatherMap |
| `sensor.soil_moisture` | % | Volumetric soil moisture from National Soil Moisture Network |
| `sensor.soil_temperature` | °F | 2-inch soil temperature from the nearest USDA SCAN station |
| `sensor.season_factor` | *(dimensionless)* | Current month's seasonal growth multiplier (0.30 – 1.50) |

### Binary Sensors

| Entity | Device class | Description |
|---|---|---|
| `binary_sensor.mow_recommended` | — | `ON` according to the wet-grass scheduling logic (see **Wet-Grass Scheduling** section below) |
| `binary_sensor.mow_overdue` | `problem` | `ON` when `days_since_mow ≥ max_days_between_mows` regardless of height or wet state |
| `binary_sensor.grass_wet` | `moisture` | `ON` when today's rainfall ≥ wet rain threshold **or** current humidity ≥ wet humidity threshold |
| `binary_sensor.dry_mow_window_soon` | — | `ON` when a dry window long enough to complete a full mow cycle exists within the lookahead period |

The min/max days act as hard bounds: `mow_recommended` will never fire before `min_days`, and always fires at `max_days`. Between those bounds, the grass growth estimate and wet-grass scheduling logic drive the trigger.

### Switch

#### `switch.mow_session_active`

Acts as the **output** to initiate an automated mowing session.

| State | Meaning |
|---|---|
| `ON` | A mow session is in progress (mower dispatched / notification sent) |
| `OFF` | No active session |

Turning the switch **OFF** cancels the session without recording a mow. To record the mow as completed, press the **Mow Complete** button instead.

### Buttons

| Entity | Description |
|---|---|
| `button.mark_mowed` | Manual mow record — resets the growth timer immediately. Use for ad-hoc mowing outside of an automated session. |
| `button.mow_complete` | Automated session completion — records the mow *and* deactivates the `mow_session_active` switch. |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full growth model and factor details.

---

## Service: `grass_growth_predictor.mark_mowed`

Call this service every time you mow manually. It resets the growth timer to now and optionally sets a new starting height. This service is independent of the automated session switch — it works whether or not a session is active.

### Parameters

| Parameter | Required | Type | Description |
|---|---|---|---|
| `mowed_to_height` | No | float (0.5 – 12.0) | Height cut to in inches. Defaults to the configured value. |

### Example YAML

```yaml
# Automation: record a mow via a button press
automation:
  - alias: "Record mowing event"
    trigger:
      - platform: state
        entity_id: input_button.mow_button
        to: ~
    action:
      - service: grass_growth_predictor.mark_mowed
        data:
          mowed_to_height: 3.0
```

```yaml
# Script: reset height to 2.5 inches
script:
  record_mow_2_5:
    alias: "Record mow at 2.5 in"
    sequence:
      - service: grass_growth_predictor.mark_mowed
        data:
          mowed_to_height: 2.5
```

```yaml
# Display in a Lovelace card
type: entities
title: Lawn Status
entities:
  - entity: sensor.current_grass_height
    name: Current Height
```

---

## Automated Mower Control

The integration supports a full automated mowing workflow while still allowing manual mow recording at any point.

### Workflow

```
[Mow Recommended ON] → send notification / queue session
       ↓
[User/automation turns ON switch.mow_session_active]
       ↓  (mowing happens)
[Press button.mow_complete  OR  call mark_mowed service]
       ↓
[Mow recorded, switch turns OFF, timer resets]
```

### Example automation: notify and auto-start on overdue

```yaml
automation:
  - alias: "Send mow notification when recommended"
    trigger:
      - platform: state
        entity_id: binary_sensor.mow_recommended
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Lawn needs mowing"
          message: "Grass is ready to mow. Tap to start a session."

  - alias: "Escalate when overdue"
    trigger:
      - platform: state
        entity_id: binary_sensor.mow_overdue
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.mow_session_active
      - service: notify.mobile_app_your_phone
        data:
          title: "Mowing overdue!"
          message: "Auto-starting mow session — confirm when done."
```

### Example automation: record completion

```yaml
automation:
  - alias: "Record mow when mower docks"
    trigger:
      - platform: state
        entity_id: sensor.robomow_status
        to: "docked"
    condition:
      - condition: state
        entity_id: switch.mow_session_active
        state: "on"
    action:
      - service: button.press
        target:
          entity_id: button.mow_complete
```

---

## Wet-Grass Scheduling

The integration avoids mowing wet grass by checking rainfall and humidity from the OpenWeatherMap hourly forecast. A force-mow threshold ensures the mower never delays indefinitely.

### `mow_recommended` logic

```
mow_overdue    = days_since_mow ≥ max_days          ← always fires (ignores wet state)
force_mow      = growth_since_mow ≥ 1.0 in          ← always fires (ignores wet state)
days_ok        = days_since_mow ≥ min_days
normal_trigger = days_ok AND growth_since_mow ≥ 0.5 in

mow_recommended = mow_overdue
               OR force_mow
               OR (normal_trigger AND NOT grass_wet)
               OR (normal_trigger AND grass_wet AND NOT dry_window_soon)
```

The last condition ensures the mower still runs when the grass has grown enough but no dry window is forecast within the lookahead period — preventing indefinite postponement during prolonged wet weather.

### Wet state detection

| Condition | Source |
|---|---|
| `rainfall ≥ wet_rain_threshold_in` | Today's accumulated precipitation from OWM daily forecast (mm → inches) |
| `current_humidity ≥ wet_humidity_pct` | Humidity from the most recent OWM hourly slot |

Either condition alone makes `binary_sensor.grass_wet` turn `ON`.

### Dry-window detection

Each hourly slot is tested against three internal thresholds:

| Slot criterion | Value |
|---|---|
| Rain per hour | ≤ 0.04 in (~1 mm) |
| Precipitation probability | ≤ 30% |
| Relative humidity | < `wet_humidity_pct` |

The integration looks for a contiguous run of qualifying hours equal to `mow_cycle_duration_hours`. The start time of the first such window is returned as `sensor.next_dry_mow_window`.

### Example automation: wait for a dry window

```yaml
automation:
  - alias: "Start mower when dry window arrives"
    trigger:
      - platform: state
        entity_id: binary_sensor.dry_mow_window_soon
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.mow_recommended
        state: "on"
      - condition: state
        entity_id: binary_sensor.grass_wet
        state: "off"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.mow_session_active
```

---

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Component diagrams, data-flow sequence, growth model formula, update intervals |
| [CHANGELOG.md](CHANGELOG.md) | Version history and release notes |

---

## License

[MIT](LICENSE)

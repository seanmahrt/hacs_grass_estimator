# Grass Growth Predictor

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/seanmahrt/hacs_grass_estimator?style=for-the-badge)](https://github.com/seanmahrt/hacs_grass_estimator/releases)
[![License](https://img.shields.io/github/license/seanmahrt/hacs_grass_estimator?style=for-the-badge)](LICENSE)
[![HA Min Version](https://img.shields.io/badge/Home%20Assistant-2024.1.0%2B-blue?style=for-the-badge)](https://www.home-assistant.io/)

A Home Assistant custom integration that estimates your current grass height based on the time since your last mow, local weather data, soil conditions, and seasonal patterns.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Via HACS (Recommended)](#via-hacs-recommended)
  - [Manual](#manual)
- [Configuration](#configuration)
- [How to Use](#how-to-use)
  - [Inputs](#inputs--tell-the-integration-what-happened)
  - [Outputs](#outputs--react-to-what-the-integration-tells-you)
  - [Wiring Guide](#wiring-guide--recommended-setup)
    - [1. Manual-only household](#1-manual-only-household-no-robot-mower)
    - [2. Robot mower — notify and wait](#2-robot-mower--notify-and-wait-for-dry-conditions)
    - [3. Robot mower — schedule at dry window](#3-robot-mower--schedule-at-the-next-dry-window)
    - [4. Mow-overdue escalation](#4-mow-overdue-escalation)
    - [5. Dashboard card](#5-dashboard-card)
  - [Sensors](#sensors)
  - [Binary Sensors](#binary-sensors)
  - [Switch](#switch)
  - [Buttons](#buttons)
- [Service: mark\_mowed](#service-grass_growth_predictor-mark_mowed)
- [Automated Mower Control](#automated-mower-control)
  - [Workflow](#workflow)
  - [Example: notify and auto-start on overdue](#example-automation-notify-and-auto-start-on-overdue)
  - [Example: record completion](#example-automation-record-completion)
- [Wet-Grass Scheduling](#wet-grass-scheduling)
  - [`mow_recommended` logic](#mow_recommended-logic)
  - [Wet state detection](#wet-state-detection)
  - [Dry-window detection](#dry-window-detection)
  - [Example: wait for a dry window](#example-automation-wait-for-a-dry-window)
- [Documentation](#documentation)
- [License](#license)

---

## Features

| Feature | Description |
|---|---|
| **Height tracking** | Estimates grass height in inches since the last mow |
| **Growing Degree Days** | Reads daily high/low temperature from the HA weather entity to compute GDD-based growth acceleration |
| **Rainfall factor** | Today's precipitation from the HA weather entity boosts the daily growth rate |
| **Soil moisture factor** | National Soil Moisture Network API adjusts growth for wet/dry soil |
| **Soil temperature factor** | Nearest USDA SCAN station soil temperature scales growth, using the USDA AWDB `elements` API and preferring the 2-inch depth with fallback to the nearest reported depth |
| **Seasonal factor** | Month-based multiplier tuned for Northern Hemisphere cool-season turf |
| **Toggle multipliers** | Each factor can be individually enabled or disabled |
| **Upstream outage notifications** | Creates a Home Assistant persistent notification the first time a weather, soil moisture, or SCAN fetch fails, and clears it automatically after recovery |
| **Automated mower control** | Switch output to trigger a mow session, binary sensors for recommended/overdue status, growth-based trigger with configurable min/max day bounds and growth thresholds |
| **Wet-grass scheduling** | Skips mowing when grass is wet (recent rainfall or high humidity/dew from the HA weather entity hourly forecast). A configurable force-mow threshold overrides the wet check when the grass has grown too long. A dry-window lookahead scans the hourly forecast to find a suitable mow window before falling back to mowing anyway. |

---

## Prerequisites

This integration reads weather data from an existing HA weather entity rather than making its own API calls. You need a weather integration that provides **daily and hourly forecasts** — the official [OpenWeatherMap integration](https://www.home-assistant.io/integrations/openweathermap/) is recommended.

1. Install the **OpenWeatherMap** integration (or another weather integration with hourly forecast support).
2. Note the entity ID it creates (typically `weather.openweathermap`).
3. Then install and configure Grass Growth Predictor.

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
| **Weather Entity** | The HA weather entity to read forecasts from (e.g. `weather.openweathermap`). Must support daily and hourly forecasts. | `weather.openweathermap` |
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

## How to Use

This section describes how each input and output entity is intended to be connected in a real Home Assistant setup.

### Inputs — tell the integration what happened

| Entity / Service | When to call it | How |
|---|---|---|
| `button.mark_mowed` | Mowed manually outside of an automated session | Press the button in the UI, or trigger it from an automation/script |
| `button.mow_complete` | Automated mower finished a dispatched session | Call `button.press` targeting this button (e.g. when your mower docks or reports idle) |
| `grass_growth_predictor.mark_mowed` | Any mow event — also accepts an optional height override | Call the service from an automation, script, or the Developer Tools → Services panel |
| `switch.mow_session_active` turned **ON** | You have decided to start a mow session | Turn on via an automation or the UI; signals the mower is running so the integration tracks the active session |
| `switch.mow_session_active` turned **OFF** | Cancel a session _without_ recording a mow | Turn off via an automation or the UI; resets session state but does not reset the growth timer |

### Outputs — react to what the integration tells you

| Entity | Meaning | Typical automation response |
|---|---|---|
| `binary_sensor.mow_recommended` | Conditions are right to mow (growth threshold met + either dry or no dry window coming) | Send a push notification; turn on a dashboard indicator; trigger a mower dispatch |
| `binary_sensor.mow_overdue` | Max days exceeded regardless of growth or wet state | Escalate: force-start the mower and send an urgent alert |
| `binary_sensor.grass_wet` | Current conditions are too wet to mow | Suppress mow-start automations; optionally notify |
| `binary_sensor.mow_not_advised` | Currently wet **or** any forecast hour within the mow cycle window is rainy/humid — single go/no-go for manual mowing | Block manual mow start; display a warning on a dashboard |
| `binary_sensor.dry_mow_window_soon` | A dry window long enough for a full mow cycle is coming | Schedule the mower to start at `sensor.next_dry_mow_window` |
| `sensor.next_dry_mow_window` | Timestamp of the next suitable dry window | Use in a `time` trigger or `template` trigger to start the mower at precisely the right time |
| `sensor.current_grass_height` | Estimated current height in inches | Display on a dashboard; use in a condition to guard other automations |
| `sensor.growth_since_last_mow` | Inches of growth since the last mow | Display on a dashboard; useful for fine-tuning threshold options |

### Wiring guide — recommended setup

#### 1. Manual-only household (no robot mower)

Connect your physical mow button (e.g. an `input_button` helper) to the `mark_mowed` service, and put `binary_sensor.mow_recommended` on a dashboard card so you know when it's time to mow.

```yaml
automation:
  - alias: "Record manual mow"
    trigger:
      - platform: state
        entity_id: input_button.mow_button
        to: ~
    action:
      - service: grass_growth_predictor.mark_mowed
        data:
          mowed_to_height: 3.0
```

#### 2. Robot mower — notify and wait for dry conditions

The mower is dispatched only when `mow_recommended` is ON and the grass is currently dry. If the grass is wet, the integration will still set `mow_recommended` once no dry window is in the forecast — so the mower is never blocked indefinitely.

```yaml
automation:
  - alias: "Dispatch robot mower when recommended and dry"
    trigger:
      - platform: state
        entity_id: binary_sensor.mow_recommended
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.grass_wet
        state: "off"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.mow_session_active
      # Replace with your mower's actual start service:
      - service: vacuum.start
        target:
          entity_id: vacuum.lawn_mower

  - alias: "Record mow when robot mower docks"
    trigger:
      - platform: state
        entity_id: sensor.lawn_mower_status
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

#### 3. Robot mower — schedule at the next dry window

Use `sensor.next_dry_mow_window` to kick off the mower at the precise start of the next suitable dry period.

```yaml
automation:
  - alias: "Start mower at next dry window"
    trigger:
      - platform: template
        value_template: >
          {{ now() >= states('sensor.next_dry_mow_window') | as_datetime
             and is_state('binary_sensor.mow_recommended', 'on') }}
    condition:
      - condition: state
        entity_id: binary_sensor.grass_wet
        state: "off"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.mow_session_active
      - service: vacuum.start
        target:
          entity_id: vacuum.lawn_mower
```

#### 4. Mow-overdue escalation

When the hard upper day limit is reached, override any wet-grass delay and alert the household.

```yaml
automation:
  - alias: "Escalate when mow is overdue"
    trigger:
      - platform: state
        entity_id: binary_sensor.mow_overdue
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Mow overdue!"
          message: >
            Lawn has not been mowed in over
            {{ states('sensor.days_since_last_mow') | round(0) }} days.
            Starting mower now.
      - service: switch.turn_on
        target:
          entity_id: switch.mow_session_active
      - service: vacuum.start
        target:
          entity_id: vacuum.lawn_mower
```

#### 5. Dashboard card

A simple entities card to keep all relevant sensors visible at a glance.

```yaml
type: entities
title: Lawn Status
entities:
  - entity: sensor.current_grass_height
    name: Current Height
  - entity: sensor.growth_since_last_mow
    name: Growth Since Mow
  - entity: sensor.days_since_last_mow
    name: Days Since Mow
  - entity: binary_sensor.mow_recommended
    name: Mow Recommended
  - entity: binary_sensor.mow_overdue
    name: Mow Overdue
  - entity: binary_sensor.grass_wet
    name: Grass Wet
  - entity: binary_sensor.mow_not_advised
    name: Mow Not Advised
  - entity: binary_sensor.dry_mow_window_soon
    name: Dry Window Soon
  - entity: sensor.next_dry_mow_window
    name: Next Dry Window
  - entity: switch.mow_session_active
    name: Mow Session Active
```



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
| `sensor.growth_since_last_mow` | in | Estimated grass growth above the mowed-to height since the last mow. Compared against the normal growth trigger and force-mow threshold to drive `mow_recommended`. |
| `sensor.next_dry_mow_window` | timestamp | Start time of the next forecasted dry window long enough to complete a full mow cycle, or `unknown` if none found in the lookahead period. |
| `sensor.growing_degree_days` | °F·d | Today's GDD (avg temp − 50 °F base, floored at 0) |
| `sensor.rainfall` | in | Today's total forecast precipitation from the weather entity (full-day total; drives the rain growth multiplier). Attributes expose `past_rainfall_in` (rain already fallen, used for wet-grass detection) and `current_surface_moisture_in` |
| `sensor.soil_moisture` | % | Volumetric soil moisture from National Soil Moisture Network |
| `sensor.soil_temperature` | °F | 2-inch soil temperature from the nearest USDA SCAN station |
| `sensor.season_factor` | *(dimensionless)* | Current month's seasonal growth multiplier (0.30 – 1.50) |

### Binary Sensors

| Entity | Device class | Description |
|---|---|---|
| `binary_sensor.mow_recommended` | — | `ON` according to the wet-grass scheduling logic (see **Wet-Grass Scheduling** section below) |
| `binary_sensor.mow_overdue` | `problem` | `ON` when `days_since_mow ≥ max_days_between_mows` regardless of height or wet state |
| `binary_sensor.grass_wet` | `moisture` | `ON` when past rainfall (rain already fallen today) minus estimated evaporation ≥ wet rain threshold **or** current humidity ≥ wet humidity threshold |
| `binary_sensor.mow_not_advised` | — | `ON` when the grass is currently wet **or** any hourly forecast slot within the next `mow_cycle_duration_hours` hours is rainy or humid. Use this as a single go/no-go indicator when mowing manually. |
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

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full growth model factor tables and mow scheduling logic details.

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
| `past_rainfall_in − evaporated ≥ wet_rain_threshold_in` | Sum of precipitation from hourly slots whose datetime is in the past (**not** the full-day forecast total, which would include tonight's forecast rain). Evaporation since dawn is subtracted using current temperature/wind/cloud/humidity conditions. |
| `current_humidity ≥ wet_humidity_pct` | Humidity from the most recent HA weather entity hourly forecast slot; falls back to the live `humidity` attribute if no hourly slots are available |

Using past-only rainfall means a forecast of heavy rain tonight will not mark the grass as wet at 9 AM.

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

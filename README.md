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

All options except location and API key can be changed later via **Configure** on the integration card.

---

## Sensor: `sensor.current_grass_height`

Reports the estimated grass height in **inches**.

### Attributes

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

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full growth model and factor details.

---

## Service: `grass_growth_predictor.mark_mowed`

Call this service every time you mow. It resets the growth timer to now and optionally sets a new starting height.

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

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Component diagrams, data-flow sequence, growth model formula, update intervals |
| [CHANGELOG.md](CHANGELOG.md) | Version history and release notes |

---

## License

[MIT](LICENSE)

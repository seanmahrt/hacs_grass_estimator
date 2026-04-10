# Changelog

All notable changes to Grass Growth Predictor are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- **Automated mower control** — new entities for managing a mowing session workflow:
  - `switch.mow_session_active` — output switch to initiate a mow session (dispatch a mower, send a push notification, etc.). Persisted to storage so state survives restarts.
  - `binary_sensor.mow_recommended` — turns `ON` when `days_since_mow ≥ min_days` **AND** `growth_since_mow ≥ max_growth_between_mows`, or when `mow_overdue` is ON. Min/max days act as hard lower/upper bounds; growth does the actual triggering between them.
  - `binary_sensor.mow_overdue` — turns `ON` when `days_since_mow ≥ max_days_between_mows` regardless of growth height. Exposed with `device_class: problem` for dashboard alerting.
  - `button.mow_complete` — records a completed automated mow *and* deactivates `switch.mow_session_active` in a single action.
  - `sensor.growth_since_mow` — reports estimated grass growth above the mowed-to height since the last mow (inches). This is the value compared against `max_growth_between_mows` to drive `mow_recommended`.
- **Minimum Days Between Mows** option (default 3) — lower day bound; `mow_recommended` will not fire before this.
- **Maximum Days Between Mows** option (default 10) — upper day bound; `mow_overdue` fires here regardless of height.
- **Maximum Growth Between Mows** option (default 1.5 in) — height growth above mowed-to height that triggers `mow_recommended` between the day bounds.
- `CONF_MIN_DAYS_BETWEEN_MOWS`, `CONF_MAX_DAYS_BETWEEN_MOWS`, `CONF_MAX_GROWTH_BETWEEN_MOWS` and their defaults in `const.py`.
- `SENSOR_GROWTH_SINCE_MOW`, `STORE_MOW_SESSION_ACTIVE`, `SWITCH_MOW_SESSION`, `BINARY_SENSOR_MOW_RECOMMENDED`, `BINARY_SENSOR_MOW_OVERDUE`, `BUTTON_MOW_COMPLETE` constants in `const.py`.
- `switch.py` and `binary_sensor.py` platform modules.
- `async_start_mow_session()`, `async_end_mow_session()`, and `async_complete_mow()` coordinator methods.
- `mow_session_active` property on `GrassGrowthCoordinator`.
- `binary_sensor` and `switch` added to the `PLATFORMS` list in `__init__.py`.
- New options fields (`min_days_between_mows`, `max_days_between_mows`, `max_growth_between_mows`) in the options flow and translation strings.

### Note
The existing `button.mark_mowed` button and `grass_growth_predictor.mark_mowed` service are **unchanged** — manual mow recording works exactly as before, independent of the session switch.

---

## [1.2.0] — 2026-04-06

### Added
- Seven new sensor entities exposing each growth model input as a first-class HA sensor: **Daily Growth Rate** (in/day), **Days Since Last Mow** (d), **Growing Degree Days** (°F·d), **Rainfall** (in), **Soil Moisture** (%), **Soil Temperature** (°F), and **Season Factor** (dimensionless). All sensors share the Grass Growth Predictor device and update on the same 12-hour coordinator cycle.
- `SENSOR_DAILY_GROWTH_RATE`, `SENSOR_DAYS_SINCE_MOW`, `SENSOR_GDD`, `SENSOR_RAINFALL`, `SENSOR_SOIL_MOISTURE`, `SENSOR_SOIL_TEMPERATURE`, `SENSOR_SEASON_FACTOR` constants added to `const.py`.
- Shared `_GrassBaseSensor` base class in `sensor.py` to reduce boilerplate across sensor entities.

---

## [1.1.0] — 2026-04-06

### Fixed
- **Internal error 500 on options dialog**: `OptionsFlow.__init__` was passing `config_entry` to the base class, which HA 2024.x+ sets automatically. Removed the override so the gear icon opens correctly.
- **Integration failed to load** (`ImportError`): `sensor.py` imported `ATTR_ENABLED_MULTIPLIERS`, `ATTR_SEASON_FACTOR`, `ATTR_SOIL_MOISTURE`, and `ATTR_SOIL_TEMPERATURE` from `const.py` but they were never defined there.

### Changed
- `config_flow.py`: Return type updated from deprecated `FlowResult` to `ConfigFlowResult` for both the config flow and options flow steps.
- `sensor.py` / `button.py`: `device_info` now returns a typed `DeviceInfo` object with `DeviceEntryType.SERVICE` instead of a raw `dict` with a plain string.
- `button.py`: `MarkMowedButton` now extends `CoordinatorEntity` for proper availability tracking when the coordinator is unavailable.
- `manifest.json`: Bumped version to `1.1.0`; added explicit `homeassistant` minimum version (`>=2024.1.0`).

### Added
- `ATTR_ENABLED_MULTIPLIERS`, `ATTR_SEASON_FACTOR`, `ATTR_SOIL_MOISTURE`, `ATTR_SOIL_TEMPERATURE` added to `const.py`.

---

## [1.0.0] — 2026-04-06

### Added
- Initial release.
- `sensor.current_grass_height` entity reporting estimated grass height in inches.
- `grass_growth_predictor.mark_mowed` service to reset the growth timer.
- Growth model with five toggleable multipliers: seasonal, GDD, rainfall, soil moisture, soil temperature.
- Data sourced from OpenWeatherMap One Call API, National Soil Moisture Network, and USDA SCAN stations.
- Full UI config flow with options editing.
- Persistent storage of last mow timestamp and mowed-to height.

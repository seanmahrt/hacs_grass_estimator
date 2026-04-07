# Changelog

All notable changes to Grass Growth Predictor are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

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

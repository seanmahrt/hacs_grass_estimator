# Changelog

All notable changes to Grass Growth Predictor are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Changed
- Upgraded OpenWeatherMap endpoint from One Call **2.5** to One Call **3.0** pay-per-call API.
- All data sources (weather, soil moisture, soil temperature) now refresh every **12 hours** instead of the previous mixed 1 h / 3 h / 6 h schedule.
- Coordinator poll interval aligned to 12 hours.

### Added
- Weather data (`gdd`, `rainfall`) and the fetch timestamp are now **persisted to HA storage** so a Home Assistant restart does not trigger an unnecessary OpenWeatherMap API call if the 12-hour TTL has not elapsed.
- `ARCHITECTURE.md` — Mermaid diagrams covering component layout, data-flow sequence, and the growth model.
- `CHANGELOG.md` — this file.

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

# Changelog

All notable changes to Grass Growth Predictor are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## Versions

- [Unreleased](#unreleased)
- [1.5.0](#150)
- [1.4.1](#141)
- [1.4.0](#140)
- [1.3.0](#130)
- [1.2.0](#120--2026-04-06)
- [1.1.0](#110--2026-04-06)
- [1.0.0](#100--2026-04-06)

---

## [Unreleased]

### Fixed
- **Documentation: entity references updated to match HA display names** — `sensor.growth_since_mow` corrected to `sensor.growth_since_last_mow` throughout README and ARCHITECTURE (entity `_attr_name` is "Growth Since Last Mow"). Added missing `binary_sensor.mow_not_advised` to the README Outputs quick-reference table.
- **`Mow Not Advised` / `Grass Wet` stuck ON due to future-rain attribution** — `current_moisture_in` was previously computed from the daily forecast total (including rain forecast for later today/tonight). It now uses only `past_rainfall_in`: the sum of precipitation from hourly forecast slots whose datetime is already in the past. This prevents a heavy evening forecast from marking the grass as wet all morning.
- **`Mark Mowed` left `Mow Session Active` switch ON** — `async_mark_mowed` now sets `mow_session_active = False` before saving, matching the behaviour of `async_complete_mow`. Both mow-recording paths clear the session unconditionally.

### Added
- **Hourly refresh aligned to :50 past each hour** — the coordinator no longer uses an interval-based auto-poll. Instead, `async_track_utc_time_change` (minute=50, second=0) drives all periodic refreshes. This guarantees sensor state is updated 10 minutes before each hourly forecast boundary, so dry-window automations that trigger at the top of the hour always see current data. The weather TTL is fixed at 55 minutes (down from `max(1 h, mow_cycle_h / 2)`) so every `:50` tick reliably fetches a fresh forecast. Manual refreshes (`mark_mowed`, `mow_complete`, options save) continue to work independently and still respect the 55 min weather TTL to avoid redundant API calls.

### Changed
- **Dynamic poll interval removed** — `_compute_poll_interval()` and its `update_interval` wiring have been removed. The mow cycle duration no longer affects the coordinator refresh rate.
- `_async_options_updated` simplified — no longer adjusts `update_interval`; just calls `async_refresh()`.
- `cancel_window_refresh` replaced by `cancel_hourly_schedule` (called on entry unload to deregister the `async_track_utc_time_change` listener).
- **Dynamic poll interval and weather TTL driven by Mow Cycle Duration** — superseded by the fixed hourly :50 schedule above; this entry is no longer applicable.
- **`past_rainfall_in` attribute on `sensor.rainfall`** — exposes the rain that has actually fallen today (summed from past hourly slots) alongside the full-day forecast total and current surface moisture estimate, making it easy to debug wet-grass state.
- **Comprehensive logging** — coordinator now logs at `INFO` level when mow events are recorded (including which caller, timestamp, and prior session state) and when weather data is fetched (GDD, daily precip, past rain, slot count, humidity). Debug-level logs cover wet-grass calculation inputs/outputs and every compute cycle result, enabling diagnosis without restarting HA.
- **`past_rainfall` key in coordinator return dict** — downstream entities and future attributes have direct access to past-only rainfall without re-summing hourly slots.

### Changed
- Button `Mark Mowed` docstring updated to clarify it is for manual mowing and now always clears any active session.
- Button `Mow Complete` docstring updated to clarify it is for the automated mowing workflow; both buttons are now safe to press regardless of session state.
- `sensor.rainfall` `extra_state_attributes` updated: exposes `past_rainfall_in` and `current_surface_moisture_in` to aid troubleshooting of `Grass Wet` / `Mow Not Advised` state.
- ARCHITECTURE.md updated: button table, Update Intervals table, evaporation/moisture description, and `grass_wet` source table all reflect the rainfall attribution fix.

---

## [1.5.0]

### Changed
- **Weather data now sourced from a HA weather entity** instead of direct OWM API calls. During setup, select any HA weather entity that provides daily and hourly forecasts (e.g. `weather.openweathermap`). The integration calls `weather.get_forecasts` on every coordinator poll to read GDD, rainfall, and per-hour humidity/precipitation — no OWM API key is needed in this integration.
- **Removed** `owm_api_key` configuration field and all direct HTTP calls to `api.openweathermap.org`.
- **Weather data no longer persisted to HA storage**; the weather entity handles its own caching and the integration reads fresh data on every 2-hour coordinator poll.
- `precipitation_probability` conversion: HA weather forecast reports this as 0–100 %; the internal dry-window logic expects 0–1, so the coordinator divides by 100 on read.
- Current humidity fallback: if no hourly forecast slots are available, the integration falls back to the `humidity` attribute of the weather entity's current state.

### Added
- `CONF_WEATHER_ENTITY = "weather_entity_id"` and `DEFAULT_WEATHER_ENTITY = "weather.openweathermap"` in `const.py`.
- Entity picker (HA `EntitySelector`, domain `weather`) in the config flow setup step.
- `entity_not_found` UI error message if the selected weather entity doesn't exist at setup time.

### Removed
- Stale `STORE_WEATHER_DATA`, `STORE_WEATHER_FETCHED_AT`, `STORE_HOURLY_FORECAST`, and `HEIGHT_UPDATE_INTERVAL` constants from `const.py`.

---

## [1.4.1]

### Added
- `binary_sensor.mow_not_advised` — single go/no-go indicator for **manual mowing**. `ON` when the grass is currently wet (`binary_sensor.grass_wet` is ON) **or** any hourly forecast slot within the next `mow_cycle_duration_hours` hours has significant rain (> 0.04 in), high precipitation probability (> 30%), or humidity above the wet threshold. The lookahead window uses the same cycle-duration setting as the dry-window search so both sensors are consistent.

### Changed
- **Coordinator poll interval reduced from 12 h to 2 h** so weather data is read more frequently. Soil data uses its own 12 h TTL and is unaffected.

---

## [1.4.0]

### Added
- Wet grass detection and dry mow window scheduling:
  - `binary_sensor.grass_wet` — `ON` when today's rainfall ≥ wet rain threshold **or** current hourly humidity ≥ wet humidity threshold. Device class `moisture`.
  - `binary_sensor.dry_mow_window_soon` — `ON` when a contiguous dry window long enough to complete a full mow cycle is found within the hourly forecast lookahead.
  - `sensor.next_dry_mow_window` — `SensorDeviceClass.TIMESTAMP` sensor reporting the start time of the next dry mow window, or `unknown` if none found.
- **Force-mow growth threshold** (`force_mow_growth_threshold`, default 1.0 in) — when `growth_since_mow` exceeds this value, mowing is triggered regardless of wet conditions.
- **Mow Cycle Duration** option (`mow_cycle_duration_hours`, default 12 h) — specifies how long the mower takes to complete one cycle; used to find a contiguous dry window.
- **Wet Rain Threshold** option (`wet_rain_threshold_in`, default 0.1 in) — today's accumulated rainfall above which the grass is considered wet.
- **Wet Humidity Threshold** option (`wet_humidity_pct`, default 85%) — current humidity above which the grass is considered wet from dew or overnight moisture.
- **Dry Window Lookahead** option (`dry_window_lookahead_hours`, default 48 h) — hours of hourly forecast to scan; falls back to mowing anyway if no window is found.
- `_find_dry_mow_window()` pure function in `coordinator.py` — finds the first contiguous run of qualifying hourly slots (rain ≤ 0.04 in, pop ≤ 30%, humidity < threshold).
- `CONF_FORCE_MOW_GROWTH_THRESHOLD`, `CONF_MOW_CYCLE_DURATION_HOURS`, `CONF_WET_RAIN_THRESHOLD_IN`, `CONF_WET_HUMIDITY_PCT`, `CONF_DRY_WINDOW_LOOKAHEAD_HOURS` and their defaults in `const.py`.

### Changed
- **`mow_recommended` logic** updated to a four-condition OR gate:
  1. `mow_overdue` (days ≥ max_days) — always fires, ignores wet state
  2. `force_mow` (growth ≥ force threshold) — always fires, ignores wet state
  3. `normal_trigger AND NOT grass_wet` — ideal case: grown enough, currently dry
  4. `normal_trigger AND grass_wet AND NOT dry_window_soon` — wet but no dry window coming → mow anyway to prevent indefinite delay
- **`max_growth_between_mows` default** revised from 1.5 in to **0.5 in** so the normal trigger fires below the force-mow threshold (logical ordering: 0.5 in → start looking for dry window; 1.0 in → force mow).

---

## [1.3.0]

### Added
- **Automated mower control** — new entities for managing a mowing session workflow:
  - `switch.mow_session_active` — output switch to initiate a mow session (dispatch a mower, send a push notification, etc.). Persisted to storage so state survives restarts.
  - `binary_sensor.mow_recommended` — turns `ON` when `days_since_mow ≥ min_days` **AND** `growth_since_mow ≥ max_growth_between_mows`, or when `mow_overdue` is ON. Min/max days act as hard lower/upper bounds; growth does the actual triggering between them.
  - `binary_sensor.mow_overdue` — turns `ON` when `days_since_mow ≥ max_days_between_mows` regardless of growth height. Exposed with `device_class: problem` for dashboard alerting.
  - `button.mow_complete` — records a completed automated mow *and* deactivates `switch.mow_session_active` in a single action.
  - `sensor.growth_since_mow` — reports estimated grass growth above the mowed-to height since the last mow (inches).
- **Minimum Days Between Mows** option (default 3) — lower day bound; `mow_recommended` will not fire before this.
- **Maximum Days Between Mows** option (default 10) — upper day bound; `mow_overdue` fires here regardless of height.
- **Maximum Growth Between Mows** option (default 1.5 in) — height growth above mowed-to height that triggers `mow_recommended` between the day bounds.
- `CONF_MIN_DAYS_BETWEEN_MOWS`, `CONF_MAX_DAYS_BETWEEN_MOWS`, `CONF_MAX_GROWTH_BETWEEN_MOWS` and their defaults in `const.py`.
- `switch.py` and `binary_sensor.py` platform modules.
- `async_start_mow_session()`, `async_end_mow_session()`, and `async_complete_mow()` coordinator methods.

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

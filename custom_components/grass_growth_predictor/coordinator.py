"""DataUpdateCoordinator for Grass Growth Predictor."""
from __future__ import annotations

import asyncio
import math
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    BINARY_SENSOR_DRY_MOW_WINDOW_SOON,
    BINARY_SENSOR_GRASS_WET,
    BINARY_SENSOR_MOW_NOT_ADVISED,
    BINARY_SENSOR_MOW_OVERDUE,
    BINARY_SENSOR_MOW_RECOMMENDED,
    CONF_BASE_GROWTH_RATE,
    CONF_DRY_WINDOW_LOOKAHEAD_HOURS,
    CONF_ENABLE_GDD,
    CONF_ENABLE_RAIN,
    CONF_ENABLE_SEASONAL,
    CONF_ENABLE_SOIL_MOISTURE,
    CONF_ENABLE_SOIL_TEMP,
    CONF_FORCE_MOW_GROWTH_THRESHOLD,
    CONF_MAX_DAYS_BETWEEN_MOWS,
    CONF_MAX_GROWTH_BETWEEN_MOWS,
    CONF_MIN_DAYS_BETWEEN_MOWS,
    CONF_MOW_CYCLE_DURATION_HOURS,
    CONF_MOWED_TO_HEIGHT,
    CONF_WEATHER_ENTITY,
    CONF_WET_HUMIDITY_PCT,
    CONF_WET_RAIN_THRESHOLD_IN,
    DEFAULT_BASE_GROWTH_RATE,
    DEFAULT_DRY_WINDOW_LOOKAHEAD_HOURS,
    DEFAULT_FORCE_MOW_GROWTH_THRESHOLD,
    DEFAULT_MAX_DAYS_BETWEEN_MOWS,
    DEFAULT_MAX_GROWTH_BETWEEN_MOWS,
    DEFAULT_MIN_DAYS_BETWEEN_MOWS,
    DEFAULT_MOW_CYCLE_DURATION_HOURS,
    DEFAULT_MOWED_TO_HEIGHT,
    DEFAULT_WEATHER_ENTITY,
    DEFAULT_WET_HUMIDITY_PCT,
    DEFAULT_WET_RAIN_THRESHOLD_IN,
    DOMAIN,
    GDD_BASE_TEMP_F,
    NSM_BASE_URL,
    OPTIMAL_GDD_DAILY,
    OPTIMAL_SOIL_MOISTURE_PCT,
    OPTIMAL_SOIL_TEMP_F,
    SCAN_DATA_URL,
    SCAN_STATIONS_URL,
    SEASON_FACTORS,
    SENSOR_NEXT_DRY_MOW_WINDOW,
    SOIL_UPDATE_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
    STORE_LAST_MOW_TIMESTAMP,
    STORE_MOW_SESSION_ACTIVE,
    STORE_MOWED_TO_HEIGHT,
)

_LOGGER = logging.getLogger(__name__)


class GrassGrowthCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage fetching and computing grass height data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._stored_data: dict[str, Any] = {}

        # Per-source cache
        self._weather_data: dict[str, Any] | None = None
        self._current_humidity: float = 0.0
        self._current_wind_mph: float = 0.0
        self._current_cloud_pct: float = 50.0
        self._current_temp_f: float = 70.0
        self._hourly_forecast: list[dict[str, Any]] = []  # reduced hourly slots from HA weather entity

        self._soil_moisture_data: dict[str, Any] | None = None
        self._soil_moisture_fetched_at: datetime | None = None

        self._soil_temp_data: dict[str, Any] | None = None
        self._soil_temp_fetched_at: datetime | None = None

        # Nearest SCAN station (resolved once, then cached)
        self._scan_station_triplet: str | None = None
        self._scan_station_resolved: bool = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Poll every 2 h — sufficient for mow-decision sensors; weather data
            # comes from the HA weather entity (no direct API rate limit to worry about).
            update_interval=timedelta(hours=2),
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def _cfg(self) -> dict[str, Any]:
        """Merged config with options taking priority over entry data."""
        return {**self.entry.data, **self.entry.options}

    @property
    def last_mow_timestamp(self) -> datetime | None:
        raw = self._stored_data.get(STORE_LAST_MOW_TIMESTAMP)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            return None

    @property
    def mowed_to_height(self) -> float:
        return float(
            self._stored_data.get(
                STORE_MOWED_TO_HEIGHT,
                self._cfg.get(CONF_MOWED_TO_HEIGHT, DEFAULT_MOWED_TO_HEIGHT),
            )
        )

    @property
    def mow_session_active(self) -> bool:
        return bool(self._stored_data.get(STORE_MOW_SESSION_ACTIVE, False))

    # ------------------------------------------------------------------
    # Setup / service handlers
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Load persisted mow data from storage."""
        stored = await self._store.async_load()
        if stored:
            self._stored_data = dict(stored)

    async def async_mark_mowed(self, mowed_to_height: float | None = None) -> None:
        """Record a mowing event; persist and refresh immediately."""
        now = dt_util.now()
        if mowed_to_height is None:
            mowed_to_height = self._cfg.get(CONF_MOWED_TO_HEIGHT, DEFAULT_MOWED_TO_HEIGHT)
        self._stored_data[STORE_LAST_MOW_TIMESTAMP] = now.isoformat()
        self._stored_data[STORE_MOWED_TO_HEIGHT] = float(mowed_to_height)
        await self._store.async_save(self._stored_data)
        await self.async_refresh()

    async def async_complete_mow(self, mowed_to_height: float | None = None) -> None:
        """Record a completed mow from an automated session and end the session."""
        now = dt_util.now()
        if mowed_to_height is None:
            mowed_to_height = self._cfg.get(CONF_MOWED_TO_HEIGHT, DEFAULT_MOWED_TO_HEIGHT)
        self._stored_data[STORE_LAST_MOW_TIMESTAMP] = now.isoformat()
        self._stored_data[STORE_MOWED_TO_HEIGHT] = float(mowed_to_height)
        self._stored_data[STORE_MOW_SESSION_ACTIVE] = False
        await self._store.async_save(self._stored_data)
        await self.async_refresh()

    async def async_start_mow_session(self) -> None:
        """Activate the mow session output (e.g. dispatch mower or send notification)."""
        self._stored_data[STORE_MOW_SESSION_ACTIVE] = True
        await self._store.async_save(self._stored_data)
        self.async_update_listeners()

    async def async_end_mow_session(self) -> None:
        """Cancel/deactivate the mow session without recording a mow."""
        self._stored_data[STORE_MOW_SESSION_ACTIVE] = False
        await self._store.async_save(self._stored_data)
        self.async_update_listeners()

    # ------------------------------------------------------------------
    # DataUpdateCoordinator hook
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.now()
        session = async_get_clientsession(self.hass)

        await self._read_weather_from_ha()

        if self._soil_moisture_needs_update(now):
            await self._fetch_soil_moisture(session)

        if self._soil_temp_needs_update(now):
            await self._fetch_soil_temp(session)

        return self._compute()

    # ------------------------------------------------------------------
    # TTL helpers
    # ------------------------------------------------------------------

    def _soil_moisture_needs_update(self, now: datetime) -> bool:
        return self._soil_moisture_fetched_at is None or (
            (now - self._soil_moisture_fetched_at).total_seconds() >= SOIL_UPDATE_INTERVAL
        )

    def _soil_temp_needs_update(self, now: datetime) -> bool:
        return self._soil_temp_fetched_at is None or (
            (now - self._soil_temp_fetched_at).total_seconds() >= SOIL_UPDATE_INTERVAL
        )

    # ------------------------------------------------------------------
    # Fetchers
    # ------------------------------------------------------------------

    async def _read_weather_from_ha(self) -> None:
        """Read weather data from the configured HA weather entity.

        Replaces direct OWM HTTP calls. The HA weather entity (e.g. the OWM
        integration) manages its own fetch schedule and caching; we just read from it.
        Uses weather.get_forecasts for both daily (GDD + rainfall) and hourly
        (wet/dry scheduling) data.
        """
        cfg = self._cfg
        weather_entity_id = cfg.get(CONF_WEATHER_ENTITY, DEFAULT_WEATHER_ENTITY)

        state = self.hass.states.get(weather_entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            _LOGGER.warning(
                "Weather entity %s is unavailable; using cached weather data", weather_entity_id
            )
            if self._weather_data is None:
                self._weather_data = {"gdd": 10.0, "rainfall": 0.0}
            return

        attrs = state.attributes
        temp_unit = attrs.get("temperature_unit", "°F")
        precip_unit = attrs.get("precipitation_unit", "mm")
        wind_unit = attrs.get("wind_speed_unit", "mph")

        # Current humidity as a fallback when no hourly slots are available.
        self._current_humidity = float(attrs.get("humidity") or 0.0)
        # Current drying-condition fallbacks from entity state attributes.
        self._current_wind_mph = _to_mph(float(attrs.get("wind_speed") or 0.0), wind_unit)
        self._current_cloud_pct = float(attrs.get("cloud_coverage") or 50.0)
        raw_cur_temp = float(attrs.get("temperature") or 70.0)
        self._current_temp_f = raw_cur_temp if temp_unit != "°C" else raw_cur_temp * 9.0 / 5.0 + 32.0

        # --- Daily forecast: GDD + today's rainfall ---
        try:
            daily_resp = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity_id, "type": "daily"},
                blocking=True,
                return_response=True,
            )
            daily = (daily_resp or {}).get(weather_entity_id, {}).get("forecast") or []
            today = daily[0] if daily else {}

            t_high = float(today.get("temperature") or 70)
            t_low = float(today.get("templow") or 50)
            if temp_unit == "°C":
                t_high = t_high * 9.0 / 5.0 + 32.0
                t_low = t_low * 9.0 / 5.0 + 32.0
            gdd = max(0.0, (t_high + t_low) / 2.0 - GDD_BASE_TEMP_F)

            rain_raw = float(today.get("precipitation") or 0.0)
            rain_inches = rain_raw * 0.03937 if precip_unit == "mm" else rain_raw

            self._weather_data = {"gdd": gdd, "rainfall": rain_inches}

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to read daily forecast from %s: %s", weather_entity_id, err)
            if self._weather_data is None:
                self._weather_data = {"gdd": 10.0, "rainfall": 0.0}

        # --- Hourly forecast: wet/dry scheduling ---
        try:
            hourly_resp = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity_id, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
            hourly_raw = (hourly_resp or {}).get(weather_entity_id, {}).get("forecast") or []

            slots = []
            for slot in hourly_raw:
                raw_dt = slot.get("datetime")
                try:
                    dt_epoch = int(datetime.fromisoformat(raw_dt).timestamp()) if raw_dt else 0
                except (ValueError, TypeError):
                    dt_epoch = 0
                rain_raw = float(slot.get("precipitation") or 0.0)
                rain_in = rain_raw * 0.03937 if precip_unit == "mm" else rain_raw
                # HA weather entities report precipitation_probability as 0-100 %;
                # our dry-window logic uses 0-1, so divide here.
                pop_pct = float(slot.get("precipitation_probability") or 0.0)
                raw_temp = float(slot.get("temperature") or 70.0)
                temp_f = raw_temp if temp_unit != "°C" else raw_temp * 9.0 / 5.0 + 32.0
                slots.append({
                    "dt": dt_epoch,
                    "rain_1h": rain_in,
                    "humidity": int(slot.get("humidity") or 0),
                    "pop": pop_pct / 100.0,
                    "temp_f": temp_f,
                    "wind_mph": _to_mph(float(slot.get("wind_speed") or 0.0), wind_unit),
                    "cloud_pct": float(slot.get("cloud_coverage") or 50.0),
                })
            self._hourly_forecast = slots

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to read hourly forecast from %s: %s", weather_entity_id, err)

    async def _fetch_soil_moisture(self, session) -> None:
        """Fetch volumetric soil moisture from National Soil Moisture Network."""
        cfg = self._cfg
        lat = cfg.get(CONF_LATITUDE, self.hass.config.latitude)
        lon = cfg.get(CONF_LONGITUDE, self.hass.config.longitude)

        params = {"lat": lat, "lon": lon, "depth": 5}

        try:
            async with asyncio.timeout(30):
                async with session.get(NSM_BASE_URL, params=params) as resp:
                    resp.raise_for_status()
                    payload = await resp.json(content_type=None)

            moisture_pct = _parse_nsm_moisture(payload)
            self._soil_moisture_data = {"soil_moisture": moisture_pct}
            self._soil_moisture_fetched_at = dt_util.now()

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Soil moisture fetch failed: %s", err)
            if self._soil_moisture_data is None:
                self._soil_moisture_data = {"soil_moisture": OPTIMAL_SOIL_MOISTURE_PCT}

    async def _fetch_soil_temp(self, session) -> None:
        """Fetch 2-inch soil temperature from the nearest USDA SCAN station."""
        cfg = self._cfg
        lat = cfg.get(CONF_LATITUDE, self.hass.config.latitude)
        lon = cfg.get(CONF_LONGITUDE, self.hass.config.longitude)

        try:
            if not self._scan_station_resolved:
                self._scan_station_triplet = await self._find_scan_station(session, lat, lon)
                self._scan_station_resolved = True

            if not self._scan_station_triplet:
                _LOGGER.warning(
                    "No SCAN station found within 200 miles of %.4f, %.4f", lat, lon
                )
                if self._soil_temp_data is None:
                    self._soil_temp_data = {"soil_temperature": OPTIMAL_SOIL_TEMP_F}
                return

            today = dt_util.now().strftime("%Y-%m-%d")
            params = {
                "stationTriplets": self._scan_station_triplet,
                "elementCd": "STO",
                "ordinal": 2,   # 2-inch depth
                "beginDate": today,
                "endDate": today,
                "duration": "DAILY",
            }

            async with asyncio.timeout(30):
                async with session.get(SCAN_DATA_URL, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)

            soil_temp = _parse_scan_soil_temp(data)
            self._soil_temp_data = {"soil_temperature": soil_temp}
            self._soil_temp_fetched_at = dt_util.now()

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("SCAN soil temperature fetch failed: %s", err)
            if self._soil_temp_data is None:
                self._soil_temp_data = {"soil_temperature": OPTIMAL_SOIL_TEMP_F}

    async def _find_scan_station(self, session, lat: float, lon: float) -> str | None:
        """Return the stationTriplet of the nearest USDA SCAN station."""
        params = {
            "networkCds": "SCAN",
            "latitude": lat,
            "longitude": lon,
            "radius": 200,
            "maxResults": 1,
        }
        try:
            async with asyncio.timeout(30):
                async with session.get(SCAN_STATIONS_URL, params=params) as resp:
                    resp.raise_for_status()
                    stations = await resp.json(content_type=None)

            if isinstance(stations, list) and stations:
                triplet = stations[0].get("stationTriplet")
                _LOGGER.debug("Nearest SCAN station: %s", triplet)
                return triplet

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("SCAN station lookup failed: %s", err)

        return None

    # ------------------------------------------------------------------
    # Growth computation
    # ------------------------------------------------------------------

    def _compute(self) -> dict[str, Any]:
        """Compute current grass height and all contributing factors."""
        now = dt_util.now()
        cfg = self._cfg

        last_mow = self.last_mow_timestamp
        days_since_mow = (
            max(0.0, (now - last_mow).total_seconds() / 86_400.0)
            if last_mow is not None
            else 0.0
        )

        base_rate = float(cfg.get(CONF_BASE_GROWTH_RATE, DEFAULT_BASE_GROWTH_RATE))
        min_days = float(cfg.get(CONF_MIN_DAYS_BETWEEN_MOWS, DEFAULT_MIN_DAYS_BETWEEN_MOWS))
        max_days = float(cfg.get(CONF_MAX_DAYS_BETWEEN_MOWS, DEFAULT_MAX_DAYS_BETWEEN_MOWS))
        max_growth = float(cfg.get(CONF_MAX_GROWTH_BETWEEN_MOWS, DEFAULT_MAX_GROWTH_BETWEEN_MOWS))
        force_growth = float(cfg.get(CONF_FORCE_MOW_GROWTH_THRESHOLD, DEFAULT_FORCE_MOW_GROWTH_THRESHOLD))
        mow_cycle_h = float(cfg.get(CONF_MOW_CYCLE_DURATION_HOURS, DEFAULT_MOW_CYCLE_DURATION_HOURS))
        wet_rain_in = float(cfg.get(CONF_WET_RAIN_THRESHOLD_IN, DEFAULT_WET_RAIN_THRESHOLD_IN))
        wet_humidity = float(cfg.get(CONF_WET_HUMIDITY_PCT, DEFAULT_WET_HUMIDITY_PCT))
        lookahead_h = int(cfg.get(CONF_DRY_WINDOW_LOOKAHEAD_HOURS, DEFAULT_DRY_WINDOW_LOOKAHEAD_HOURS))

        weather = self._weather_data or {"gdd": 10.0, "rainfall": 0.0}
        gdd = float(weather.get("gdd", 10.0))
        rainfall = float(weather.get("rainfall", 0.0))
        soil_moisture = float(
            (self._soil_moisture_data or {}).get("soil_moisture", OPTIMAL_SOIL_MOISTURE_PCT)
        )
        soil_temp = float(
            (self._soil_temp_data or {}).get("soil_temperature", OPTIMAL_SOIL_TEMP_F)
        )

        season_factor = 1.0
        gdd_factor = 1.0
        rain_factor = 1.0
        soil_moisture_factor = 1.0
        soil_temp_factor = 1.0
        enabled: list[str] = []

        if cfg.get(CONF_ENABLE_SEASONAL, True):
            season_factor = SEASON_FACTORS.get(now.month, 1.0)
            enabled.append("seasonal")

        if cfg.get(CONF_ENABLE_GDD, True):
            gdd_factor = _gdd_factor(gdd)
            enabled.append("gdd")

        if cfg.get(CONF_ENABLE_RAIN, True):
            rain_factor = _rain_factor(rainfall)
            enabled.append("rain")

        if cfg.get(CONF_ENABLE_SOIL_MOISTURE, True):
            soil_moisture_factor = _soil_moisture_factor(soil_moisture)
            enabled.append("soil_moisture")

        if cfg.get(CONF_ENABLE_SOIL_TEMP, True):
            soil_temp_factor = _soil_temp_factor(soil_temp)
            enabled.append("soil_temp")

        daily_rate = (
            base_rate
            * season_factor
            * gdd_factor
            * rain_factor
            * soil_moisture_factor
            * soil_temp_factor
        )

        current_height = self.mowed_to_height + days_since_mow * daily_rate
        growth_since_mow = max(0.0, current_height - self.mowed_to_height)

        # --- Wet grass detection ---
        # Prefer the first hourly slot for current conditions; fall back to entity state attrs.
        if self._hourly_forecast:
            cur_slot = self._hourly_forecast[0]
            current_humidity = float(cur_slot.get("humidity", 0))
            cur_temp_f = float(cur_slot.get("temp_f", self._current_temp_f))
            cur_wind_mph = float(cur_slot.get("wind_mph", self._current_wind_mph))
            cur_cloud_pct = float(cur_slot.get("cloud_pct", self._current_cloud_pct))
        else:
            current_humidity = self._current_humidity
            cur_temp_f = self._current_temp_f
            cur_wind_mph = self._current_wind_mph
            cur_cloud_pct = self._current_cloud_pct

        # Estimate how much of today's rainfall has already evaporated.
        # Assume drying conditions have been roughly constant since dawn (06:00 local).
        # This is a conservative lower bound — some drying may have occurred before dawn.
        hours_since_dawn = max(0.0, (now.hour + now.minute / 60.0) - 6.0)
        current_evap_rate = _evaporation_rate_in_per_hour(
            cur_temp_f, cur_wind_mph, cur_cloud_pct, current_humidity
        )
        evaporated_today = current_evap_rate * hours_since_dawn
        current_moisture_in = max(0.0, rainfall - evaporated_today)

        grass_wet = (current_moisture_in >= wet_rain_in) or (current_humidity >= wet_humidity)

        # --- Dry mow window ---
        hourly_window = self._hourly_forecast[:lookahead_h]
        dry_window_epoch = _find_dry_mow_window(
            hourly_window, mow_cycle_h, wet_humidity, current_moisture_in, wet_rain_in
        )
        dry_window_dt: datetime | None = (
            dt_util.utc_from_timestamp(dry_window_epoch)
            if dry_window_epoch is not None
            else None
        )
        dry_window_soon = dry_window_dt is not None

        # --- Mow-not-advised: covers the whole mow cycle window ---
        # ON when currently wet OR any hourly slot in the next mow_cycle_h hours is wet
        # after accounting for projected evaporation through the cycle window.
        cycle_slots = self._hourly_forecast[:max(1, math.ceil(mow_cycle_h))]
        moisture = current_moisture_in
        rain_coming = grass_wet
        if not rain_coming:
            for i, s in enumerate(cycle_slots):
                if i + 1 < len(cycle_slots):
                    slot_dur_h = (int(cycle_slots[i + 1].get("dt") or 0) - int(s.get("dt") or 0)) / 3600.0
                else:
                    slot_dur_h = 1.0
                slot_dur_h = max(slot_dur_h, 0.25)
                evap = _evaporation_rate_in_per_hour(
                    float(s.get("temp_f", cur_temp_f)),
                    float(s.get("wind_mph", cur_wind_mph)),
                    float(s.get("cloud_pct", cur_cloud_pct)),
                    float(s.get("humidity", current_humidity)),
                ) * slot_dur_h
                moisture = max(0.0, moisture - evap) + float(s.get("rain_1h", 0.0))
                if (
                    moisture > _DRY_SLOT_RAIN_IN
                    or float(s.get("rain_1h", 0.0)) > _DRY_SLOT_RAIN_IN
                    or float(s.get("pop", 0.0)) > _DRY_SLOT_POP_MAX
                    or int(s.get("humidity", 0)) >= wet_humidity
                ):
                    rain_coming = True
                    break
        mow_not_advised = rain_coming

        # --- Mowing thresholds ---
        # mow_overdue: hard upper bound — always ON at max_days, ignores wet state
        mow_overdue = last_mow is None or days_since_mow >= max_days
        # force_mow: grown too much — mow regardless of wet state
        force_mow = growth_since_mow >= force_growth
        # normal_trigger: grown enough and past minimum days — prefer a dry window
        days_ok = last_mow is None or days_since_mow >= min_days
        normal_trigger = days_ok and growth_since_mow >= max_growth

        # mow_recommended logic:
        #   1. overdue or overgrown → always mow
        #   2. normal trigger + dry now → mow
        #   3. normal trigger + wet + no dry window coming → mow anyway (don't delay indefinitely)
        mow_recommended = (
            mow_overdue
            or force_mow
            or (normal_trigger and not grass_wet)
            or (normal_trigger and grass_wet and not dry_window_soon)
        )

        return {
            "current_height": round(current_height, 2),
            "daily_growth_rate": round(daily_rate, 5),
            "days_since_mow": round(days_since_mow, 3),
            "growth_since_mow": round(growth_since_mow, 2),
            "last_mow_timestamp": last_mow.isoformat() if last_mow else None,
            "gdd": round(gdd, 2),
            "rainfall": round(rainfall, 4),
            "current_moisture": round(current_moisture_in, 4),
            "soil_moisture": round(soil_moisture, 1),
            "soil_temperature": round(soil_temp, 1),
            "season_factor": round(season_factor, 3),
            "enabled_multipliers": enabled,
            "current_humidity": round(current_humidity, 1),
            SENSOR_NEXT_DRY_MOW_WINDOW: dry_window_dt,
            BINARY_SENSOR_GRASS_WET: grass_wet,
            BINARY_SENSOR_MOW_NOT_ADVISED: mow_not_advised,
            BINARY_SENSOR_DRY_MOW_WINDOW_SOON: dry_window_soon,
            BINARY_SENSOR_MOW_RECOMMENDED: mow_recommended,
            BINARY_SENSOR_MOW_OVERDUE: mow_overdue,
        }


# ------------------------------------------------------------------
# Pure growth-factor functions
# ------------------------------------------------------------------

# Dry-window slot thresholds (not user-configurable — keep UI simple)
_DRY_SLOT_RAIN_IN = 0.04   # ≈ 1 mm/h; above this a slot is considered rainy
_DRY_SLOT_POP_MAX = 0.30   # 30 % precipitation probability ceiling for a dry slot

# Drying rate ceiling (in/h) under ideal conditions (sunny, windy, low humidity).
# Used to prevent unrealistically fast drying estimates.
_MAX_EVAP_RATE_IN_PER_HOUR = 0.08


def _to_mph(speed: float, unit: str) -> float:
    """Convert a wind speed value to miles per hour."""
    unit_l = unit.lower()
    if "km" in unit_l:          # km/h
        return speed * 0.621371
    if unit_l in ("m/s", "ms"): # m/s
        return speed * 2.23694
    return speed                 # already mph (or unknown — pass through)


def _evaporation_rate_in_per_hour(
    temp_f: float,
    wind_mph: float,
    cloud_pct: float,
    humidity_pct: float,
) -> float:
    """Estimate surface evaporation from a wet grass surface (inches/hour).

    Combines two components inspired by the Penman equation:

    1. **Radiation term** — energy available to vaporise water.
       Proxy: clear-sky fraction × temperature factor (warmer air holds more
       energy and increases the vapour-pressure deficit).

    2. **Aerodynamic term** — wind ventilates the wet surface and replaces
       saturated air with drier ambient air (vapour-pressure deficit).

    Calibration targets:
    - Good drying (clear sky, 75 °F, 15 mph, 40% RH) → ~0.060 in/h
    - Moderate drying (50% cloud, 65 °F, 10 mph, 60% RH) → ~0.025 in/h
    - Poor drying (overcast, 50 °F, calm, 85% RH)       → ~0.001 in/h
    """
    temp_c = (temp_f - 32.0) * 5.0 / 9.0
    solar = max(0.0, 1.0 - cloud_pct / 100.0)
    vpd = max(0.0, 1.0 - humidity_pct / 100.0) * max(0.0, temp_c / 30.0)
    wind_factor = 1.0 + min(wind_mph, 20.0) / 10.0  # 1.0 (calm) → 3.0 (20 mph)

    radiation_term = 0.04 * solar * max(0.0, temp_c / 25.0)
    aero_term = 0.02 * wind_factor * vpd

    return min(_MAX_EVAP_RATE_IN_PER_HOUR, radiation_term + aero_term)


def _find_dry_mow_window(
    hourly: list[dict[str, Any]],
    needed_hours: float,
    wet_humidity_pct: float,
    initial_moisture_in: float = 0.0,
    wet_rain_threshold_in: float = 0.1,
) -> int | None:
    """Return epoch timestamp of the first contiguous dry window long enough to mow.

    A slot is 'dry' when ALL of the following hold:
    - Projected surface moisture ≤ wet_rain_threshold_in  (accounts for evaporation)
    - rain_1h  ≤ _DRY_SLOT_RAIN_IN
    - pop      ≤ _DRY_SLOT_POP_MAX
    - humidity < wet_humidity_pct

    Moisture is projected forward by subtracting each slot's evaporation
    (_evaporation_rate_in_per_hour × slot duration) and adding its rain_1h.

    Window duration is validated against real timestamps so the result is
    correct regardless of the forecast interval (1 h, 3 h, etc.) used by the
    configured weather entity.
    """
    needed_secs = needed_hours * 3600.0
    window_start: int | None = None
    moisture = initial_moisture_in

    for i, slot in enumerate(hourly):
        slot_dt = int(slot.get("dt") or 0)
        if i + 1 < len(hourly):
            next_dt = int(hourly[i + 1].get("dt") or (slot_dt + 3600))
        else:
            next_dt = slot_dt + 3600
        slot_dur_h = max((next_dt - slot_dt) / 3600.0, 0.25)

        evap = _evaporation_rate_in_per_hour(
            float(slot.get("temp_f", 70.0)),
            float(slot.get("wind_mph", 0.0)),
            float(slot.get("cloud_pct", 50.0)),
            float(slot.get("humidity", 100)),
        ) * slot_dur_h
        moisture = max(0.0, moisture - evap) + float(slot.get("rain_1h", 0.0))

        if (
            moisture <= wet_rain_threshold_in
            and float(slot.get("rain_1h", 0.0)) <= _DRY_SLOT_RAIN_IN
            and float(slot.get("pop", 0.0)) <= _DRY_SLOT_POP_MAX
            and int(slot.get("humidity", 100)) < wet_humidity_pct
        ):
            if window_start is None:
                window_start = slot_dt
            if (next_dt - window_start) >= needed_secs:
                return window_start
        else:
            window_start = None

    return None


def _gdd_factor(gdd: float) -> float:
    """Scale 0.05–2.0 based on growing degree days relative to optimal."""
    if gdd <= 0:
        return 0.05
    return float(min(2.0, max(0.05, gdd / OPTIMAL_GDD_DAILY)))


def _rain_factor(rain_inches: float) -> float:
    """Boost growth up to 1.5x for well-watered conditions."""
    return float(min(1.5, max(0.8, 1.0 + rain_inches * 0.25)))


def _soil_moisture_factor(pct: float) -> float:
    """Map soil moisture % to a 0.05–1.0 growth factor."""
    if pct < 10:
        return 0.05
    if pct < 30:
        return 0.05 + (pct - 10) / 20.0 * 0.95
    if pct <= 65:
        return 1.0
    if pct <= 85:
        return 1.0 - (pct - 65) / 20.0 * 0.35
    return 0.65


def _soil_temp_factor(temp_f: float) -> float:
    """Map soil temperature (°F) to a 0.0–1.0 growth factor (cool-season turf)."""
    if temp_f <= 32:
        return 0.0
    if temp_f < 50:
        return (temp_f - 32) / 18.0 * 0.25
    if temp_f < 60:
        return 0.25 + (temp_f - 50) / 10.0 * 0.75
    if temp_f <= 75:
        return 1.0
    if temp_f <= 95:
        return 1.0 - (temp_f - 75) / 20.0 * 0.55
    return 0.45


# ------------------------------------------------------------------
# API response parsers
# ------------------------------------------------------------------

def _parse_nsm_moisture(payload: Any) -> float:
    """Best-effort extraction of soil moisture % from NSM API payload."""
    candidate_keys = ("soil_moisture_pct", "moisture_pct", "value", "moisture")

    if isinstance(payload, dict):
        for key in candidate_keys:
            val = payload.get(key)
            if val is not None:
                m = float(val)
                return m * 100 if m < 1.5 else m

        nested = payload.get("data")
        if isinstance(nested, dict):
            for key in candidate_keys:
                val = nested.get(key)
                if val is not None:
                    m = float(val)
                    return m * 100 if m < 1.5 else m

    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            for key in candidate_keys:
                val = first.get(key)
                if val is not None:
                    m = float(val)
                    return m * 100 if m < 1.5 else m

    return OPTIMAL_SOIL_MOISTURE_PCT


def _parse_scan_soil_temp(data: Any) -> float:
    """Extract soil temperature from USDA AWDB REST API data response."""
    if isinstance(data, list) and data:
        record = data[0]
        if isinstance(record, dict):
            values = record.get("values") or []
            if values and values[0] is not None:
                try:
                    return float(values[0])
                except (TypeError, ValueError):
                    pass
    return OPTIMAL_SOIL_TEMP_F

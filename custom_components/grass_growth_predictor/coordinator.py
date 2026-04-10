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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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
    CONF_OWM_API_KEY,
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
    DEFAULT_WET_HUMIDITY_PCT,
    DEFAULT_WET_RAIN_THRESHOLD_IN,
    DOMAIN,
    GDD_BASE_TEMP_F,
    HEIGHT_UPDATE_INTERVAL,
    NSM_BASE_URL,
    OPTIMAL_GDD_DAILY,
    OPTIMAL_SOIL_MOISTURE_PCT,
    OPTIMAL_SOIL_TEMP_F,
    OWM_BASE_URL,
    SCAN_DATA_URL,
    SCAN_STATIONS_URL,
    SEASON_FACTORS,
    SENSOR_NEXT_DRY_MOW_WINDOW,
    SOIL_UPDATE_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
    STORE_HOURLY_FORECAST,
    STORE_LAST_MOW_TIMESTAMP,
    STORE_MOW_SESSION_ACTIVE,
    STORE_MOWED_TO_HEIGHT,
    STORE_WEATHER_DATA,
    STORE_WEATHER_FETCHED_AT,
    WEATHER_MIN_UPDATE_INTERVAL,
    WEATHER_UPDATE_INTERVAL,
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
        self._weather_fetched_at: datetime | None = None
        self._hourly_forecast: list[dict[str, Any]] = []  # reduced hourly slots from OWM

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
            # Poll every 2 h so the dynamic OWM TTL (max 2 h, mow_cycle/2) is honoured.
            # The height calculation and soil fetches use their own longer TTLs internally.
            update_interval=timedelta(seconds=WEATHER_MIN_UPDATE_INTERVAL),
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
            # Restore weather cache so a restart doesn't burn an extra API call
            raw_ts = self._stored_data.get(STORE_WEATHER_FETCHED_AT)
            if raw_ts:
                try:
                    self._weather_fetched_at = datetime.fromisoformat(raw_ts)
                except (ValueError, TypeError):
                    pass
            raw_data = self._stored_data.get(STORE_WEATHER_DATA)
            if isinstance(raw_data, dict):
                self._weather_data = raw_data
            raw_hourly = self._stored_data.get(STORE_HOURLY_FORECAST)
            if isinstance(raw_hourly, list):
                self._hourly_forecast = raw_hourly

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

        if self._weather_needs_update(now):
            await self._fetch_weather(session)

        if self._soil_moisture_needs_update(now):
            await self._fetch_soil_moisture(session)

        if self._soil_temp_needs_update(now):
            await self._fetch_soil_temp(session)

        return self._compute()

    # ------------------------------------------------------------------
    # TTL helpers
    # ------------------------------------------------------------------

    def _weather_needs_update(self, now: datetime) -> bool:
        # Refresh OWM at half the mow-cycle duration, but never faster than 2 h.
        mow_cycle_h = float(
            self._cfg.get(CONF_MOW_CYCLE_DURATION_HOURS, DEFAULT_MOW_CYCLE_DURATION_HOURS)
        )
        ttl = max(WEATHER_MIN_UPDATE_INTERVAL, (mow_cycle_h / 2.0) * 3600.0)
        return self._weather_fetched_at is None or (
            (now - self._weather_fetched_at).total_seconds() >= ttl
        )

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

    async def _fetch_weather(self, session) -> None:
        """Fetch GDD and rainfall via OpenWeatherMap One Call 3.0."""
        cfg = self._cfg
        lat = cfg.get(CONF_LATITUDE, self.hass.config.latitude)
        lon = cfg.get(CONF_LONGITUDE, self.hass.config.longitude)
        api_key = cfg.get(CONF_OWM_API_KEY, "")

        params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "imperial",
            "exclude": "current,minutely,alerts",
        }

        try:
            async with asyncio.timeout(30):
                async with session.get(OWM_BASE_URL, params=params) as resp:
                    resp.raise_for_status()
                    payload = await resp.json()

            daily = payload.get("daily") or [{}]
            today = daily[0] if daily else {}
            temp = today.get("temp") or {}
            t_max = float(temp.get("max", 70))
            t_min = float(temp.get("min", 50))
            gdd = max(0.0, (t_max + t_min) / 2.0 - GDD_BASE_TEMP_F)
            rain_mm = float(today.get("rain", 0.0))
            rain_inches = rain_mm * 0.03937  # mm → inches

            self._weather_data = {"gdd": gdd, "rainfall": rain_inches}
            self._weather_fetched_at = dt_util.now()

            # Parse hourly forecast — keep only fields needed for wet/dry scheduling.
            # OWM hourly rain field is {"1h": mm} or absent; convert to inches.
            hourly_raw = payload.get("hourly") or []
            self._hourly_forecast = [
                {
                    "dt": int(slot.get("dt", 0)),
                    "rain_1h": float(
                        (slot.get("rain") or {}).get("1h", 0.0)
                    ) * 0.03937,  # mm → inches
                    "humidity": int(slot.get("humidity", 0)),
                    "pop": float(slot.get("pop", 0.0)),
                }
                for slot in hourly_raw
            ]

            self._stored_data[STORE_WEATHER_FETCHED_AT] = self._weather_fetched_at.isoformat()
            self._stored_data[STORE_WEATHER_DATA] = self._weather_data
            self._stored_data[STORE_HOURLY_FORECAST] = self._hourly_forecast
            await self._store.async_save(self._stored_data)

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("OpenWeatherMap fetch failed: %s", err)
            if self._weather_data is None:
                self._weather_data = {"gdd": 10.0, "rainfall": 0.0}

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
        # Hourly[0] represents the current/nearest hour from the cached forecast.
        current_humidity = (
            float(self._hourly_forecast[0].get("humidity", 0))
            if self._hourly_forecast
            else 0.0
        )
        grass_wet = (rainfall >= wet_rain_in) or (current_humidity >= wet_humidity)

        # --- Dry mow window ---
        hourly_window = self._hourly_forecast[:lookahead_h]
        dry_window_epoch = _find_dry_mow_window(hourly_window, mow_cycle_h, wet_humidity)
        dry_window_dt: datetime | None = (
            dt_util.utc_from_timestamp(dry_window_epoch)
            if dry_window_epoch is not None
            else None
        )
        dry_window_soon = dry_window_dt is not None

        # --- Mow-not-advised: covers the whole mow cycle window ---
        # ON when currently wet OR any hourly slot in the next mow_cycle_h hours is wet.
        # Intended as a manual-mow indicator: if you start now, will conditions stay tolerable?
        cycle_slots = self._hourly_forecast[:max(1, math.ceil(mow_cycle_h))]
        rain_coming = any(
            float(s.get("rain_1h", 0.0)) > _DRY_SLOT_RAIN_IN
            or float(s.get("pop", 0.0)) > _DRY_SLOT_POP_MAX
            or int(s.get("humidity", 0)) >= wet_humidity
            for s in cycle_slots
        )
        mow_not_advised = grass_wet or rain_coming

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


def _find_dry_mow_window(
    hourly: list[dict[str, Any]],
    needed_hours: float,
    wet_humidity_pct: float,
) -> int | None:
    """Return epoch timestamp of the first contiguous dry window long enough to mow.

    A slot is 'dry' when:
    - rain_1h < _DRY_SLOT_RAIN_IN inches
    - pop     < _DRY_SLOT_POP_MAX
    - humidity < wet_humidity_pct
    """
    needed = max(1, math.ceil(needed_hours))
    run = 0
    window_start: int | None = None
    for slot in hourly:
        if (
            float(slot.get("rain_1h", 0.0)) <= _DRY_SLOT_RAIN_IN
            and float(slot.get("pop", 0.0)) <= _DRY_SLOT_POP_MAX
            and int(slot.get("humidity", 100)) < wet_humidity_pct
        ):
            if run == 0:
                window_start = slot.get("dt")
            run += 1
            if run >= needed:
                return window_start
        else:
            run = 0
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

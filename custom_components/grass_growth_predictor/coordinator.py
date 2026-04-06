"""DataUpdateCoordinator for Grass Growth Predictor."""
from __future__ import annotations

import asyncio
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
    CONF_BASE_GROWTH_RATE,
    CONF_ENABLE_GDD,
    CONF_ENABLE_RAIN,
    CONF_ENABLE_SEASONAL,
    CONF_ENABLE_SOIL_MOISTURE,
    CONF_ENABLE_SOIL_TEMP,
    CONF_MOWED_TO_HEIGHT,
    CONF_OWM_API_KEY,
    DEFAULT_BASE_GROWTH_RATE,
    DEFAULT_MOWED_TO_HEIGHT,
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
    SOIL_UPDATE_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
    STORE_LAST_MOW_TIMESTAMP,
    STORE_MOWED_TO_HEIGHT,
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
            update_interval=timedelta(seconds=HEIGHT_UPDATE_INTERVAL),
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
        return self._weather_fetched_at is None or (
            (now - self._weather_fetched_at).total_seconds() >= WEATHER_UPDATE_INTERVAL
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
        """Fetch GDD and rainfall via OpenWeatherMap One Call 2.5."""
        cfg = self._cfg
        lat = cfg.get(CONF_LATITUDE, self.hass.config.latitude)
        lon = cfg.get(CONF_LONGITUDE, self.hass.config.longitude)
        api_key = cfg.get(CONF_OWM_API_KEY, "")

        params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "imperial",
            "exclude": "current,minutely,hourly,alerts",
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

        return {
            "current_height": round(current_height, 2),
            "daily_growth_rate": round(daily_rate, 5),
            "days_since_mow": round(days_since_mow, 3),
            "last_mow_timestamp": last_mow.isoformat() if last_mow else None,
            "gdd": round(gdd, 2),
            "rainfall": round(rainfall, 4),
            "soil_moisture": round(soil_moisture, 1),
            "soil_temperature": round(soil_temp, 1),
            "season_factor": round(season_factor, 3),
            "enabled_multipliers": enabled,
        }


# ------------------------------------------------------------------
# Pure growth-factor functions
# ------------------------------------------------------------------

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

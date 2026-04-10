"""Sensor platform for Grass Growth Predictor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DAILY_GROWTH_RATE,
    ATTR_DAYS_SINCE_MOW,
    ATTR_ENABLED_MULTIPLIERS,
    ATTR_GDD,
    ATTR_LAST_MOW_TIMESTAMP,
    ATTR_RAINFALL,
    ATTR_SEASON_FACTOR,
    ATTR_SOIL_MOISTURE,
    ATTR_SOIL_TEMPERATURE,
    DOMAIN,
    SENSOR_CURRENT_GRASS_HEIGHT,
    SENSOR_DAILY_GROWTH_RATE,
    SENSOR_DAYS_SINCE_MOW,
    SENSOR_GDD,
    SENSOR_GROWTH_SINCE_MOW,
    SENSOR_NEXT_DRY_MOW_WINDOW,
    SENSOR_RAINFALL,
    SENSOR_SEASON_FACTOR,
    SENSOR_SOIL_MOISTURE,
    SENSOR_SOIL_TEMPERATURE,
)
from .coordinator import GrassGrowthCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GrassGrowthCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CurrentGrassHeightSensor(coordinator, entry),
            DailyGrowthRateSensor(coordinator, entry),
            DaysSinceMowSensor(coordinator, entry),
            GrowthSinceMowSensor(coordinator, entry),
            NextDryMowWindowSensor(coordinator, entry),
            GrowingDegreeDaysSensor(coordinator, entry),
            RainfallSensor(coordinator, entry),
            SoilMoistureSensor(coordinator, entry),
            SoilTemperatureSensor(coordinator, entry),
            SeasonFactorSensor(coordinator, entry),
        ],
        True,
    )


class _GrassBaseSensor(CoordinatorEntity[GrassGrowthCoordinator], SensorEntity):
    """Shared base for all Grass Growth Predictor sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _data_key: str  # set by each subclass

    def __init__(self, coordinator: GrassGrowthCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{self._data_key}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._data_key)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Grass Growth Predictor",
            manufacturer="Custom Integration",
            model="Grass Growth Predictor v1",
            entry_type=DeviceEntryType.SERVICE,
        )


class CurrentGrassHeightSensor(_GrassBaseSensor):
    """Sensor reporting the estimated current grass height in inches."""

    _attr_name = "Current Grass Height"
    _attr_native_unit_of_measurement = "in"
    _attr_icon = "mdi:grass"
    _data_key = "current_height"

    def __init__(self, coordinator: GrassGrowthCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_CURRENT_GRASS_HEIGHT}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("current_height")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            ATTR_LAST_MOW_TIMESTAMP: data.get("last_mow_timestamp"),
            ATTR_DAILY_GROWTH_RATE: data.get("daily_growth_rate"),
            ATTR_DAYS_SINCE_MOW: data.get("days_since_mow"),
            ATTR_GDD: data.get("gdd"),
            ATTR_RAINFALL: data.get("rainfall"),
            ATTR_SOIL_MOISTURE: data.get("soil_moisture"),
            ATTR_SOIL_TEMPERATURE: data.get("soil_temperature"),
            ATTR_SEASON_FACTOR: data.get("season_factor"),
            ATTR_ENABLED_MULTIPLIERS: data.get("enabled_multipliers", []),
        }


class DailyGrowthRateSensor(_GrassBaseSensor):
    """Sensor reporting the calculated daily grass growth rate."""

    _attr_name = "Daily Growth Rate"
    _attr_native_unit_of_measurement = "in/day"
    _attr_icon = "mdi:speedometer"
    _data_key = SENSOR_DAILY_GROWTH_RATE


class DaysSinceMowSensor(_GrassBaseSensor):
    """Sensor reporting the number of days since the last mow."""

    _attr_name = "Days Since Last Mow"
    _attr_native_unit_of_measurement = "d"
    _attr_icon = "mdi:calendar-clock"
    _data_key = SENSOR_DAYS_SINCE_MOW


class GrowthSinceMowSensor(_GrassBaseSensor):
    """Sensor reporting the estimated grass growth since the last mow.

    This is the value compared against 'Maximum Growth Between Mows' to
    determine whether a mow session should be recommended.
    """

    _attr_name = "Growth Since Last Mow"
    _attr_native_unit_of_measurement = "in"
    _attr_icon = "mdi:grass"
    _data_key = SENSOR_GROWTH_SINCE_MOW


class NextDryMowWindowSensor(CoordinatorEntity[GrassGrowthCoordinator], SensorEntity):
    """Timestamp sensor reporting the start of the next suitable dry mow window.

    Returns 'unknown' when no dry window is found within the lookahead period.
    """

    _attr_has_entity_name = True
    _attr_name = "Next Dry Mow Window"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:weather-sunny-off"

    def __init__(self, coordinator: GrassGrowthCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_NEXT_DRY_MOW_WINDOW}"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(SENSOR_NEXT_DRY_MOW_WINDOW)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Grass Growth Predictor",
            manufacturer="Custom Integration",
            model="Grass Growth Predictor v1",
            entry_type=DeviceEntryType.SERVICE,
        )


class GrowingDegreeDaysSensor(_GrassBaseSensor):
    """Sensor reporting today's growing degree days."""

    _attr_name = "Growing Degree Days"
    _attr_native_unit_of_measurement = "°F·d"
    _attr_icon = "mdi:thermometer-lines"
    _data_key = SENSOR_GDD


class RainfallSensor(_GrassBaseSensor):
    """Sensor reporting today's rainfall used in the growth model."""

    _attr_name = "Rainfall"
    _attr_native_unit_of_measurement = "in"
    _attr_icon = "mdi:weather-rainy"
    _data_key = SENSOR_RAINFALL


class SoilMoistureSensor(_GrassBaseSensor):
    """Sensor reporting the volumetric soil moisture percentage."""

    _attr_name = "Soil Moisture"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:water-percent"
    _data_key = SENSOR_SOIL_MOISTURE


class SoilTemperatureSensor(_GrassBaseSensor):
    """Sensor reporting the 2-inch soil temperature."""

    _attr_name = "Soil Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _data_key = SENSOR_SOIL_TEMPERATURE


class SeasonFactorSensor(_GrassBaseSensor):
    """Sensor reporting the current month's seasonal growth multiplier."""

    _attr_name = "Season Factor"
    _attr_icon = "mdi:calendar-range"
    _data_key = SENSOR_SEASON_FACTOR

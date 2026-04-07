"""Sensor platform for Grass Growth Predictor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
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
)
from .coordinator import GrassGrowthCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GrassGrowthCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CurrentGrassHeightSensor(coordinator, entry)], True)


class CurrentGrassHeightSensor(CoordinatorEntity[GrassGrowthCoordinator], SensorEntity):
    """Sensor reporting the estimated current grass height in inches."""

    _attr_has_entity_name = True
    _attr_name = "Current Grass Height"
    _attr_native_unit_of_measurement = "in"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:grass"

    def __init__(
        self,
        coordinator: GrassGrowthCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
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

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Grass Growth Predictor",
            manufacturer="Custom Integration",
            model="Grass Growth Predictor v1",
            entry_type=DeviceEntryType.SERVICE,
        )

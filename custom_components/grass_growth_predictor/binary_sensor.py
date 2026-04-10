"""Binary sensor platform for Grass Growth Predictor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BINARY_SENSOR_MOW_OVERDUE,
    BINARY_SENSOR_MOW_RECOMMENDED,
    DOMAIN,
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
            MowRecommendedBinarySensor(coordinator, entry),
            MowOverdueBinarySensor(coordinator, entry),
        ]
    )


class _MowBinarySensorBase(CoordinatorEntity[GrassGrowthCoordinator], BinarySensorEntity):
    """Shared base for mow status binary sensors."""

    _attr_has_entity_name = True
    _data_key: str

    def __init__(self, coordinator: GrassGrowthCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{self._data_key}"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return bool(self.coordinator.data.get(self._data_key, False))

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Grass Growth Predictor",
            manufacturer="Custom Integration",
            model="Grass Growth Predictor v1",
            entry_type=DeviceEntryType.SERVICE,
        )


class MowRecommendedBinarySensor(_MowBinarySensorBase):
    """ON when enough time has passed since the last mow (>= min_days_between_mows).

    Use this in automations to send a notification or queue a mow session.
    """

    _attr_name = "Mow Recommended"
    _attr_icon = "mdi:lawnmower"
    _data_key = BINARY_SENSOR_MOW_RECOMMENDED


class MowOverdueBinarySensor(_MowBinarySensorBase):
    """ON when the lawn has not been mowed within max_days_between_mows.

    Use this in automations to trigger an urgent alert or auto-start a mow session.
    """

    _attr_name = "Mow Overdue"
    _attr_icon = "mdi:alert-circle"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _data_key = BINARY_SENSOR_MOW_OVERDUE

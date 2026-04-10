"""Binary sensor platform for Grass Growth Predictor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BINARY_SENSOR_DRY_MOW_WINDOW_SOON,
    BINARY_SENSOR_GRASS_WET,
    BINARY_SENSOR_MOW_NOT_ADVISED,
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
            GrassWetBinarySensor(coordinator, entry),
            MowNotAdvisedBinarySensor(coordinator, entry),
            DryMowWindowSoonBinarySensor(coordinator, entry),
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
    Always ON at max_days regardless of wet/dry grass state.
    """

    _attr_name = "Mow Overdue"
    _attr_icon = "mdi:alert-circle"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _data_key = BINARY_SENSOR_MOW_OVERDUE


class GrassWetBinarySensor(_MowBinarySensorBase):
    """ON when the grass is estimated to be wet.

    Wet conditions are detected from two OWM proxies:
    - Today's accumulated rainfall exceeds the configured rain threshold
    - The current hourly humidity exceeds the configured humidity threshold (dew/overnight moisture)

    When ON, mow sessions are deferred unless a dry window cannot be found
    or the force-mow growth threshold is exceeded.
    """

    _attr_name = "Grass Wet"
    _attr_icon = "mdi:water"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _data_key = BINARY_SENSOR_GRASS_WET


class MowNotAdvisedBinarySensor(_MowBinarySensorBase):
    """ON when conditions are unsuitable for mowing across the entire mow cycle window.

    Fires when the grass is currently wet OR any hourly forecast slot within
    the configured mow cycle duration has significant rain, high precipitation
    probability, or high humidity. Intended as a single green/red indicator
    for a person about to start mowing manually.
    """

    _attr_name = "Mow Not Advised"
    _attr_icon = "mdi:cancel"
    _data_key = BINARY_SENSOR_MOW_NOT_ADVISED


class DryMowWindowSoonBinarySensor(_MowBinarySensorBase):
    """ON when a suitable dry mow window exists within the lookahead period.

    A dry window is a contiguous block of hourly forecast slots
    (at least as long as the configured mow cycle duration) where rain,
    probability of precipitation, and humidity are all below thresholds.
    """

    _attr_name = "Dry Mow Window Soon"
    _attr_icon = "mdi:weather-sunny"
    _data_key = BINARY_SENSOR_DRY_MOW_WINDOW_SOON

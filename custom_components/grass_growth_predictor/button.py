"""Button platform for Grass Growth Predictor."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BUTTON_MARK_MOWED, DOMAIN
from .coordinator import GrassGrowthCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GrassGrowthCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MarkMowedButton(coordinator, entry)])


class MarkMowedButton(CoordinatorEntity[GrassGrowthCoordinator], ButtonEntity):
    """Button that records a mowing event using the configured cut height."""

    _attr_has_entity_name = True
    _attr_name = "Mark Mowed"
    _attr_icon = "mdi:lawnmower"

    def __init__(self, coordinator: GrassGrowthCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{BUTTON_MARK_MOWED}"

    async def async_press(self) -> None:
        await self.coordinator.async_mark_mowed(None)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Grass Growth Predictor",
            manufacturer="Custom Integration",
            model="Grass Growth Predictor v1",
            entry_type=DeviceEntryType.SERVICE,
        )

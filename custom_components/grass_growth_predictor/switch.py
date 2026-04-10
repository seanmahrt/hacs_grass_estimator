"""Switch platform for Grass Growth Predictor."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCH_MOW_SESSION
from .coordinator import GrassGrowthCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GrassGrowthCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MowSessionSwitch(coordinator, entry)])


class MowSessionSwitch(CoordinatorEntity[GrassGrowthCoordinator], SwitchEntity):
    """Switch that initiates or cancels an automated mow session.

    Turn ON  → signals that a mowing session should begin (trigger a mower,
               send a push notification, etc.).
    Turn OFF → cancels the session without recording a completed mow.

    Use the 'Mow Complete' button (or the mark_mowed service) to record
    an actual mowing event and automatically deactivate the session.
    """

    _attr_has_entity_name = True
    _attr_name = "Mow Session Active"
    _attr_icon = "mdi:robot-mower"

    def __init__(self, coordinator: GrassGrowthCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{SWITCH_MOW_SESSION}"

    @property
    def is_on(self) -> bool:
        return self.coordinator.mow_session_active

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_start_mow_session()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_end_mow_session()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Grass Growth Predictor",
            manufacturer="Custom Integration",
            model="Grass Growth Predictor v1",
            entry_type=DeviceEntryType.SERVICE,
        )

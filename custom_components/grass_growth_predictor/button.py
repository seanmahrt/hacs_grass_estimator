"""Button platform for Grass Growth Predictor."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BUTTON_MARK_MOWED, BUTTON_MOW_COMPLETE, DOMAIN
from .coordinator import GrassGrowthCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GrassGrowthCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        MarkMowedButton(coordinator, entry),
        MowCompleteButton(coordinator, entry),
    ])


class MarkMowedButton(CoordinatorEntity[GrassGrowthCoordinator], ButtonEntity):
    """Button that records a manual mowing event using the configured cut height.

    Use this when you mow the lawn yourself (not through the automated session flow).
    Resets the growth timer, stores the cut height, and clears any active mow session
    so the 'Mow Session Active' switch is never left ON accidentally.

    For the end of an automated session, use 'Mow Complete' instead — it does the
    same thing but the intent is explicit.
    """

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


class MowCompleteButton(CoordinatorEntity[GrassGrowthCoordinator], ButtonEntity):
    """Button that records a completed automated mow and ends the active mow session.

    Use this at the end of the automated mowing workflow (e.g. in the node-red flow
    or automation that runs the mower).  It resets the growth timer, stores the cut
    height, and explicitly deactivates the 'Mow Session Active' switch.

    For ad-hoc manual mowing outside of the automated session flow, use 'Mark Mowed'.
    Both buttons now clear the session, so either is safe to press regardless of
    session state — the distinction is only one of intent and workflow clarity.
    """

    _attr_has_entity_name = True
    _attr_name = "Mow Complete"
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator: GrassGrowthCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{BUTTON_MOW_COMPLETE}"

    async def async_press(self) -> None:
        await self.coordinator.async_complete_mow()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Grass Growth Predictor",
            manufacturer="Custom Integration",
            model="Grass Growth Predictor v1",
            entry_type=DeviceEntryType.SERVICE,
        )

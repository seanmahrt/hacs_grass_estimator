"""Grass Growth Predictor integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import CONF_MOWED_TO_HEIGHT, DOMAIN, SERVICE_MARK_MOWED
from .coordinator import GrassGrowthCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

MARK_MOWED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MOWED_TO_HEIGHT): vol.All(
            vol.Coerce(float), vol.Range(min=0.5, max=12.0)
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Grass Growth Predictor from a config entry."""
    coordinator = GrassGrowthCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register the mark_mowed service (idempotent on reload)
    if not hass.services.has_service(DOMAIN, SERVICE_MARK_MOWED):

        async def _handle_mark_mowed(call: ServiceCall) -> None:
            height: float | None = call.data.get(CONF_MOWED_TO_HEIGHT)
            for coord in hass.data[DOMAIN].values():
                await coord.async_mark_mowed(height)

        hass.services.async_register(
            DOMAIN,
            SERVICE_MARK_MOWED,
            _handle_mark_mowed,
            schema=MARK_MOWED_SCHEMA,
        )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the coordinator when options change."""
    coordinator: GrassGrowthCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_MARK_MOWED)
            hass.data.pop(DOMAIN)
    return unload_ok

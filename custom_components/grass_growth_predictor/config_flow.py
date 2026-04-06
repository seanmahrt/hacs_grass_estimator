"""Config flow for the Grass Growth Predictor integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    DEFAULT_ENABLE_GDD,
    DEFAULT_ENABLE_RAIN,
    DEFAULT_ENABLE_SEASONAL,
    DEFAULT_ENABLE_SOIL_MOISTURE,
    DEFAULT_ENABLE_SOIL_TEMP,
    DEFAULT_MOWED_TO_HEIGHT,
    DOMAIN,
    OWM_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)

_STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LATITUDE): cv.latitude,
        vol.Required(CONF_LONGITUDE): cv.longitude,
        vol.Required(CONF_OWM_API_KEY): str,
        vol.Required(CONF_MOWED_TO_HEIGHT, default=DEFAULT_MOWED_TO_HEIGHT): vol.All(
            vol.Coerce(float), vol.Range(min=0.5, max=12.0)
        ),
        vol.Required(CONF_BASE_GROWTH_RATE, default=DEFAULT_BASE_GROWTH_RATE): vol.All(
            vol.Coerce(float), vol.Range(min=0.01, max=2.0)
        ),
        vol.Required(CONF_ENABLE_SEASONAL, default=DEFAULT_ENABLE_SEASONAL): bool,
        vol.Required(CONF_ENABLE_GDD, default=DEFAULT_ENABLE_GDD): bool,
        vol.Required(CONF_ENABLE_RAIN, default=DEFAULT_ENABLE_RAIN): bool,
        vol.Required(CONF_ENABLE_SOIL_MOISTURE, default=DEFAULT_ENABLE_SOIL_MOISTURE): bool,
        vol.Required(CONF_ENABLE_SOIL_TEMP, default=DEFAULT_ENABLE_SOIL_TEMP): bool,
    }
)


async def _validate_owm_api_key(session, api_key: str, lat: float, lon: float) -> bool:
    """Return True if the OWM API key is accepted by the server."""
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "exclude": "minutely,hourly,daily,alerts",
    }
    try:
        async with asyncio.timeout(10):
            async with session.get(OWM_BASE_URL, params=params) as resp:
                return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


class GrassGrowthPredictorConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle a config flow for Grass Growth Predictor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                valid = await _validate_owm_api_key(
                    session,
                    user_input[CONF_OWM_API_KEY],
                    user_input[CONF_LATITUDE],
                    user_input[CONF_LONGITUDE],
                )
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            else:
                if not valid:
                    errors[CONF_OWM_API_KEY] = "invalid_api_key"
                else:
                    unique_id = (
                        f"{user_input[CONF_LATITUDE]:.4f}_{user_input[CONF_LONGITUDE]:.4f}"
                    )
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Grass Growth Predictor",
                        data=user_input,
                    )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE,
                    default=(user_input or {}).get(CONF_LATITUDE, self.hass.config.latitude),
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE,
                    default=(user_input or {}).get(CONF_LONGITUDE, self.hass.config.longitude),
                ): cv.longitude,
                vol.Required(CONF_OWM_API_KEY): str,
                vol.Required(
                    CONF_MOWED_TO_HEIGHT,
                    default=(user_input or {}).get(CONF_MOWED_TO_HEIGHT, DEFAULT_MOWED_TO_HEIGHT),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=12.0)),
                vol.Required(
                    CONF_BASE_GROWTH_RATE,
                    default=(user_input or {}).get(CONF_BASE_GROWTH_RATE, DEFAULT_BASE_GROWTH_RATE),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=2.0)),
                vol.Required(
                    CONF_ENABLE_SEASONAL,
                    default=(user_input or {}).get(CONF_ENABLE_SEASONAL, DEFAULT_ENABLE_SEASONAL),
                ): bool,
                vol.Required(
                    CONF_ENABLE_GDD,
                    default=(user_input or {}).get(CONF_ENABLE_GDD, DEFAULT_ENABLE_GDD),
                ): bool,
                vol.Required(
                    CONF_ENABLE_RAIN,
                    default=(user_input or {}).get(CONF_ENABLE_RAIN, DEFAULT_ENABLE_RAIN),
                ): bool,
                vol.Required(
                    CONF_ENABLE_SOIL_MOISTURE,
                    default=(user_input or {}).get(
                        CONF_ENABLE_SOIL_MOISTURE, DEFAULT_ENABLE_SOIL_MOISTURE
                    ),
                ): bool,
                vol.Required(
                    CONF_ENABLE_SOIL_TEMP,
                    default=(user_input or {}).get(CONF_ENABLE_SOIL_TEMP, DEFAULT_ENABLE_SOIL_TEMP),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GrassGrowthOptionsFlow:
        return GrassGrowthOptionsFlow(config_entry)


class GrassGrowthOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Grass Growth Predictor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MOWED_TO_HEIGHT,
                    default=current.get(CONF_MOWED_TO_HEIGHT, DEFAULT_MOWED_TO_HEIGHT),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=12.0)),
                vol.Required(
                    CONF_BASE_GROWTH_RATE,
                    default=current.get(CONF_BASE_GROWTH_RATE, DEFAULT_BASE_GROWTH_RATE),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=2.0)),
                vol.Required(
                    CONF_ENABLE_SEASONAL,
                    default=current.get(CONF_ENABLE_SEASONAL, DEFAULT_ENABLE_SEASONAL),
                ): bool,
                vol.Required(
                    CONF_ENABLE_GDD,
                    default=current.get(CONF_ENABLE_GDD, DEFAULT_ENABLE_GDD),
                ): bool,
                vol.Required(
                    CONF_ENABLE_RAIN,
                    default=current.get(CONF_ENABLE_RAIN, DEFAULT_ENABLE_RAIN),
                ): bool,
                vol.Required(
                    CONF_ENABLE_SOIL_MOISTURE,
                    default=current.get(CONF_ENABLE_SOIL_MOISTURE, DEFAULT_ENABLE_SOIL_MOISTURE),
                ): bool,
                vol.Required(
                    CONF_ENABLE_SOIL_TEMP,
                    default=current.get(CONF_ENABLE_SOIL_TEMP, DEFAULT_ENABLE_SOIL_TEMP),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

"""Config flow for the Grass Growth Predictor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_BASE_GROWTH_RATE,
    CONF_DRY_WINDOW_LOOKAHEAD_HOURS,
    CONF_ENABLE_GDD,
    CONF_ENABLE_RAIN,
    CONF_ENABLE_SEASONAL,
    CONF_ENABLE_SOIL_MOISTURE,
    CONF_ENABLE_SOIL_TEMP,
    CONF_FORCE_MOW_GROWTH_THRESHOLD,
    CONF_MAX_DAYS_BETWEEN_MOWS,
    CONF_MAX_GROWTH_BETWEEN_MOWS,
    CONF_MIN_DAYS_BETWEEN_MOWS,
    CONF_MOW_CYCLE_DURATION_HOURS,
    CONF_MOWED_TO_HEIGHT,
    CONF_WEATHER_ENTITY,
    CONF_WET_HUMIDITY_PCT,
    CONF_WET_RAIN_THRESHOLD_IN,
    DEFAULT_BASE_GROWTH_RATE,
    DEFAULT_DRY_WINDOW_LOOKAHEAD_HOURS,
    DEFAULT_ENABLE_GDD,
    DEFAULT_ENABLE_RAIN,
    DEFAULT_ENABLE_SEASONAL,
    DEFAULT_ENABLE_SOIL_MOISTURE,
    DEFAULT_ENABLE_SOIL_TEMP,
    DEFAULT_FORCE_MOW_GROWTH_THRESHOLD,
    DEFAULT_MAX_DAYS_BETWEEN_MOWS,
    DEFAULT_MAX_GROWTH_BETWEEN_MOWS,
    DEFAULT_MIN_DAYS_BETWEEN_MOWS,
    DEFAULT_MOW_CYCLE_DURATION_HOURS,
    DEFAULT_MOWED_TO_HEIGHT,
    DEFAULT_WEATHER_ENTITY,
    DEFAULT_WET_HUMIDITY_PCT,
    DEFAULT_WET_RAIN_THRESHOLD_IN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LATITUDE): cv.latitude,
        vol.Required(CONF_LONGITUDE): cv.longitude,
        vol.Required(CONF_WEATHER_ENTITY, default=DEFAULT_WEATHER_ENTITY): EntitySelector(
            EntitySelectorConfig(domain="weather")
        ),
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


class GrassGrowthPredictorConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle a config flow for Grass Growth Predictor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            weather_entity_id = user_input.get(CONF_WEATHER_ENTITY, DEFAULT_WEATHER_ENTITY)
            if self.hass.states.get(weather_entity_id) is None:
                errors[CONF_WEATHER_ENTITY] = "entity_not_found"
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
                vol.Required(
                    CONF_WEATHER_ENTITY,
                    default=(user_input or {}).get(CONF_WEATHER_ENTITY, DEFAULT_WEATHER_ENTITY),
                ): EntitySelector(EntitySelectorConfig(domain="weather")),
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
        return GrassGrowthOptionsFlow()


class GrassGrowthOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Grass Growth Predictor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                vol.Required(
                    CONF_MIN_DAYS_BETWEEN_MOWS,
                    default=current.get(CONF_MIN_DAYS_BETWEEN_MOWS, DEFAULT_MIN_DAYS_BETWEEN_MOWS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
                vol.Required(
                    CONF_MAX_DAYS_BETWEEN_MOWS,
                    default=current.get(CONF_MAX_DAYS_BETWEEN_MOWS, DEFAULT_MAX_DAYS_BETWEEN_MOWS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_MAX_GROWTH_BETWEEN_MOWS,
                    default=current.get(CONF_MAX_GROWTH_BETWEEN_MOWS, DEFAULT_MAX_GROWTH_BETWEEN_MOWS),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=6.0)),
                vol.Required(
                    CONF_FORCE_MOW_GROWTH_THRESHOLD,
                    default=current.get(CONF_FORCE_MOW_GROWTH_THRESHOLD, DEFAULT_FORCE_MOW_GROWTH_THRESHOLD),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=6.0)),
                vol.Required(
                    CONF_MOW_CYCLE_DURATION_HOURS,
                    default=current.get(CONF_MOW_CYCLE_DURATION_HOURS, DEFAULT_MOW_CYCLE_DURATION_HOURS),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=24.0)),
                vol.Required(
                    CONF_WET_RAIN_THRESHOLD_IN,
                    default=current.get(CONF_WET_RAIN_THRESHOLD_IN, DEFAULT_WET_RAIN_THRESHOLD_IN),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=2.0)),
                vol.Required(
                    CONF_WET_HUMIDITY_PCT,
                    default=current.get(CONF_WET_HUMIDITY_PCT, DEFAULT_WET_HUMIDITY_PCT),
                ): vol.All(vol.Coerce(int), vol.Range(min=50, max=100)),
                vol.Required(
                    CONF_DRY_WINDOW_LOOKAHEAD_HOURS,
                    default=current.get(CONF_DRY_WINDOW_LOOKAHEAD_HOURS, DEFAULT_DRY_WINDOW_LOOKAHEAD_HOURS),
                ): vol.All(vol.Coerce(int), vol.Range(min=6, max=48)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

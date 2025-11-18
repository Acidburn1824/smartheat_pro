from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TEMP_SENSOR,
    CONF_HEATER_ENTITY,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_ECO_TEMP,
    CONF_COMFORT_TEMP,
    CONF_COMFORT_PLUS_TEMP,
    CONF_BOOST_TEMP,
    CONF_HYSTERESIS,
    CONF_BOOST_DURATION,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_ECO_TEMP,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_COMFORT_PLUS_TEMP,
    DEFAULT_BOOST_TEMP,
    DEFAULT_HYSTERESIS,
    DEFAULT_BOOST_DURATION,
)

_LOGGER = logging.getLogger(__name__)


class SmartHeatProConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour SmartHeat Pro."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME)
            if not name:
                errors[CONF_NAME] = "required"

            if not errors:
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="SmartHeat Pro Salon"): TextSelector(
                    TextSelectorConfig(multiline=False)
                ),
                vol.Required(CONF_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=["sensor", "climate"])
                ),
                vol.Required(CONF_HEATER_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain=["switch", "climate"])
                ),
                vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=15,
                        step=0.5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): NumberSelector(
                    NumberSelectorConfig(
                        min=15,
                        max=30,
                        step=0.5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_ECO_TEMP, default=DEFAULT_ECO_TEMP): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=25,
                        step=0.5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_COMFORT_TEMP, default=DEFAULT_COMFORT_TEMP): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=25,
                        step=0.5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_COMFORT_PLUS_TEMP, default=DEFAULT_COMFORT_PLUS_TEMP): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=25,
                        step=0.5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=25,
                        step=0.5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): NumberSelector(
                    NumberSelectorConfig(
                        min=0.1,
                        max=1.0,
                        step=0.1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_BOOST_DURATION, default=DEFAULT_BOOST_DURATION): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=120,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]):
        """Import YAML (non utilisé ici)."""
        return await self.async_step_user(user_input)

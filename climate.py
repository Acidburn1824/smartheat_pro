from __future__ import annotations

import logging
from datetime import timedelta, datetime
from typing import Any, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.components.climate.const import (
    ATTR_TEMPERATURE,
)
from homeassistant.const import (
    TEMP_CELSIUS,
    STATE_ON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    ATTR_LEARNED_HEAT_RATE,
    ATTR_LAST_HEATING_START,
    ATTR_LAST_HEATING_STOP,
    ATTR_BOOST_END,
    ATTR_IS_HEATING,
)
from .helpers import get_state_float, safe_float, now_utc

_LOGGER = logging.getLogger(__name__)

PRESET_ECO = "eco"
PRESET_COMFORT = "comfort"
PRESET_COMFORT_PLUS = "comfort_plus"
PRESET_BOOST = "boost"

SCAN_INTERVAL = timedelta(seconds=30)  # fréquence de check


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up climate entity from config entry."""
    data = entry.data

    name = data.get(CONF_NAME, entry.title)
    temp_sensor = data[CONF_TEMP_SENSOR]
    heater = data[CONF_HEATER_ENTITY]

    entity = SmartHeatProThermostat(
        hass=hass,
        entry_id=entry.entry_id,
        name=name,
        temp_sensor=temp_sensor,
        heater_entity=heater,
        min_temp=safe_float(data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP), DEFAULT_MIN_TEMP),
        max_temp=safe_float(data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP), DEFAULT_MAX_TEMP),
        eco_temp=safe_float(data.get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP), DEFAULT_ECO_TEMP),
        comfort_temp=safe_float(data.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP), DEFAULT_COMFORT_TEMP),
        comfort_plus_temp=safe_float(
            data.get(CONF_COMFORT_PLUS_TEMP, DEFAULT_COMFORT_PLUS_TEMP), DEFAULT_COMFORT_PLUS_TEMP
        ),
        boost_temp=safe_float(data.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP), DEFAULT_BOOST_TEMP),
        hysteresis=safe_float(data.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS), DEFAULT_HYSTERESIS),
        boost_duration=int(data.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION)),
    )

    async_add_entities([entity])


class SmartHeatProThermostat(ClimateEntity):
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_ECO, PRESET_COMFORT, PRESET_COMFORT_PLUS, PRESET_BOOST]

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        temp_sensor: str,
        heater_entity: str,
        min_temp: float,
        max_temp: float,
        eco_temp: float,
        comfort_temp: float,
        comfort_plus_temp: float,
        boost_temp: float,
        hysteresis: float,
        boost_duration: int,
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_climate"
        self._attr_name = name

        self._temp_sensor = temp_sensor
        self._heater_entity = heater_entity

        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp

        self._eco_temp = eco_temp
        self._comfort_temp = comfort_temp
        self._comfort_plus_temp = comfort_plus_temp
        self._boost_temp = boost_temp
        self._hysteresis = hysteresis
        self._boost_duration = boost_duration  # minutes

        self._attr_preset_mode = PRESET_COMFORT
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_target_temperature = self._comfort_temp
        self._attr_current_temperature: Optional[float] = None
        self._attr_hvac_action = HVACAction.IDLE

        # apprentissage simple : °C/heure (placeholder v1)
        self._learned_heat_rate: Optional[float] = None
        self._last_heating_start: Optional[str] = None
        self._last_heating_stop: Optional[str] = None

        self._boost_end: Optional[str] = None
        self._is_heating = False

        self._unsub_temp = None
        self._unsub_timer = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            manufacturer="SmartHeat Pro",
            name=self._attr_name,
            model="SmartHeat Pro v0.0.1",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            ATTR_LEARNED_HEAT_RATE: self._learned_heat_rate,
            ATTR_LAST_HEATING_START: self._last_heating_start,
            ATTR_LAST_HEATING_STOP: self._last_heating_stop,
            ATTR_BOOST_END: self._boost_end,
            ATTR_IS_HEATING: self._is_heating,
            "eco_temp": self._eco_temp,
            "comfort_temp": self._comfort_temp,
            "comfort_plus_temp": self._comfort_plus_temp,
            "boost_temp": self._boost_temp,
            "hysteresis": self._hysteresis,
        }

    async def async_added_to_hass(self) -> None:
        """Called when entity is added."""
        _LOGGER.debug("SmartHeat Pro %s ajouté", self._attr_name)

        @callback
        def temp_changed(event):
            self._update_current_temperature()
            self._async_control_heating()

        self._unsub_temp = async_track_state_change_event(
            self.hass, [self._temp_sensor], temp_changed
        )

        self._unsub_timer = async_track_time_interval(
            self.hass, lambda now: self._async_control_heating(), SCAN_INTERVAL
        )

        self._update_current_temperature()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup on remove."""
        if self._unsub_temp:
            self._unsub_temp()
        if self._unsub_timer:
            self._unsub_timer()

    def _update_current_temperature(self):
        temp = get_state_float(self.hass, self._temp_sensor, None)
        if temp is not None:
            self._attr_current_temperature = temp

    # --------------------
    # Gestion des presets
    # --------------------
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self._attr_preset_modes:
            _LOGGER.warning("Preset inconnu: %s", preset_mode)
            return
        self._attr_preset_mode = preset_mode

        if preset_mode == PRESET_ECO:
            self._attr_target_temperature = self._eco_temp
            self._boost_end = None
        elif preset_mode == PRESET_COMFORT:
            self._attr_target_temperature = self._comfort_temp
            self._boost_end = None
        elif preset_mode == PRESET_COMFORT_PLUS:
            self._attr_target_temperature = self._comfort_plus_temp
            self._boost_end = None
        elif preset_mode == PRESET_BOOST:
            self._attr_target_temperature = self._boost_temp
            boost_end = now_utc() + timedelta(minutes=self._boost_duration)
            self._boost_end = boost_end.isoformat()

        await self._async_control_heating(force=True)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self._attr_hvac_modes:
            return
        self._attr_hvac_mode = hvac_mode
        await self._async_control_heating(force=True)
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        temp = safe_float(temp, None)
        if temp is None:
            return
        self._attr_target_temperature = temp
        # on ne change pas le preset automatiquement ici
        await self._async_control_heating(force=True)
        self.async_write_ha_state()

    # --------------------
    # Logique de régulation
    # --------------------
    async def _async_turn_heater_on(self):
        state = self.hass.states.get(self._heater_entity)
        if state and state.state == STATE_ON:
            return
        _LOGGER.debug("%s: allumage chauffage %s", self._attr_name, self._heater_entity)
        self._is_heating = True
        self._attr_hvac_action = HVACAction.HEATING
        self._last_heating_start = now_utc().isoformat()

        domain = self._heater_entity.split(".")[0]
        await self.hass.services.async_call(
            domain,
            "turn_on",
            {"entity_id": self._heater_entity},
            blocking=False,
        )

    async def _async_turn_heater_off(self):
        state = self.hass.states.get(self._heater_entity)
        if state and state.state == STATE_OFF:
            return
        _LOGGER.debug("%s: extinction chauffage %s", self._attr_name, self._heater_entity)
        self._is_heating = False
        self._attr_hvac_action = HVACAction.IDLE
        self._last_heating_stop = now_utc().isoformat()

        # placeholder pour apprentissage futur

        domain = self._heater_entity.split(".")[0]
        await self.hass.services.async_call(
            domain,
            "turn_off",
            {"entity_id": self._heater_entity},
            blocking=False,
        )

    async def _async_control_heating(self, force: bool = False):
        """Contrôle principal du chauffage."""
        if self._attr_hvac_mode == HVACMode.OFF:
            await self._async_turn_heater_off()
            self.async_write_ha_state()
            return

        self._update_current_temperature()
        current = self._attr_current_temperature
        target = self._attr_target_temperature
        if current is None or target is None:
            _LOGGER.debug("%s: température inconnue, pas de régulation", self._attr_name)
            return

        # gestion fin de boost
        if self._attr_preset_mode == PRESET_BOOST and self._boost_end is not None:
            try:
                boost_end = datetime.fromisoformat(self._boost_end)
            except Exception:
                boost_end = None
            now = now_utc()
            if boost_end and now >= boost_end:
                # retour confort
                self._attr_preset_mode = PRESET_COMFORT
                self._attr_target_temperature = self._comfort_temp
                self._boost_end = None
                _LOGGER.info("%s: fin du boost, retour en mode confort", self._attr_name)

        # Hystérésis : ON si < (target - hyst), OFF si > (target + hyst)
        h = self._hysteresis
        turn_on_threshold = target - h
        turn_off_threshold = target + h

        if force:
            _LOGGER.debug(
                "%s: contrôle forcé - current=%.2f target=%.2f (%.2f/%.2f)",
                self._attr_name,
                current,
                target,
                turn_on_threshold,
                turn_off_threshold,
            )

        if not self._is_heating and current < turn_on_threshold:
            await self._async_turn_heater_on()
        elif self._is_heating and current > turn_off_threshold:
            await self._async_turn_heater_off()

        self.async_write_ha_state()

"""Provides device automations for Alarm control panel."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TYPE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

BASIC_TRIGGER_TYPES = {"triggered", "disarmed", "arming"}
TRIGGER_TYPES = BASIC_TRIGGER_TYPES | {"armed_home", "armed_away", "armed_night"}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for Alarm control panel devices."""
    registry = await entity_registry.async_get_registry(hass)
    triggers = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        entity_state = hass.states.get(entry.entity_id)

        # We need a state or else we can't populate the HVAC and preset modes.
        if entity_state is None:
            continue

        supported_features = entity_state.attributes[ATTR_SUPPORTED_FEATURES]

        # Add triggers for each entity that belongs to this integration
        base_trigger = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        triggers += [
            {
                **base_trigger,
                CONF_TYPE: trigger,
            }
            for trigger in BASIC_TRIGGER_TYPES
        ]
        if supported_features & SUPPORT_ALARM_ARM_HOME:
            triggers.append(
                {
                    **base_trigger,
                    CONF_TYPE: "armed_home",
                }
            )
        if supported_features & SUPPORT_ALARM_ARM_AWAY:
            triggers.append(
                {
                    **base_trigger,
                    CONF_TYPE: "armed_away",
                }
            )
        if supported_features & SUPPORT_ALARM_ARM_NIGHT:
            triggers.append(
                {
                    **base_trigger,
                    CONF_TYPE: "armed_night",
                }
            )

    return triggers


async def async_get_trigger_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List trigger capabilities."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if config[CONF_TYPE] == "triggered":
        to_state = STATE_ALARM_TRIGGERED
    elif config[CONF_TYPE] == "disarmed":
        to_state = STATE_ALARM_DISARMED
    elif config[CONF_TYPE] == "arming":
        to_state = STATE_ALARM_ARMING
    elif config[CONF_TYPE] == "armed_home":
        to_state = STATE_ALARM_ARMED_HOME
    elif config[CONF_TYPE] == "armed_away":
        to_state = STATE_ALARM_ARMED_AWAY
    elif config[CONF_TYPE] == "armed_night":
        to_state = STATE_ALARM_ARMED_NIGHT

    state_config = {
        state_trigger.CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state_trigger.CONF_TO: to_state,
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]
    state_config = state_trigger.TRIGGER_SCHEMA(state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )

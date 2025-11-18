from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN


def safe_float(value, default: float | None = None) -> Optional[float]:
    try:
        v = float(value)
        if v != v:  # NaN
            return default
        return v
    except (TypeError, ValueError):
        return default


def get_state_float(hass: HomeAssistant, entity_id: str, default=None) -> Optional[float]:
    state = hass.states.get(entity_id)
    if not state or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return default
    return safe_float(state.state, default)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)

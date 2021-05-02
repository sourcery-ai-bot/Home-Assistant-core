"""Test SMHI component setup process."""
from unittest.mock import Mock

from homeassistant.components import smhi

from .common import AsyncMock

TEST_CONFIG = {
    "config": {
        "name": "0123456789ABCDEF",
        "longitude": "62.0022",
        "latitude": "17.0022",
    }
}


async def test_forward_async_setup_entry() -> None:
    """Test that it will forward setup entry."""
    hass = Mock()

    assert await smhi.async_setup_entry(hass, {}) is True
    assert len(hass.config_entries.async_setup_platforms.mock_calls) == 1


async def test_forward_async_unload_entry() -> None:
    """Test that it will forward unload entry."""
    hass = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    assert await smhi.async_unload_entry(hass, {}) is True
    assert len(hass.config_entries.async_unload_platforms.mock_calls) == 1

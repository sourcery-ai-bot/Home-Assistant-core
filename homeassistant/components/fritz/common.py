"""Support for AVM FRITZ!Box classes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

# pylint: disable=import-error
from fritzconnection import FritzConnection
from fritzconnection.lib.fritzhosts import FritzHosts
from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    TRACKER_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class Device:
    """FRITZ!Box device class."""

    mac: str
    ip_address: str
    name: str


class FritzBoxTools:
    """FrtizBoxTools class."""

    def __init__(
        self,
        hass,
        password,
        username=DEFAULT_USERNAME,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
    ):
        """Initialize FritzboxTools class."""
        self._cancel_scan = None
        self._device_info = None
        self._devices: dict[str, Any] = {}
        self._unique_id = None
        self.connection = None
        self.fritzhosts = None
        self.fritzstatus = None
        self.hass = hass
        self.host = host
        self.password = password
        self.port = port
        self.username = username

    async def async_setup(self):
        """Wrap up FritzboxTools class setup."""
        return await self.hass.async_add_executor_job(self.setup)

    def setup(self):
        """Set up FritzboxTools class."""
        self.connection = FritzConnection(
            address=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            timeout=60.0,
        )

        self.fritzstatus = FritzStatus(fc=self.connection)
        if self._unique_id is None:
            self._unique_id = self.connection.call_action("DeviceInfo:1", "GetInfo")[
                "NewSerialNumber"
            ]

        self._device_info = self._fetch_device_info()

    async def async_start(self):
        """Start FritzHosts connection."""
        self.fritzhosts = FritzHosts(fc=self.connection)

        await self.hass.async_add_executor_job(self.scan_devices)

        self._cancel_scan = async_track_time_interval(
            self.hass, self.scan_devices, timedelta(seconds=TRACKER_SCAN_INTERVAL)
        )

    @callback
    def async_unload(self):
        """Unload FritzboxTools class."""
        _LOGGER.debug("Unloading FRITZ!Box router integration")
        if self._cancel_scan is not None:
            self._cancel_scan()
            self._cancel_scan = None

    @property
    def unique_id(self):
        """Return unique id."""
        return self._unique_id

    @property
    def fritzbox_model(self):
        """Return model."""
        return self._device_info["model"].replace("FRITZ!Box ", "")

    @property
    def device_info(self):
        """Return device info."""
        return self._device_info

    @property
    def devices(self) -> dict[str, Any]:
        """Return devices."""
        return self._devices

    @property
    def signal_device_new(self) -> str:
        """Event specific per FRITZ!Box entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._unique_id}"

    @property
    def signal_device_update(self) -> str:
        """Event specific per FRITZ!Box entry to signal updates in devices."""
        return f"{DOMAIN}-device-update-{self._unique_id}"

    def _update_info(self):
        """Retrieve latest information from the FRITZ!Box."""
        return self.fritzhosts.get_hosts_info()

    def scan_devices(self, now: datetime | None = None) -> None:
        """Scan for new devices and return a list of found device ids."""
        _LOGGER.debug("Checking devices for FRITZ!Box router %s", self.host)

        new_device = False
        for known_host in self._update_info():
            if not known_host.get("mac"):
                continue

            dev_mac = known_host["mac"]
            dev_name = known_host["name"]
            dev_ip = known_host["ip"]
            dev_home = known_host["status"]

            dev_info = Device(dev_mac, dev_ip, dev_name)

            if dev_mac in self._devices:
                self._devices[dev_mac].update(dev_info, dev_home)
            else:
                device = FritzDevice(dev_mac)
                device.update(dev_info, dev_home)
                self._devices[dev_mac] = device
                new_device = True

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    def _fetch_device_info(self):
        """Fetch device info."""
        info = self.connection.call_action("DeviceInfo:1", "GetInfo")

        dev_info = {}
        dev_info["identifiers"] = {
            # Serial numbers are unique identifiers within a specific domain
            (DOMAIN, self.unique_id)
        }
        dev_info["manufacturer"] = "AVM"

        if dev_name := info.get("NewName"):
            dev_info["name"] = dev_name
        if dev_model := info.get("NewModelName"):
            dev_info["model"] = dev_model
        if dev_sw_ver := info.get("NewSoftwareVersion"):
            dev_info["sw_version"] = dev_sw_ver

        return dev_info


class FritzData:
    """Storage class for platform global data."""

    def __init__(self) -> None:
        """Initialize the data."""
        self.tracked = {}


class FritzDevice:
    """FritzScanner device."""

    def __init__(self, mac, name=None):
        """Initialize device info."""
        self._mac = mac
        self._name = name
        self._ip_address = None
        self._last_activity = None
        self._connected = False

    def update(self, dev_info, dev_home):
        """Update device info."""
        utc_point_in_time = dt_util.utcnow()
        if not self._name:
            self._name = dev_info.name or self._mac.replace(":", "_")
        self._connected = dev_home

        if not self._connected:
            self._ip_address = None
            return

        self._last_activity = utc_point_in_time
        self._ip_address = dev_info.ip_address

    @property
    def is_connected(self):
        """Return connected status."""
        return self._connected

    @property
    def mac_address(self):
        """Get MAC address."""
        return self._mac

    @property
    def hostname(self):
        """Get Name."""
        return self._name

    @property
    def ip_address(self):
        """Get IP address."""
        return self._ip_address

    @property
    def last_activity(self):
        """Return device last activity."""
        return self._last_activity

from datetime import timedelta
import logging
import aiohttp
import math
import re
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import asyncio
from random import random

from homeassistant import config_entries
from homeassistant.const import STATE_ON, STATE_OFF, CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, KEY_POESWITCH

CONF_DEVICES = "devices"
SCAN_INTERVAL = 30

_LOGGER = logging.getLogger(__name__)

DEVICES_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICES_SCHEMA])}),
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    """Set up the Zyxel POE component."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for device_config in conf[CONF_DEVICES]:
        host = device_config.get(CONF_HOST)
        name = device_config.get(CONF_NAME)
        password = device_config.get(CONF_PASSWORD)
        interval = device_config.get(CONF_SCAN_INTERVAL)

        data = {
            CONF_HOST: host,
            CONF_NAME: name,
            CONF_PASSWORD: password,
            CONF_SCAN_INTERVAL: interval
        }

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
                data=data
            )
        )

    return True


FORWARD_PLATFORMS = (
    "sensor",
    "switch",
)

async def async_setup_entry(hass, entry):
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]

    if not name or len(name) == 0:
        name = host
    
    password = entry.data[CONF_PASSWORD]
    interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug(f"using {interval}s update interval")
    coordinator = ZyxelCoordinator(hass, name, host, password, interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(KEY_POESWITCH, {})[entry.entry_id] = coordinator
    for platform in FORWARD_PLATFORMS:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, platform))

    return True

# Generate a random number
def randomStr():
    randomStrArr = ['0','1','2','3','4','5','6','7','8','9',
                        'a','b','c','d','e','f','g','h','i','j','k','l','m',
                        'n','o','p','q','r','s','t','u','v','w','x','y','z',
                        'A','B','C','D','E','F','G','H','I','J','K','L','M',
                        'N','O','P','Q','R','S','T','U','V','W','X','Y','Z'
                        ]
    index = math.floor(random() * len(randomStrArr))

    return randomStrArr[index]

# Encrypt the string
def encode(_input):
    pwdStrArr = [*_input]
    pwdFinalStr = ""
    for i in range(len(pwdStrArr)+1):
        if (i == len(pwdStrArr)):
            pwdFinalStr += randomStr()
            break
        else:
            code = ord(pwdStrArr[i])
            tempStr = chr(code - len(pwdStrArr))
            pwdFinalStr += randomStr() + tempStr

    return pwdFinalStr

def int_to_bool_list(num):
    return [bool(num & (1<<n)) for n in range(4)]

def bool_list_to_int(bools):
    return int(''.join(str(int(i)) for i in reversed(bools)), 2)

class ZyxelCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, name, host, password, interval):
        super().__init__(
            hass,
            _LOGGER,
            name="Zyxel POE",
            update_interval=timedelta(seconds=interval),
        )

        async def on_hass_stop(event):
            """Close connection when hass stops."""
            await self.logout()
    
        self.cancel = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)

        self.ports = {}
        self._client = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar(unsafe=True))

        _LOGGER.debug(f"Created coordinator with name: {name}")
        self._name = name
        self._host = host
        self._password = password

    def __del__(self):
        _LOGGER.info("removing shutdown hook")
        self.cancel()

    def get_port_power(self, port):
        p = self.ports.get(port)
        if p:
            return p.get('power', 0)
        return 0

    def get_port_state(self, port):
        p = self.ports.get(port)
        if p:
            return p.get('state', STATE_ON)
        return STATE_ON

    def set_port_state(self, port, state):
        p = self.ports.get(port)
        if not p:
            self.ports[port] = {}
        self.ports[port]['state'] = state

    async def logout(self):
        _LOGGER.info("Logging out")
        try:
            url = f"http://{self._host}/logout.html"
            await self._client.get(url)
        except Exception as ex:
            _LOGGER.warn(ex)
            pass

    def _have_login_cookie(self):
        if 'token' in [c.key for c in self._client.cookie_jar]:
            _LOGGER.debug("Cookie contains a login token")
            return True
        return False

    def _clear_login_cookie(self):
        _LOGGER.debug("Login cookie no longer valid. Clearing cookies")
        self._client._client.cookie_jar.clear()

    async def _login(self):
        if self._have_login_cookie():
            return
        _LOGGER.debug("Logging in")

        login_data = {
            "password": encode(self._password),
        }

        url = f"http://{self._host}/login.cgi"
        resp = await self._client.post(url, data=login_data)
        text = await resp.text()
        _LOGGER.debug(f"POST to {url} returned status code: {resp.status}")
        if resp.ok and self._have_login_cookie():
            _LOGGER.info("Logged in successfully")
            return
        _LOGGER.debug(f"Login failed: {text}")
        raise UpdateFailed(f"Login failed: {text}")

    async def change_state(self, is_retry=False):
        if is_retry:
            _LOGGER.warn("retry changing port state")
        url = f"http://{self._host}/port_state_set.cgi"
        try:
            with async_timeout.timeout(10):
                await self._login()
                switches = [True if o.get("state", STATE_ON) == STATE_ON else False for _, o in self.ports.items()]
                data = {
                    "g_port_state": 31,
                    "g_port_flwcl": 0,
                    "g_port_poe": bool_list_to_int(switches),
                    "g_port_speed0": 0,
                    "g_port_speed1":0,
                    "g_port_speed2":0,
                    "g_port_speed3":0,
                    "g_port_speed4":0
                }
                _LOGGER.debug(f"POST {data} to {url}")
                resp = await self._client.post(url, data=data)
                text = await resp.text()
                if not resp.ok:
                    raise UpdateFailed(f"Changing state failed: {text}")

                if re.search(r'action="login.cgi"', text):
                    _LOGGER.info("login required. retrying")
                    self._clear_login_cookie()
                    if not is_retry:
                        await self.change_state(is_retry=True)
                else:
                    _LOGGER.info("State change successful")

        except (asyncio.TimeoutError, aiohttp.ClientError) as ex:
            if not is_retry:
                await asyncio.sleep(5)
                await self.change_state(is_retry=True)
                pass
            raise UpdateFailed(f"Connection error during change state: {ex}") from ex

    async def _fetch_poe_port_state(self):
        url = f"http://{self._host}/port_state_data.js"
        resp = await self._client.get(url)
        text = await resp.text()
        _LOGGER.debug(f"GET {url} returned status code: {resp.status}")
        if not resp.ok:
            raise UpdateFailed(f"Refresh failed: {text}")

        m = re.findall(r"portPoE\s?=\s?'(\d+)';", text)
        if m and len(m) >= 1:
            switches = int_to_bool_list(int(m[0]))
            for i, val in enumerate(switches):
                _LOGGER.debug(f"Port {i} state {val}")
                if not self.ports.get(i):
                    self.ports[i] = {}
                self.ports[i]["state"] = STATE_ON if val else STATE_OFF
        else:
            if re.search(r'action="login.cgi"', text):
                self._clear_login_cookie()
            else:
                _LOGGER.warn(f"Unexpected response received during update state: {text}")

    async def _fetch_poe_port_power(self):
        url = f"http://{self._host}/poe_data.js"
        resp = await self._client.get(url)
        text = await resp.text()
        _LOGGER.debug(f"GET {url} returned status code: {resp.status}")
        if not resp.ok:
            raise UpdateFailed(f"Refresh failed: {text}")

        m = re.findall(r"port_power\s?=\s?\[([\s\d+\.,]+)\]", text)
        if m and len(m) >= 1:
            powers = [x.strip() for x in m[0].split(',')]
            for i, val in enumerate(powers):
                _LOGGER.debug(f"Port {i} power {val}W")
                if not self.ports.get(i):
                    self.ports[i] = {}
                self.ports[i]["power"] = float(val)
        else:
            if re.search(r'action="login.cgi"', text):
                self._clear_login_cookie()
            else:
                _LOGGER.warn(f"Unexpected response received during update state: {text}")

    async def _async_update_data(self):
        _LOGGER.debug("Polling for updates")
        try:
            with async_timeout.timeout(10):
                await self._login()
                await self._fetch_poe_port_state()
                await self._fetch_poe_port_power()
        except (asyncio.TimeoutError, aiohttp.ClientError) as ex:
            raise UpdateFailed(f"Connection error during update: {ex}") from ex

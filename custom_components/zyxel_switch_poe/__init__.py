import re
import math
import logging
import asyncio

from random import random
from datetime import timedelta

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.const import STATE_ON, STATE_OFF, CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_STOP

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, KEY_POESWITCH, METHOD_POST, METHOD_GET, BRAND

MAX_HTTP_RETRIES = 3
MAX_APP_RETRIES = 2
CONF_DEVICES = "devices"

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

    _LOGGER.debug(f"Using {interval}s update interval")
    coordinator = ZyxelCoordinator(hass, name, host, password, interval)

    await coordinator.async_config_entry_first_refresh()

    dev_reg = dr.async_get(hass)

    dev_reg.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={(dr.CONNECTION_NETWORK_MAC, coordinator.device_info['mac'])},
                identifiers={
                    (DOMAIN, host)
                },
                manufacturer=BRAND,
                name=coordinator.device_info['name'],
                model=coordinator.device_info['model'],
                sw_version=coordinator.device_info['sw_version']
            )
    hass.data.setdefault(KEY_POESWITCH, {})[entry.entry_id] = coordinator
    for platform in FORWARD_PLATFORMS:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, platform))

    return True

# Generate a random number
def random_str():
    random_str_arr = ['0','1','2','3','4','5','6','7','8','9',
                        'a','b','c','d','e','f','g','h','i','j','k','l','m',
                        'n','o','p','q','r','s','t','u','v','w','x','y','z',
                        'A','B','C','D','E','F','G','H','I','J','K','L','M',
                        'N','O','P','Q','R','S','T','U','V','W','X','Y','Z'
                        ]
    index = math.floor(random() * len(random_str_arr))

    return random_str_arr[index]

# Encrypt the string
def encode(_input):
    pwd_str_arr = [*_input]
    pwd_final_str = ""
    for i in range(len(pwd_str_arr)+1):
        if i == len(pwd_str_arr):
            pwd_final_str += random_str()
            break

        code = ord(pwd_str_arr[i])
        temp_str = chr(code - len(pwd_str_arr))
        pwd_final_str += random_str() + temp_str

    return pwd_final_str

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
            try:
                await self.logout()
            except:
                pass

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)

        self.ports = {}
        self.device_info = {}
        self._client = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar(unsafe=True))

        _LOGGER.debug(f"Created coordinator with name: {name}")
        self.name = name
        self.host = host
        self._password = password

    async def get_system_info(self):
        if not await self._login():
            return False

        ok, text = await self.execute(METHOD_GET, f"http://{self.host}/system_data.js")
        if not ok:
            return False

        m = re.findall(r"sys_fmw_ver\s?=\s?'(.+)';", text)
        if not m or len(m) < 1:
            _LOGGER.info(f"Unexpected response received system info retrieval: {text}")
            return False
        sw_version = m[0]

        m = re.findall(r"model_name\s?=\s?'(.+)';", text)
        if not m or len(m) < 1:
            _LOGGER.info(f"Unexpected response received system info retrieval: {text}")
            return False
        model = m[0]

        m = re.findall(r"sys_MAC\s?=\s?'(.+)';", text)
        if not m or len(m) < 1:
            _LOGGER.info(f"Unexpected response received system info retrieval: {text}")
            return False
        mac = m[0]

        m = re.findall(r"sys_dev_name\s?=\s?'(.+)';", text)
        if not m or len(m) < 1:
            _LOGGER.info(f"Unexpected response received system info retrieval: {text}")
            return False
        name = m[0]

        return {
            'name': name,
            'mac': mac,
            'sw_version': sw_version,
            'model': model
        }


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

    async def execute(self, method, url, data=None):
        for i in range(MAX_HTTP_RETRIES):
            try:
                if i != 0:
                    _LOGGER.info(f"Retry {method} {url} ({i} out of {MAX_HTTP_RETRIES})")
                    await asyncio.sleep(2)

                if method == METHOD_GET:
                    resp = await self._client.get(url, timeout=5)
                else:
                    resp = await self._client.post(url, data=data, timeout=5)

                _LOGGER.debug(f"{method} {url} returned status code: {resp.status}")
                if not resp.ok:
                    _LOGGER.info("Failed. retrying")
                    continue
                text = await resp.text()
                if not "login.cgi" in url and not "logout.html" in url and re.search(r'action="login.cgi"', text):
                    _LOGGER.info("Login required. retrying")
                    self._clear_login_cookie()
                    return False, text

                return True, text

            except (asyncio.TimeoutError, aiohttp.ClientError) as ex:
                _LOGGER.info(f"Error during {method} {url}: {ex}")

        return False, None

    async def logout(self):
        _LOGGER.info("Logging out")
        await self.execute(METHOD_GET, f"http://{self.host}/logout.html")

    def _have_login_cookie(self):
        if 'token' in [c.key for c in self._client.cookie_jar]:
            _LOGGER.debug("Cookie contains a login token")
            return True
        return False

    def _clear_login_cookie(self):
        _LOGGER.debug("Login cookie no longer valid. Clearing cookies")
        self._client.cookie_jar.clear()

    async def _login(self):
        if self._have_login_cookie():
            _LOGGER.debug("Login token should still be valid")
            return True

        _LOGGER.debug("Logging in")

        login_data = {
            "password": encode(self._password),
        }

        ok, text = await self.execute(METHOD_POST, f"http://{self.host}/login.cgi", data=login_data)
        if not ok:
            _LOGGER.debug("Login failed")
            return False

        if self._have_login_cookie():
            _LOGGER.info("Logged in successfully")
            return True

        if text is not None and "logged in already" in text:
            _LOGGER.info("Other login session is still active")
        else:
            _LOGGER.info(f"Unknown error during login: {text}")

        _LOGGER.debug("Login failed")
        return False

    async def _do_change_state(self):
        if not await self._login():
            return False

        switches = [True if o.get("state", STATE_ON) == STATE_ON else False for _, o in self.ports.items()]

        data = {
            "g_port_flwcl": 0,
            "g_port_poe": bool_list_to_int(switches),
            "g_port_speed0": 0,
            "g_port_speed1": 0,
            "g_port_speed2": 0,
            "g_port_speed3": 0,
            "g_port_speed4": 0
        }


        if "GS1200-5HP v2" in self.device_info["model"]:
            data["g_port_state"] = 31
        elif "GS1200-8HP v2" in self.device_info["model"]:
            data["g_port_state"] = 223            
            data["g_port_speed5"] = 0
            data["g_port_speed6"] = 0
            data["g_port_speed7"] = 0
        else:
            _LOGGER.error(f"Unknown model: {self.device_info['model']}")
            return False

        ok, _ = await self.execute(METHOD_POST, f"http://{self.host}/port_state_set.cgi", data=data)
        if not ok:
            _LOGGER.warning("Failed to change state")
            return False

        _LOGGER.debug("State change successful")
        return True

    async def change_state(self):
        for i in range(MAX_APP_RETRIES):
            if await self._do_change_state():
                return
            _LOGGER.info("Retry changing state")
            if i < MAX_APP_RETRIES:
                await asyncio.sleep(2)
        raise UpdateFailed("Failed to change state")

    async def _fetch_poe_port_state(self):
        if not await self._login():
            return False

        ok, text = await self.execute(METHOD_GET, f"http://{self.host}/port_state_data.js")
        if not ok:
            return False

        m = re.findall(r"portPoE\s?=\s?'(\d+)';", text)
        if not m or len(m) < 1:
            _LOGGER.info(f"Unexpected response received during update state: {text}")
            return False

        switches = int_to_bool_list(int(m[0]))
        for i, val in enumerate(switches):
            _LOGGER.debug(f"Port {i} state {val}")
            if not self.ports.get(i):
                self.ports[i] = {}
            self.ports[i]["state"] = STATE_ON if val else STATE_OFF

        return True

    async def _fetch_poe_port_power(self):
        if not await self._login():
            return False

        ok, text = await self.execute(METHOD_GET, f"http://{self.host}/poe_data.js")
        if not ok:
            return False

        m = re.findall(r"port_power\s?=\s?\[([\s\d+\.,]+)\]", text)
        if not m or len(m) < 1:
            _LOGGER.info(f"Unexpected response received during update state: {text}")
            return False

        powers = [x.strip() for x in m[0].split(',')]
        for i, val in enumerate(powers):
            _LOGGER.debug(f"Port {i} power {val}W")
            if not self.ports.get(i):
                self.ports[i] = {}
            self.ports[i]["power"] = float(val)
        return True

    async def _async_update_data(self):
        _LOGGER.debug("Polling for updates")
        for _ in range(MAX_APP_RETRIES):
            if await self._fetch_poe_port_state() and await self._fetch_poe_port_power():
                return
            _LOGGER.info("Retry fetching state")
            await asyncio.sleep(2)
        raise UpdateFailed("Failed to refresh state")


    async def _async_setup(self):
        self.device_info = await self.get_system_info()

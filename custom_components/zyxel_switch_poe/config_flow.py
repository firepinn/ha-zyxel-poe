"""Config flow to configure component."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class ZyxelPOEFlowHandler(config_entries.ConfigFlow):
    """Config flow for Zyxel POE platform."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        self._errors = {}

    async def async_step_import(self, user_input):
        """Import a config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title="configuration.yaml", data=user_input
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]
            password = user_input[CONF_PASSWORD]
            interval = user_input[CONF_SCAN_INTERVAL]

            return self.async_create_entry(
                title=host,
                data={
                    CONF_HOST: host,
                    CONF_NAME: name,
                    CONF_PASSWORD: password,
                    CONF_SCAN_INTERVAL: interval
                }
            )

        return await self._show_user_config_form()

    async def _show_user_config_form(self):
        """Show form to enter the credentials."""
        return self.async_show_form(
            step_id='user',
            errors=self._errors,
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=None): str,
                vol.Required(CONF_PASSWORD, default=None): str,
                vol.Optional(CONF_NAME, default=""): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=60):  vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
            }),
        )

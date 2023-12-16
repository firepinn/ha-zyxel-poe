import logging

from homeassistant.core import callback
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import KEY_POESWITCH

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.info('Configuring switches')

    coordinator = hass.data[KEY_POESWITCH][config_entry.entry_id]

    entities = list()
    for port_idx, _ in coordinator.ports.items():
        entities.append(ZyxelPoeSwitch(coordinator, port_idx))
    async_add_entities(entities, update_before_add=True)

class ZyxelPoeSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, port_idx):
        super().__init__(coordinator, context=port_idx)
        self._port_idx = port_idx
        self._coordinator = coordinator
        self._attr_name = f"{coordinator._name} port{self._port_idx}"
        self._attr_unique_id = f"{self._coordinator._host}_{self._port_idx}_poe_switch"

    async def async_turn_on(self):
        self._coordinator.set_port_state(self._port_idx, STATE_ON)
        await self._coordinator.change_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        self._coordinator.set_port_state(self._port_idx, STATE_OFF)
        await self._coordinator.change_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._coordinator.get_port_state(self._port_idx) == STATE_ON
        self.async_write_ha_state()

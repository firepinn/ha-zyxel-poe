import logging

from homeassistant.core import callback
from homeassistant.const import UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass

from .const import KEY_POESWITCH

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.info('Configuring sensors')

    coordinator = hass.data[KEY_POESWITCH][config_entry.entry_id]

    entities = list()
    for port_idx, _ in coordinator.ports.items():
        entities.append(ZyxelPoeSensor(coordinator, port_idx, SensorEntityDescription(
            key=f"port{port_idx} power",
            name=f"{coordinator._name} port{port_idx} power",
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
        )))
    async_add_entities(entities, update_before_add=True)

class ZyxelPoeSensor(CoordinatorEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, port_idx, description: SensorEntityDescription):
        super().__init__(coordinator, context=port_idx)
        self._coordinator = coordinator
        self._port_idx = port_idx
        self.entity_description = description
        self._attr_unique_id = f"{self._coordinator._host}_{self._port_idx}_poe_power"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._coordinator.get_port_power(self._port_idx)
        self.async_write_ha_state()

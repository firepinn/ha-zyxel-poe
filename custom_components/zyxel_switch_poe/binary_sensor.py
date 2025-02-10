from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import STATE_ON

from .const import KEY_POESWITCH, DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[KEY_POESWITCH][config_entry.entry_id]

    entities = []
    for port_idx, _ in coordinator.ports.items():
        entities.append(PortLinkStateEntity(coordinator, port_idx))

    async_add_entities(entities, update_before_add=False)

class PortLinkStateEntity(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, port_idx):
        super().__init__(coordinator, context=port_idx)
        self._attr_native_value = self.coordinator.get_port_link_state(self.coordinator_context) == STATE_ON
        self._attr_unique_id = f"{self.coordinator.host}_{self.coordinator_context}_state"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.host)
            }
        )

    @property
    def name(self) -> str:
        return f"{self.coordinator.name} port{self.coordinator_context} link state",

    @property
    def is_on(self) -> bool:
        return self.coordinator.get_port_link_state(self.coordinator_context) == STATE_ON

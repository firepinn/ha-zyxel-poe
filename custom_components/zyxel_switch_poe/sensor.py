import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass

from .const import KEY_POESWITCH, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[KEY_POESWITCH][config_entry.entry_id]

    entities = []
    for port_idx, port in coordinator.ports.items():
        if port.get('is_poe_port', False):
            entities.append(PoePowerEntity(coordinator, port_idx, SensorEntityDescription(
                key=f"port{port_idx} power",
                name=f"{coordinator.name} port{port_idx} power",
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
            )))
        entities.append(LinkSpeedEntity(coordinator, port_idx, SensorEntityDescription(
            key=f"port{port_idx} link speed",
            name=f"{coordinator.name} port{port_idx} link speed",
            entity_registry_enabled_default=False
        )))
    entities.append(UptimeEntity(coordinator, SensorEntityDescription(
        key=f"uptime",
        name=f"{coordinator.name} uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION
    )))
    _LOGGER.debug(f'Configuring {len(entities)} sensors')
    async_add_entities(entities, update_before_add=False)


class UptimeEntity(CoordinatorEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_native_value = self.coordinator.get_uptime()
        self._attr_unique_id = f"{self.coordinator.host}_uptime"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.host)
            }
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.get_uptime()
        _LOGGER.debug(f"Uptime changed to {self._attr_native_value}")
        self.async_write_ha_state()

class PoePowerEntity(CoordinatorEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, port_idx, description: SensorEntityDescription):
        super().__init__(coordinator, context=port_idx)
        self.entity_description = description
        self._attr_native_value = self.coordinator.get_port_power(self.coordinator_context)
        self._attr_unique_id = f"{self.coordinator.host}_{self.coordinator_context}_poe_power"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.host)
            }
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.get_port_power(self.coordinator_context)
        _LOGGER.debug(f"Power value of port {self.coordinator_context} changed to {self._attr_native_value}")
        self.async_write_ha_state()

class LinkSpeedEntity(CoordinatorEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, port_idx, description: SensorEntityDescription):
        super().__init__(coordinator, context=port_idx)
        self.entity_description = description
        self._attr_native_value = self.coordinator.get_port_link_speed(self.coordinator_context)
        self._attr_unique_id = f"{self.coordinator.host}_{self.coordinator_context}_speed"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.host)
            }
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.get_port_link_speed(self.coordinator_context)
        _LOGGER.debug(f"Link speed value of port {self.coordinator_context} changed to {self._attr_native_value}")
        self.async_write_ha_state()

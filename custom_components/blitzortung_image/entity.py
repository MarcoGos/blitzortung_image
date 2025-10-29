"""Blitzortung Image Entity Base Class"""

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER, NAME
from .coordinator import BlitzortungDataUpdateCoordinator


class BlitzortungImageEntity(CoordinatorEntity[BlitzortungDataUpdateCoordinator]):
    """Base class for Blitzortung Image entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlitzortungDataUpdateCoordinator,
        description: EntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
            name=NAME,
        )
        self._attr_unique_id = f"{entry_id}-{DEFAULT_NAME} {description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

"""Blitzortung Image Sensor Entities"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from .const import DOMAIN, DEFAULT_NAME, LAST_UPDATED
from .coordinator import BlitzortungDataUpdateCoordinator
from .entity import BlitzortungImageEntity

DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=LAST_UPDATED,
        translation_key=LAST_UPDATED,
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]


async def async_setup_entry(
    hass,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blitzortung Image sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[BlitzortungImageSensor] = []

    # Add all sensors described above.
    for description in DESCRIPTIONS:
        entities.append(
            BlitzortungImageSensor(
                coordinator=coordinator,
                entry_id=config_entry.entry_id,
                description=description,
            )
        )

    async_add_entities(entities)


class BlitzortungImageSensor(BlitzortungImageEntity, SensorEntity):
    """Defines a Blitzortung Image sensor."""

    def __init__(
        self,
        coordinator: BlitzortungDataUpdateCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Blitzortun Image sensor."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            entry_id=entry_id,
        )
        self.entity_id = f"{SENSOR_DOMAIN}.{DEFAULT_NAME} {description.key}"

    @property
    def native_value(self) -> StateType:  # type: ignore
        """Return the state of the sensor."""
        return self.coordinator.api.setting(LAST_UPDATED)

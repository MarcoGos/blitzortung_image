"""Blitzortung Image Number Entities"""

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.components.number.const import DOMAIN as NUMBER_DOMAIN, NumberMode
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BlitzortungDataUpdateCoordinator
from .const import DOMAIN, DEFAULT_NAME, MARKER_LATITUDE, MARKER_LONGITUDE
from .entity import BlitzortungImageEntity

DESCRIPTIONS: list[NumberEntityDescription] = [
    NumberEntityDescription(
        key=MARKER_LATITUDE,
        translation_key=MARKER_LATITUDE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:latitude",
        native_min_value=-180,
        native_max_value=180,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key=MARKER_LONGITUDE,
        translation_key=MARKER_LONGITUDE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:longitude",
        native_min_value=-90,
        native_max_value=90,
        mode=NumberMode.BOX,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Blitzortung Image numbers based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BlitzortungImageNumber] = []

    # Add all numbers described above.
    for description in DESCRIPTIONS:
        entities.append(
            BlitzortungImageNumber(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                description=description,
            )
        )

    async_add_entities(entities)


class BlitzortungImageNumber(BlitzortungImageEntity, NumberEntity):
    """Representation of a Blitzortung Image number entity."""

    def __init__(
        self,
        coordinator: BlitzortungDataUpdateCoordinator,
        entry_id: str,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(
            coordinator=coordinator, description=description, entry_id=entry_id
        )
        self.entity_id = f"{NUMBER_DOMAIN}.{DEFAULT_NAME}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value of the number."""
        return self.coordinator.api.setting(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        self.coordinator.api.set_setting(self.entity_description.key, value, store=True)
        self.async_write_ha_state()

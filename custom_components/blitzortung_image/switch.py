"""Blitzortung Image Switch Entities"""

from typing import Any
from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
    SwitchDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BlitzortungDataUpdateCoordinator
from .const import DOMAIN, DEFAULT_NAME, SHOW_MARKER, SHOW_LEGEND
from .entity import BlitzortungImageEntity

DESCRIPTIONS: list[SwitchEntityDescription] = [
    SwitchEntityDescription(
        key=SHOW_MARKER,
        translation_key=SHOW_MARKER,
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key=SHOW_LEGEND,
        translation_key=SHOW_LEGEND,
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:map-legend",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Blitzortung Image switches based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BlitzortungImageSwitch] = []

    # Add all numbers described above.
    for description in DESCRIPTIONS:
        entities.append(
            BlitzortungImageSwitch(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                description=description,
            )
        )

    async_add_entities(entities)


class BlitzortungImageSwitch(BlitzortungImageEntity, SwitchEntity):
    """Representation of a Blitzortung Image switch entity."""

    def __init__(
        self,
        coordinator: BlitzortungDataUpdateCoordinator,
        entry_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            entry_id=entry_id,
        )
        self.coordinator = coordinator
        self.entity_id = f"{SWITCH_DOMAIN}.{DEFAULT_NAME}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return if the switch is on."""
        return self.coordinator.api.setting(self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.coordinator.api.set_setting(self.entity_description.key, True, store=True)
        await self.coordinator.api.async_force_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.coordinator.api.set_setting(self.entity_description.key, False, store=True)
        await self.coordinator.api.async_force_refresh()
        self.async_write_ha_state()

"""Blitzorting Image Camera Component for Home Assistant."""

from dataclasses import dataclass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.camera import Camera, CameraEntityDescription
from homeassistant.components.camera.const import DOMAIN as CAMERA_DOMAIN
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_NAME, DOMAIN, LIGHTNING
from .coordinator import BlitzortingDataUpdateCoordinator
from .entity import BlitzortungImageEntity


@dataclass(frozen=True, kw_only=True)
class BlitzortungImageCameraEntityDescription(CameraEntityDescription):
    """Describes Blitzorting Image camera entity."""

    key: str | None = None
    translation_key: str | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True


DESCRIPTIONS: list[BlitzortungImageCameraEntityDescription] = [
    BlitzortungImageCameraEntityDescription(
        key=LIGHTNING,
        translation_key=LIGHTNING,
        icon="mdi:ightning-bolt-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blitzorting Image cameras based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BlitzortungImageCamera] = []

    # Add all images described above.
    for description in DESCRIPTIONS:
        entities.append(
            BlitzortungImageCamera(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                description=description,
            )
        )

    async_add_entities(entities)


class BlitzortungImageCamera(BlitzortungImageEntity, Camera):
    """Defines the radar weer plaza camera."""

    def __init__(
        self,
        coordinator: BlitzortingDataUpdateCoordinator,
        entry_id: str,
        description: BlitzortungImageCameraEntityDescription,
    ) -> None:
        """Initialize Blitzortung Image camera."""
        Camera.__init__(self)
        super().__init__(
            coordinator=coordinator, description=description, entry_id=entry_id
        )

        self._attr_content_type = "image/gif"
        self.entity_id = f"{CAMERA_DOMAIN}.{DEFAULT_NAME}_{description.key}"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image or None."""
        image = await self.coordinator.api.async_get_animated_image()
        return image

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.coordinator.api.async_register_camera()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        await self.coordinator.api.async_unregister_camera()

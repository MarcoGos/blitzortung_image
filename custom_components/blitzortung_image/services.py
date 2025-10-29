"""Global services file."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .coordinator import BlitzortingDataUpdateCoordinator
from .const import DOMAIN


class BlitzortungImageServicesSetup:
    """Class to handle Integration Services."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialise services."""
        self.hass = hass
        self.config_entry = config_entry
        self.coordinator: BlitzortingDataUpdateCoordinator = hass.data[DOMAIN][
            config_entry.entry_id
        ]

        self.setup_services()

    def setup_services(self):
        """Initialise the services in Hass."""

        self.hass.services.async_register(
            DOMAIN,
            "force_update",
            self.force_update,
        )

    async def force_update(self, _: ServiceCall) -> None:
        """Force update service"""
        api = self.coordinator.api
        await api.async_force_refresh()

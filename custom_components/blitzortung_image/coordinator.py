"""Blitzortung Image Data Update Coordinator"""

from datetime import datetime, timedelta
import logging

from homeassistant import config_entries
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .api import BlitzortungApi
from .const import (
    DEFAULT_SYNC_INTERVAL,
    DOMAIN,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


class BlitzortingDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BlitzortungApi,
        config_entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize."""
        self.api: BlitzortungApi = api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SYNC_INTERVAL),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> None:
        """Update data via api."""
        # try:
        if datetime.now().minute % 5 == 0:
            await self.api.async_get_new_images()
        # except Exception as exception:
        #     _LOGGER.warning("Error communicating with API: %s", exception)
        #     raise UpdateFailed from exception

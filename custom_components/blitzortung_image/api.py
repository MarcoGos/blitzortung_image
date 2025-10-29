"""Blitzortung API client for Home Assistant."""

from typing import Any

import os
import glob
import json
import logging
from zoneinfo import ZoneInfo
from io import BytesIO
from shutil import rmtree

from datetime import datetime, timedelta
from aiohttp.client_exceptions import (
    ClientConnectorDNSError,
    ConnectionTimeoutError,
)
from pytz import timezone

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import STORAGE_DIR
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio

from .const import (
    DOMAIN,
    MARKER_LATITUDE,
    MARKER_LONGITUDE,
    SHOW_MARKER,
    SHOW_LEGEND,
    LAST_UPDATED,
)
from .tools import calculate_mercator_position

TIMEOUT = 10
IMAGES_TO_KEEP = 18
FILES_TO_KEEP = IMAGES_TO_KEEP

_LOGGER: logging.Logger = logging.getLogger(__package__)


class BlitzortungApi:
    """Blitzortung API client to fetch weather images."""

    _headers: dict[str, str] = {"User-Agent": "Home Assistant (Blitzortung Image)"}
    _images: list[str] = []
    _data_files: list[str] = []
    _storage_path: str
    _timezone: Any = None
    _settings: dict[str, Any] = {}
    _camera: bool = False
    _username: str = ""
    _password: str = ""
    # _left_longitude: float = 1.556
    # _right_longitude: float = 8.8
    # _top_latitude: float = 54.239
    # _bottom_latitude: float = 47.270
    _left_longitude: float = -12.28
    _right_longitude: float = 34.98
    _top_latitude: float = 54.239
    _bottom_latitude: float = 35.77

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        self._hass = hass
        self._timezone = self._hass.config.time_zone
        self._session = async_get_clientsession(self._hass)
        self.set_setting(
            MARKER_LONGITUDE,
            (
                self._hass.data.get(DOMAIN, {}).get(MARKER_LONGITUDE, None)
                or self._hass.config.longitude
            ),
        )
        self.set_setting(
            MARKER_LATITUDE,
            (
                self._hass.data.get(DOMAIN, {}).get(MARKER_LATITUDE, None)
                or self._hass.config.latitude
            ),
        )
        self.set_setting(SHOW_MARKER, hass.data.get(DOMAIN, {}).get(SHOW_MARKER, True))
        self.set_setting(SHOW_LEGEND, hass.data.get(DOMAIN, {}).get(SHOW_LEGEND, True))
        self._images = []
        self._data_files = []
        self._camera = False
        self._storage_path = self._hass.config.path(STORAGE_DIR, DOMAIN)
        self._username = username
        self._password = password

    def set_setting(self, key: str, value: Any, store: bool = False) -> None:
        """Set a setting for the API."""
        self._settings[key] = value
        if store:
            self._hass.data[DOMAIN][key] = value
        _LOGGER.debug("Setting parameter %s to %s", key, value)

    def setting(self, key: str) -> Any:
        """Get a setting for the API."""
        return self._settings.get(key, None)

    async def async_get_new_images(self) -> None:
        """Fetch new images from the Blitzorting API."""
        if not self.__is_camera_registered():
            return
        if not self._images:
            await self.__async_build_images_list()
        if not self._data_files:
            await self.__async_build_data_files_list()

        time_val = datetime.now()
        lightning_data = await self.__async_get_lightning_data()
        await self.__async_save_lightning_data(time_val, lightning_data)
        self.__add_filename_to_data_files(time_val)
        await self.__async_create_image(time_val)
        self.__add_filename_to_images(time_val)

        await self.__async_create_animated_gif()

        self.set_setting(
            LAST_UPDATED,
            datetime.now().replace(tzinfo=ZoneInfo(self._hass.config.time_zone)),
        )

    async def test_connection(self) -> bool:
        """Test connection to the Blitzorting API."""
        url = f"https://{self._username}:{self._password}@data.blitzortung.org/Data/Protected/last_strikes.php?number=1&sig=0"
        async with self._session.get(url, headers=self._headers) as response:
            if response.status == 200:
                return True
            else:
                raise BlitzortungAuthenticationError()

    def get_blitzortung_url(self) -> str:
        """Get the URL for the Blitzorting API."""
        # Get last 5 minutes of data
        ts = datetime.now().timestamp() - timedelta(minutes=5).total_seconds()
        timestamp_ns = int(ts * 1_000_000_000)
        url = f"https://{self._username}:{self._password}@data.blitzortung.org/Data/Protected/last_strikes.php?time={timestamp_ns}&west={self._left_longitude}&east={self._right_longitude}&north={self._top_latitude}&south={self._bottom_latitude}&sig=0"
        return url

    async def __async_get_lightning_data(self) -> str:
        try:
            async with async_timeout.timeout(TIMEOUT):
                async with self._session.get(
                    self.get_blitzortung_url(), headers=self._headers
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        return text
                    else:
                        _LOGGER.error(
                            "Failed to fetch lightning data: %s", response.status
                        )
                        return ""
        except ClientConnectorDNSError:
            _LOGGER.error("Failed to connect to DirectAdmin server.")
            return ""
        except ConnectionTimeoutError:
            _LOGGER.error("Connection timed out while fetching quotas.")
            return ""
        except Exception as e:
            _LOGGER.error("Unexpected error: Failed to fetch quotas: %s", e)
            return ""

    async def __async_save_lightning_data(
        self,
        time_val: datetime,
        lightning_data: str,
    ) -> None:
        await self._hass.async_add_executor_job(
            self.__save_lightning_data,
            time_val,
            lightning_data,
        )

    def __save_lightning_data(self, time_val: datetime, lightning_data: str) -> None:
        path = f"{self.__get_storage_path()}/{time_val.strftime('%Y%m%d-%H%M')}.data"
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(lightning_data)

    def __get_background_image(self) -> Image.Image:
        with Image.open(f"custom_components/{DOMAIN}/images/background.png") as image:
            return image.convert("RGBA")

    def __get_marker_image(self) -> Image.Image:
        with Image.open(f"custom_components/{DOMAIN}/images/pointer-50.png") as image:
            return image.convert("RGBA")

    def __get_legend_image(self) -> Image.Image:
        with Image.open(f"custom_components/{DOMAIN}/images/legend.png") as image:
            return image.convert("RGBA")

    async def __async_create_image(
        self,
        time_val: datetime,
    ) -> None:
        await self._hass.async_add_executor_job(
            self.__create_image,
            time_val,
        )

    def __create_image(
        self,
        time_val: datetime,
    ) -> None:
        # final image size is 1050x1148
        final = self.__get_background_image()

        draw = ImageDraw.Draw(final)

        self.__draw_lightning(draw)

        # Colors
        text_color = (254, 255, 255)
        outline_color = (0, 0, 0)
        # Font
        font = ImageFont.load_default(30)
        textx = 10
        texty = final.height - font.size - 10  # type: ignore
        # Draw time and shadow
        time_str = time_val.astimezone(timezone(self._timezone)).strftime("%H:%M")
        for adj in range(-2, 3):
            draw.text((textx + adj, texty), time_str, font=font, fill=outline_color)
            draw.text((textx, texty + adj), time_str, font=font, fill=outline_color)
        draw.text((textx, texty), time_str, font=font, fill=text_color)

        filename = self.__get_image_filename(time_val)
        final.save(filename, "PNG")
        mod_time = int(time_val.timestamp())
        os.utime(filename, (mod_time, mod_time))

    def __draw_lightning(self, draw: ImageDraw.ImageDraw) -> None:
        data_files = self._data_files.copy()
        for data_file in data_files:
            with open(data_file, "r", encoding="utf-8") as f:
                for data in f:
                    if not data:
                        continue
                    strike = json.loads(data)
                    x, y = calculate_mercator_position(
                        strike["lat"],
                        strike["lon"],
                        llon=self._left_longitude,
                        rlon=self._right_longitude,
                        tlat=self._top_latitude,
                        width=draw._image.width,
                    )
                    time = strike["time"] / 1_000_000_000
                    color = self.__determine_color(time)
                    draw.ellipse(
                        (x - 2, y - 2, x + 2, y + 2),
                        fill=color,
                        outline=None,
                    )

    def __determine_color(self, strike_time: float) -> tuple[int, int, int]:
        """Determine color based on age of the strike."""
        age = datetime.now().timestamp() - strike_time
        if age < 20 * 60:
            return (255, 255, 255)  # White for strikes within the last 20 minute
        if age < 40 * 60:
            return (255, 255, 0)  # Yellow for strikes within the last 40 minutes
        if age < 60 * 60:
            return (255, 170, 0)  # Orange for strikes within the last 60 minutes
        if age < 80 * 60:
            return (255, 85, 0)  # Dark orange for strikes within the last 80 minutes
        if age < 100 * 60:
            return (255, 0, 0)  # Red for strikes within the last 100 minutes
        return (191, 0, 0)  # Dark Red for older strikes

    def __get_image_filename(self, time_val: datetime) -> str:
        return f"{self.__get_storage_path()}/{time_val.strftime('%Y%m%d-%H%M')}.png"

    def __get_data_filename(self, time_val: datetime) -> str:
        return f"{self.__get_storage_path()}/{time_val.strftime('%Y%m%d-%H%M')}.data"

    def __add_filename_to_images(self, time_val: datetime) -> None:
        self._images.append(self.__get_image_filename(time_val))
        self._images.sort()
        self.__keep_last_images()

    def __keep_last_images(self):
        while len(self._images) > IMAGES_TO_KEEP:
            filename = self._images.pop(0)
            if os.path.exists(filename):
                os.remove(filename)
                _LOGGER.debug("Removed old image: %s", filename)

    def __add_filename_to_data_files(self, time_val: datetime) -> None:
        self._data_files.append(self.__get_data_filename(time_val))
        self._data_files.sort()
        self.__keep_last_data_files()

    def __keep_last_data_files(self):
        while len(self._data_files) > FILES_TO_KEEP:
            filename = self._data_files.pop(0)
            if os.path.exists(filename):
                os.remove(filename)
                _LOGGER.debug("Removed old data file: %s", filename)

    async def __async_create_animated_gif(self) -> None:
        await self._hass.async_add_executor_job(self.__create_animated_gif)

    def __create_animated_gif(self):
        if not self.__is_camera_registered():
            return
        images = []
        duration = []
        for index, image_data in enumerate(self._images):
            if not os.path.exists(image_data):
                continue

            # Add marker location and/or legend if set

            if (
                self.setting(SHOW_MARKER)
                and self.setting(MARKER_LONGITUDE)
                and self.setting(MARKER_LATITUDE)
            ) or self.setting(SHOW_LEGEND):
                final = Image.open(image_data).convert("RGBA")

                if self.setting(SHOW_LEGEND):
                    legend = self.__get_legend_image()
                    final.paste(legend, (5, 5), legend)

                if self.setting(SHOW_MARKER):
                    marker = self.__get_marker_image().resize((40, 40))
                    marker_x, marker_y = calculate_mercator_position(
                        self.setting(MARKER_LATITUDE),
                        self.setting(MARKER_LONGITUDE),
                        llon=self._left_longitude,
                        rlon=self._right_longitude,
                        tlat=self._top_latitude,
                        width=final.width,
                    )
                    final.paste(
                        marker,
                        (
                            marker_x - int(marker.width / 2),
                            marker_y - int(marker.height / 2),
                        ),
                        marker,
                    )
                image_stream = BytesIO()
                final.save(image_stream, format="PNG")
                final.close()
                images.append(imageio.imread(image_stream))
            else:
                images.append(imageio.imread(image_data))

            duration.append(
                2000 if index == len(self._images) - 1 else 200
            )  # 200 ms for all but the last frame

        if len(images) > 0:
            imageio.mimwrite(
                f"{self.__get_storage_path()}/animated.gif",
                images,
                loop=0,
                duration=duration if len(duration) > 1 else duration[0],
            )

    async def __async_build_images_list(self) -> None:
        await self._hass.async_add_executor_job(self.__build_images_list)

    def __build_images_list(self) -> None:
        self._images = []
        files = glob.glob(os.path.join(self.__get_storage_path(), "*.png"))
        files.sort()
        for file in files:
            self._images.append(file)
        self.__keep_last_images()

    async def __async_build_data_files_list(self) -> None:
        await self._hass.async_add_executor_job(self.__build_data_files_list)

    def __build_data_files_list(self) -> None:
        self._data_files = []
        files = glob.glob(os.path.join(self.__get_storage_path(), "*.data"))
        files.sort()
        for file in files:
            self._data_files.append(file)
        self.__keep_last_data_files()

    async def async_get_animated_image(self) -> bytes | None:
        """Get the animated image."""
        return await self._hass.async_add_executor_job(self.__get_animated_image)

    def __get_animated_image(self) -> bytes | None:
        animated_path = f"{self.__get_storage_path()}/animated.gif"
        if os.path.exists(animated_path):
            with open(animated_path, "rb") as image_file:
                return image_file.read()
        return None

    def __get_storage_path(self) -> str:
        return self._storage_path

    async def async_force_refresh(self) -> None:
        """Force refresh of the images."""
        _LOGGER.debug("Refreshing Blitzortung Image images")
        if self.__is_camera_registered():
            await self.__async_create_animated_gif()

    def __is_camera_registered(self) -> bool:
        return self._camera

    async def async_register_camera(self) -> None:
        """Register a camera for the given image type."""
        await self._hass.async_add_executor_job(self.__register_camera)

    def __register_camera(self) -> None:
        self._camera = True
        storage_path = self.__get_storage_path()
        if not os.path.exists(storage_path):
            os.makedirs(storage_path, exist_ok=True)

    async def async_unregister_camera(self) -> None:
        """Unregister a camera for the given image type."""
        await self._hass.async_add_executor_job(self.__unregister_camera)

    def __unregister_camera(self) -> None:
        self._camera = False
        storage_path = self.__get_storage_path()
        if os.path.exists(storage_path):
            rmtree(storage_path)


class BlitzortungAuthenticationError(Exception):
    """Exception raised for authentication errors."""


class DomainNotFoundError(Exception):
    """Exception raised when the specified domain is not found."""


class InvalidHostnameException(Exception):
    """Exception raised for invalid hostname format."""

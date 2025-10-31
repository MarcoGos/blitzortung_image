"""Blitzortung API client for Home Assistant."""

from typing import Any

import os
import glob
import json
import logging
from zoneinfo import ZoneInfo
from io import BytesIO
from shutil import rmtree
import asyncio
from enum import Enum

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
    SHOW_ACTIVITY_GRAPH,
    LAST_UPDATED,
)
from .tools import calculate_mercator_position, draw_rotated_text

TIMEOUT = 10
IMAGES_TO_KEEP = 18
FILES_TO_KEEP = IMAGES_TO_KEEP

_LOGGER: logging.Logger = logging.getLogger(__package__)


class FileExtension(Enum):
    """File extensions used in Blitzortung API."""

    PNG = ".png"
    ACTIVITY = ".activity"
    DATA = ".data"


class BlitzortungApi:
    """Blitzortung API client to fetch weather images."""

    _headers: dict[str, str] = {"User-Agent": "Home Assistant (Blitzortung Image)"}
    _image_filenames: list[str] = []
    _storage_path: str
    _timezone: Any = None
    _settings: dict[str, Any] = {}
    _camera: bool = False
    _username: str = ""
    _password: str = ""
    _left_longitude: float = 1.556
    _right_longitude: float = 8.8
    _top_latitude: float = 54.239
    _bottom_latitude: float = 47.270

    # test values for europe
    # _left_longitude: float = -12.28
    # _right_longitude: float = 34.98
    # _top_latitude: float = 54.239
    # _bottom_latitude: float = 35.77

    _activity_data: dict[int, dict[str, int]] = {
        0: {"activity": 0},
        20: {"activity": 0},
        40: {"activity": 0},
        60: {"activity": 0},
        80: {"activity": 0},
    }

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
        self.set_setting(
            SHOW_ACTIVITY_GRAPH,
            hass.data.get(DOMAIN, {}).get(SHOW_ACTIVITY_GRAPH, True),
        )
        self._image_filenames = []
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
        """Fetch new images from the Blitzortung API."""
        if not self.__is_camera_registered():
            return
        if not self._image_filenames:
            await self.__async_build_images_filenames()

        time_val = datetime.now()
        lightning_data = await self.__async_get_lightning_data()
        await self.__async_save_lightning_data(time_val, lightning_data)
        await self.__async_create_image(time_val)
        self.__add_filename_to_images(time_val)
        await self.__async_save_activity_data(time_val)

        await self.__async_create_animated_gif()

        self.set_setting(
            LAST_UPDATED,
            datetime.now().replace(tzinfo=ZoneInfo(self._hass.config.time_zone)),
        )

    async def test_connection(self) -> bool:
        """Test connection to theuBlitzortung API."""
        url = f"https://{self._username}:{self._password}@data.blitzortung.org/Data/Protected/last_strikes.php?number=1&sig=0"
        async with self._session.get(url, headers=self._headers) as response:
            if response.status == 200:
                return True
            else:
                raise BlitzortungAuthenticationError()

    def get_blitzortung_url(self) -> str:
        """Get the URL for the Blitzortung API."""
        # Get last 5 minutes of data
        ts = datetime.now().timestamp() - timedelta(minutes=5).total_seconds()
        timestamp_ns = int(ts * 1_000_000_000)
        url = f"https://{self._username}:{self._password}@data.blitzortung.org/Data/Protected/last_strikes.php?time={timestamp_ns}&west={self._left_longitude}&east={self._right_longitude}&north={self._top_latitude}&south={self._bottom_latitude}&sig=0"
        return url

    async def __async_get_lightning_data(self) -> str:
        retries = 3
        for attempt in range(retries):
            try:
                async with async_timeout.timeout(TIMEOUT):
                    async with self._session.get(
                        self.get_blitzortung_url(), headers=self._headers
                    ) as response:
                        if response.status == 200:
                            text = await response.text()
                            return text
            except ClientConnectorDNSError:
                _LOGGER.error(
                    "Failed to connect to the blitzortung server. Attempt %d/%d",
                    attempt + 1,
                    retries,
                )
            except ConnectionTimeoutError:
                _LOGGER.error(
                    "Connection timed out while fetching lightning data. Attempt %d/%d",
                    attempt + 1,
                    retries,
                )
            except Exception as e:
                _LOGGER.error(
                    "Unexpected error: Failed to fetch lightning data: %s (Attempt %d/%d)",
                    e,
                    attempt + 1,
                    retries,
                )
            if attempt < retries - 1:
                await asyncio.sleep(2)  # Wait 2 seconds before retrying
        _LOGGER.error("All attempts to fetch lightning data failed.")
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
        path = self.__get_filename(time_val, FileExtension.DATA)
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
        final = self.__get_background_image()

        draw = ImageDraw.Draw(final)

        self.__draw_lightning(draw)
        self.__draw_time(draw, time_val)

        filename = self.__get_filename(time_val, FileExtension.PNG)
        final.save(filename, "PNG")
        mod_time = int(time_val.timestamp())
        os.utime(filename, (mod_time, mod_time))

    def __draw_time(self, draw: ImageDraw.ImageDraw, time_val: datetime) -> None:
        # Colors
        text_color = (254, 255, 255)
        outline_color = (0, 0, 0)
        # Font
        font = ImageFont.load_default(30)
        textx = 10
        texty = draw._image.height - font.size - 10  # type: ignore
        # Draw time and shadow
        time_str = time_val.astimezone(timezone(self._timezone)).strftime("%H:%M")
        for adj in range(-2, 3):
            draw.text((textx + adj, texty), time_str, font=font, fill=outline_color)
            draw.text((textx, texty + adj), time_str, font=font, fill=outline_color)
        draw.text((textx, texty), time_str, font=font, fill=text_color)

    def __draw_lightning(self, draw: ImageDraw.ImageDraw) -> None:
        self.__reset_activity_data()
        for image_filename in self._image_filenames.copy():
            data_file = image_filename[:-4] + FileExtension.DATA.value
            if os.path.exists(data_file):
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
                        age = self.__determine_age(time)
                        draw.ellipse(
                            (x - 2, y - 2, x + 2, y + 2),
                            fill=color,
                            outline=None,
                        )
                        self._activity_data[age]["activity"] += 1

    def __reset_activity_data(self) -> None:
        for v in self._activity_data.values():
            v["activity"] = 0

    def __create_activity_graph(
        self, activity_data: dict[int, dict[str, int]]
    ) -> Image.Image:
        max_activity = max(item["activity"] for item in activity_data.values())
        max_activity_key = max(
            activity_data, key=lambda k: activity_data[k]["activity"]
        )
        max_key = max(activity_data.keys())
        font = ImageFont.load_default(10)
        width, height = (len(activity_data) * 10 + 3, 75)

        image = Image.new("RGBA", (len(activity_data) * 10 + 3, 75), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        line_color = (255, 255, 255)
        draw.line(
            (0, 0, 0, 0 + height - 1),
            fill=line_color,
            width=1,
        )
        draw.line(
            (0, 0 + height - 1, 0 + width, 0 + height - 1),
            fill=line_color,
            width=1,
        )
        for key, value in activity_data.items():
            if value == 0:
                continue
            x0 = 1 + (max_key - key) // 2
            x1 = x0 + 9
            y1 = height - 2
            y0 = y1 - int((value["activity"] / max_activity) * y1)
            draw.rectangle(
                (
                    x0,
                    y0,
                    x1,
                    y1,
                ),
                fill=self.__determine_color(datetime.now().timestamp() - key * 60),
            )
            if key == max_activity_key:
                draw_rotated_text(
                    draw._image,
                    font,  # type: ignore
                    f"{max_activity}",
                    90,
                    x0,
                    2,
                    fill=(0, 0, 0),
                )
        return image

    async def __async_save_activity_data(self, time_val: datetime) -> None:
        await self._hass.async_add_executor_job(
            self.__save_activity_data,
            time_val,
        )

    def __save_activity_data(self, time_val: datetime) -> None:
        """Save the activity data to a JSON file."""
        path = self.__get_filename(time_val, FileExtension.ACTIVITY)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._activity_data, f)

    def __determine_color(self, strike_time: float) -> tuple[int, int, int]:
        """Determine color based on age of the strike."""
        colors = {
            0: (255, 255, 255),  # White
            20: (255, 255, 0),  # Yellow
            40: (255, 170, 0),  # Orange
            60: (255, 85, 0),  # Dark Orange
            80: (255, 0, 0),  # Red
        }
        age = self.__determine_age(strike_time)
        return colors.get(age, (191, 0, 0))

    def __determine_age(self, strike_time: float) -> int:
        """Determine age bucket based on age of the strike."""
        age = datetime.now().timestamp() - strike_time
        if age < 20 * 60:
            return 0
        if age < 40 * 60:
            return 20
        if age < 60 * 60:
            return 40
        if age < 80 * 60:
            return 60
        return 80

    def __get_filename(self, time_val: datetime, extension: FileExtension) -> str:
        return f"{self.__get_storage_path()}/{time_val.strftime('%Y%m%d-%H%M')}{extension.value}"

    def __add_filename_to_images(self, time_val: datetime) -> None:
        self._image_filenames.append(self.__get_filename(time_val, FileExtension.PNG))
        self._image_filenames.sort()
        self.__keep_last_images()

    def __keep_last_images(self):
        while len(self._image_filenames) > IMAGES_TO_KEEP:
            filename = self._image_filenames.pop(0)
            if os.path.exists(filename):
                os.remove(filename)
                _LOGGER.debug("Removed old image: %s", filename)
            if os.path.exists(filename[:-4] + FileExtension.ACTIVITY.value):
                os.remove(filename[:-4] + FileExtension.ACTIVITY.value)
                _LOGGER.debug(
                    "Removed old activity file: %s",
                    filename[:-4] + FileExtension.ACTIVITY.value,
                )
            if os.path.exists(filename[:-4] + FileExtension.DATA.value):
                os.remove(filename[:-4] + FileExtension.DATA.value)
                _LOGGER.debug(
                    "Removed old data file: %s",
                    filename[:-4] + FileExtension.DATA.value,
                )

    async def __async_create_animated_gif(self) -> None:
        await self._hass.async_add_executor_job(self.__create_animated_gif)

    def __create_animated_gif(self):
        if not self.__is_camera_registered():
            return
        images = []
        duration = []
        for index, image_filepath in enumerate(self._image_filenames):
            if not os.path.exists(image_filepath):
                continue

            # Add marker location
            final = Image.open(image_filepath).convert("RGBA")
            if (
                self.setting(SHOW_MARKER)
                and self.setting(MARKER_LONGITUDE)
                and self.setting(MARKER_LATITUDE)
            ):
                legend = self.__get_legend_image()
                final.paste(legend, (5, 5), legend)

            # Add legend
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

            # Add activity graph
            if self.setting(SHOW_ACTIVITY_GRAPH):
                activity_filename = image_filepath[:-4] + FileExtension.ACTIVITY.value
                if os.path.exists(activity_filename):
                    with open(activity_filename, "r", encoding="utf-8") as f:
                        activity_data = json.load(f)
                    activity_data = {int(k): v for k, v in activity_data.items()}
                    activity_graph = self.__create_activity_graph(activity_data)
                    final.paste(
                        activity_graph,
                        (
                            final.width - activity_graph.width - 5,
                            final.height - activity_graph.height - 5,
                        ),
                        activity_graph,
                    )

            image_stream = BytesIO()
            final.save(image_stream, format="PNG")
            final.close()
            images.append(imageio.imread(image_stream))

            duration.append(
                2000 if index == len(self._image_filenames) - 1 else 200
            )  # 200 ms for all but the last frame

        if len(images) > 0:
            imageio.mimwrite(
                f"{self.__get_storage_path()}/animated.gif",
                images,
                loop=0,
                duration=duration if len(duration) > 1 else duration[0],
            )

    async def __async_build_images_filenames(self) -> None:
        await self._hass.async_add_executor_job(self.__build_images_list)

    def __build_images_list(self) -> None:
        self._image_filenames = []
        files = glob.glob(os.path.join(self.__get_storage_path(), "*.png"))
        files.sort()
        for file in files:
            self._image_filenames.append(file)
        self.__keep_last_images()

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

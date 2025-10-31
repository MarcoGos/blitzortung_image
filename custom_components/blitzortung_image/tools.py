"""Calculate Mercator position based on latitude and longitude."""

import math
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple
from datetime import datetime


def calculate_mercator_position(
    lat: float,
    lon: float,
    llon: float,
    rlon: float,
    tlat: float,
    width: int = 1050,
) -> tuple[int, int]:
    x = round((lon - llon) / (rlon - llon) * width)

    # Convert to radial
    tlat_rad = tlat / 180 * math.pi
    # Calculate Mercator factor for top latitude
    ty = 0.5 * math.log((1 + math.sin(tlat_rad)) / (1 - math.sin(tlat_rad)))
    ty = width * ty / deg2rad(rlon - llon)

    # Convert to radial
    lat = lat / 180 * math.pi
    # Calculate Mercator factor for given latitude
    y = 0.5 * math.log((1 + math.sin(lat)) / (1 - math.sin(lat)))
    y = round(ty - width * y / deg2rad(rlon - llon))
    return (x, y)


def deg2rad(degrees: float) -> float:
    """Convert degrees to radians."""
    return degrees * math.pi / 180


def draw_rotated_text(
    image: Image.Image,
    font: ImageFont.ImageFont,
    text: str,
    angle: int,
    x: int,
    y: int,
    fill: Tuple[int, int, int] = (255, 255, 255),
) -> None:
    """Draw text rotated by angle at position (x, y) on the image."""
    # Create a new image with transparent background to draw the text
    # draw = ImageDraw.Draw(image)
    # bbox = draw.textbbox((0, 0), text, font=font)
    bbox = font.getbbox(text)
    text_width, text_height = int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])
    text_img = Image.new("RGBA", (text_width, text_height + 2), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((0, 0), text, font=font, fill=fill)
    # Rotate the text image
    rotated = text_img.rotate(angle, expand=1)
    # Paste the rotated text onto the original image
    image.paste(rotated, (x - 1, 0), rotated)

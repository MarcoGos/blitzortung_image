"""Calculate Mercator position based on latitude and longitude."""

import math


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

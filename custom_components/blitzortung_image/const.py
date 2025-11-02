"""Constants for the Blitzortung Image integration."""

NAME = "Blitzortung Image"
DEFAULT_NAME = NAME.lower()
DOMAIN = "blitzortung_image"
MANUFACTURER = "Blitzortung.org"

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]

DEFAULT_SYNC_INTERVAL = 60  # seconds

RETRY_ATTEMPTS = 5

MARKER_LATITUDE = "marker_latitude"
MARKER_LONGITUDE = "marker_longitude"
SHOW_MARKER = "show_marker"
SHOW_LEGEND = "show_legend"
SHOW_ACTIVITY_GRAPH = "show_activity_graph"
LAST_UPDATED = "last_updated"
LIGHTNING = "lightning"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

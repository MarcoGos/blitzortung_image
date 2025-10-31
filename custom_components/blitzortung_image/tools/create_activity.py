from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple


def __determine_color(age: int) -> tuple[int, int, int]:
    """Determine color based on age of the strike."""
    if age < 20:
        return (255, 255, 255)  # White for strikes within the last 20 minute
    if age < 40:
        return (255, 255, 0)  # Yellow for strikes within the last 40 minutes
    if age < 60:
        return (255, 170, 0)  # Orange for strikes within the last 60 minutes
    if age < 80:
        return (255, 85, 0)  # Dark orange for strikes within the last 80 minutes
    if age < 100:
        return (255, 0, 0)  # Red for strikes within the last 100 minutes
    return (191, 0, 0)  # Dark Red for older strikes


def draw_rotated_text(
    image: Image.Image,
    font: ImageFont.ImageFont,
    text: str,
    angle: int,
    x: int,
    y: int,
    fill: Tuple[int, int, int] = (255, 255, 255),
) -> Tuple[int, int]:
    """Draw text rotated by angle at position (x, y) on the image."""
    # Create a new image with transparent background to draw the text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width, text_height = int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])
    text_img = Image.new("RGBA", (text_width, text_height + 2), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((0, 0), text, font=font, fill=fill)
    # Rotate the text image
    rotated = text_img.rotate(angle, expand=1)
    # Paste the rotated text onto the original image
    image.paste(rotated, (x - 1, 0), rotated)
    return text_width, text_height


data = {
    0: {"activity": 1000},
    20: {"activity": 1100},
    40: {"activity": 2000},
    60: {"activity": 1833},
    80: {"activity": 1200},
    100: {"activity": 1300},
}

line_color = (255, 255, 255)
line_color = (0, 0, 0)

max_activity = max(item["activity"] for item in data.values())
max_activity_key = max(data, key=lambda k: data[k]["activity"])
max_key = max(data.keys())

im = Image.new("RGBA", (len(data) * 10 + 3, 75), (0, 0, 0, 0))

draw = ImageDraw.Draw(im)

font = ImageFont.load_default(10)

draw.line((0, 0, 0, im.height - 1), fill=line_color, width=1)
draw.line((0, im.height - 1, im.width, im.height - 1), fill=line_color, width=1)
for key, value in data.items():
    x = 1 + (max_key - key) // 2
    y = im.height - 2
    draw.rectangle(
        (x, y - int((value["activity"] / max_activity) * im.height) + 2, x + 9, y),
        fill=__determine_color(key),
    )
    if key == max_activity_key:
        draw_rotated_text(im, font, f"{max_activity}", 90, x, 2, fill=(0, 0, 0))

im.save("activity.png", "PNG")

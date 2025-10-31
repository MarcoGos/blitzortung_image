from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


def __determine_color(strike_time: float) -> tuple[int, int, int]:
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


ages = [20, 40, 60, 80, 100]

im = Image.new("RGBA", (90, len(ages) * 20 + 5))  # , color=(12, 66, 156, 0))

draw = ImageDraw.Draw(im)

draw.rounded_rectangle(
    (0, 0, im.width - 1, im.height - 1), radius=10, fill=(12, 66, 156)
)

font = ImageFont.load_default(16)
for i in ages:
    x = 10
    y = 12 + (i - 20)
    draw.ellipse(
        (x - 2, y - 2, x + 2, y + 2),
        fill=__determine_color(datetime.now().timestamp() - (i - 20) * 60),
        outline=None,
    )
    draw.text(
        (x + 37, y),
        f"{i}",
        font=font,
        fill=(255, 255, 255),
        anchor="rm",
    )
draw.text(
    (53, 12),
    "min.",
    font=font,
    fill=(255, 255, 255),
    anchor="lm",
)

im.save("legend.png", "PNG")

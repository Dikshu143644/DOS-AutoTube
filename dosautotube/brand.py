"""DOS brand constants: palette, fonts, logo. One place, so every video looks like DOS."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
LOGO = ASSETS / "logo.png"

# Dark warm base + peach / pink / lavender neon (the DOS look)
BG = (14, 10, 13)
BG2 = (28, 16, 26)
PEACH = (255, 154, 90)
PINK = (255, 111, 168)
LAVENDER = (201, 166, 255)
WHITE = (247, 242, 247)
MUTED = (190, 176, 196)
GRADIENT = [PEACH, PINK, LAVENDER]

CHANNEL_NAME = "DOS AI Explained"
CHANNEL_HANDLE = "@DOSAIExplained"
CHANNEL_URL = "https://www.youtube.com/@DOSAIExplained"

# Style line appended to every image prompt so generated art stays on-brand.
IMAGE_STYLE = (
    "Premium cinematic 3D render. Dark warm near-black background (#0E0A0D). Glossy chrome and "
    "iridescent glass materials with neon rim light in peach-orange (#FF9A5A), hot pink (#FF6FA8) "
    "and lavender (#C9A6FF). Soft volumetric glow, studio lighting, shallow depth of field, high "
    "detail, clean minimal composition. Absolutely no text, no letters, no numbers, no logos, no watermarks."
)


def font(weight: str = "Bold", size: int = 64):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / f"Montserrat-{weight}.ttf"), size)

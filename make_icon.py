# make_icon.py — round the corners of scryptian.ico and write a multi-size icon.ico.
#
# Usage: python make_icon.py
# Tweak RADIUS (in px at 256 base) to control how rounded the corners are.

from PIL import Image, ImageDraw

SRC = "scryptian.ico"
DST = "icon.ico"
RADIUS = 44  # corner radius in px (applied to the 256px source frame)

src = Image.open(SRC).convert("RGBA")  # largest frame (256x256)
w, h = src.size

mask = Image.new("L", (w, h), 0)
d = ImageDraw.Draw(mask)
d.rounded_rectangle([0, 0, w - 1, h - 1], radius=RADIUS, fill=255)

src.putalpha(mask)

sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
src.save(DST, format="ICO", sizes=sizes)
print(f"Wrote {DST} with sizes {[s[0] for s in sizes]}")

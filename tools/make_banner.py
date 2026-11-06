from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 720
S = 2
rng = np.random.default_rng(2026)
y, x = np.mgrid[0:H*S, 0:W*S]
x = x / S; y = y / S
light = 1.6 * np.exp(-((x - W*.50)**2 / (W*.55)**2 + (y - H*.48)**2 / (H*.65)**2))
noise = rng.normal(0, .42, x.shape)
texture = .18 * np.sin((x + y) * .28)
pixels = np.empty((*x.shape, 3), dtype=np.uint8)
for c, b in enumerate((10, 12, 15)):
    pixels[:, :, c] = np.clip(b + light + noise + texture, 0, 255)
im = Image.fromarray(pixels).convert("RGBA")
d = ImageDraw.Draw(im)
col = (255, 157, 48, 255)

def line(points, width=2):
    d.line([(int(a*S), int(b*S)) for a, b in points], fill=col, width=width)

sx, sy = W/1536, H/864
def sc(v, axis="x"):
    return v * (sx if axis == "x" else sy)

boxes = [
    (sc(47), sc(44,"y"), sc(95), sc(92,"y"), 180, 270),
    (sc(1440), sc(44,"y"), sc(1488), sc(92,"y"), 270, 360),
    (sc(47), sc(768,"y"), sc(95), sc(816,"y"), 90, 180),
    (sc(1440), sc(768,"y"), sc(1488), sc(816,"y"), 0, 90),
]
for x0,y0,x1,y1,start,end in boxes:
    d.arc(tuple(round(v*S) for v in (x0,y0,x1,y1)), start, end, fill=col, width=2)

line([(sc(71), sc(44,"y")), (sc(298), sc(44,"y"))])
line([(sc(47), sc(68,"y")), (sc(47), sc(272,"y"))])
line([(sc(1238), sc(44,"y")), (sc(1464), sc(44,"y"))])
line([(sc(1488), sc(68,"y")), (sc(1488), sc(272,"y"))])
line([(sc(47), sc(592,"y")), (sc(47), sc(792,"y"))])
line([(sc(71), sc(816,"y")), (sc(298), sc(816,"y"))])
line([(sc(1488), sc(592,"y")), (sc(1488), sc(792,"y"))])
line([(sc(1238), sc(816,"y")), (sc(1464), sc(816,"y"))])

# Integrated wordmark only (no separate giant T + title)
wm = Image.open(ROOT / "assets/wordmark.png").convert("RGBA")
arr = np.array(wm)
mask = (arr[:,:,3] > 20) & ((arr[:,:,0] > 25) | (arr[:,:,1] > 25) | (arr[:,:,2] > 25))
ys, xs = np.where(mask)
wm = wm.crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1))
target_w = int(820 * S)
wm = wm.resize((target_w, int(target_w * wm.height / wm.width)), Image.Resampling.LANCZOS)
wx = (W*S - wm.width) // 2
wy = int(H*S * 0.38) - wm.height // 2
im.alpha_composite(wm, (wx, wy))

d = ImageDraw.Draw(im)
font_path = "/usr/share/fonts/truetype/sand-box/google/Quicksand/Quicksand-VariableFont_wght.ttf"
f = ImageFont.truetype(font_path, round(36 * S))
try:
    f.set_variation_by_axes([400])
except Exception:
    pass
sub = "Audio a texto en local"
bbox = d.textbbox((0, 0), sub, font=f)
tw = bbox[2]-bbox[0]
sx_t = (W*S - tw) // 2
sy_t = wy + wm.height + int(28 * S)
d.text((sx_t, sy_t), sub, font=f, fill=(182, 185, 191, 255))

out = im.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
(ROOT / "docs").mkdir(exist_ok=True)
out.save(ROOT / "docs/banner-hero.png", optimize=True)
out.save(ROOT / "docs/banner-social.png", optimize=True)
print(ROOT / "docs/banner-hero.png")

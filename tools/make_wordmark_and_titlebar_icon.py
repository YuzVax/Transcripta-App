"""Generate wordmark.png from the user's exact reference, plus titlebar.ico.

The wordmark is the user's provided T+ranscripta image with the dark caption
background (#0B0E14) keyed out — no recomposed T spacing. titlebar.ico is
solid #0B0E14 so the caption icon is invisible; PE file icon stays logo.ico.
"""
from pathlib import Path
from PIL import Image
import shutil

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
OUT_WORDMARK = ASSETS / "wordmark.png"
OUT_TITLEBAR = ASSETS / "titlebar.ico"
REF = ROOT / "tools/logo-reference/user-wordmark-reference.png"
CAPTION = (0x0B, 0x0E, 0x14, 255)  # #0B0E14 — OptimiZation DWM caption/border
BG = (11, 14, 20)
SCALE = 4  # high-res master for LANCZOS downscale in header/splash


def key_out_bg(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    pixels = im.load()
    w, h = im.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            d = ((r - BG[0]) ** 2 + (g - BG[1]) ** 2 + (b - BG[2]) ** 2) ** 0.5
            if d < 18:
                continue
            if d < 36:
                op[x, y] = (r, g, b, int(255 * (d - 18) / 18))
            else:
                op[x, y] = (r, g, b, 255)
    alpha = out.getchannel("A")
    bbox = alpha.point(lambda p: 255 if p > 8 else 0).getbbox()
    trimmed = out.crop(bbox) if bbox else out
    pad = 2
    final = Image.new("RGBA", (trimmed.width + 2 * pad, trimmed.height + 2 * pad), (0, 0, 0, 0))
    final.alpha_composite(trimmed, (pad, pad))
    return final


def make_wordmark() -> Image.Image:
    if not REF.exists():
        raise FileNotFoundError(f"Missing user wordmark reference: {REF}")
    small = key_out_bg(Image.open(REF))
    return small.resize((small.width * SCALE, small.height * SCALE), Image.Resampling.LANCZOS)


def make_titlebar_ico() -> None:
    sizes = (16, 20, 24, 32, 40, 48, 64, 256)
    images = [Image.new("RGBA", (n, n), CAPTION) for n in sizes]
    images[0].save(OUT_TITLEBAR, format="ICO", sizes=[(n, n) for n in sizes])


def main():
    ASSETS.mkdir(exist_ok=True)
    wordmark = make_wordmark()
    wordmark.save(OUT_WORDMARK, optimize=True)
    make_titlebar_ico()
    print({
        "wordmark": str(OUT_WORDMARK),
        "wordmark_size": wordmark.size,
        "titlebar_ico": str(OUT_TITLEBAR),
        "caption": "#0B0E14",
        "source": str(REF),
    })


if __name__ == "__main__":
    main()

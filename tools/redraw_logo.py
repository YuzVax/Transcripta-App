"""Draw the T from OptimiZation's actual Z ribbon pixels, not a new look.

The only original Z construction available is raster artwork (256 px) followed
by packer/RecolorLogo.py, an HSV remap to #FF941C that preserves S/V/alpha.
We retain the top ribbon verbatim and re-form the diagonal texture into an italic T
stem, retaining its gold highlights, folded shading, soft amber shadow and
edge treatment. No new hard bevel, outline, extrusion, or different palette.
Requires Pillow and numpy. Reproducible; python3 tools/redraw_logo.py.
"""
from pathlib import Path
import hashlib, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "tools/logo-reference/optimization-Z.png"
S = 4


def path_mask(start, commands):
    points = [start]
    x, y = start
    for command in commands:
        if len(command) == 2:
            x, y = command
            points.append((x, y))
        else:
            x1, y1, x2, y2, x3, y3 = command
            for t in np.linspace(0, 1, 65)[1:]:
                u = 1 - t
                points.append((u**3*x + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3,
                               u**3*y + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3))
            x, y = x3, y3
    mask = Image.new("L", (256*S, 256*S))
    ImageDraw.Draw(mask).polygon([(round(x*S), round(y*S)) for x, y in points], fill=255)
    return mask.resize((256, 256), Image.Resampling.LANCZOS)


def main():
    z = Image.open(REF).convert("RGBA")
    assert hashlib.sha256(REF.read_bytes()).hexdigest() == "9cd61eacafc4c6830718a17ca88e90c4acf520030c4a7ff0fe21ef90f2a8fe0e"
    top_mask = path_mask((26, 109), [
        (59, 66), (68, 54, 77, 51, 87, 51), (225, 51),
        (241, 51, 243, 61, 233, 74), (219, 88), (72, 88),
        (52, 88, 39, 97, 26, 109),
    ])
    diagonal = path_mask((166, 88), [
        (188, 88), (207, 88, 208, 101, 198, 113),
        (182, 129, 146, 145, 112, 165),
        (90, 179, 74, 190, 59, 204), (25, 204),
        (14, 205, 17, 197, 20, 192), (45, 161),
        (54, 150, 63, 144, 74, 138), (154, 96),
        (161, 92, 165, 90, 166, 88),
    ])
    stem_mask = path_mask((143, 88), [
        (188, 88), (169, 98, 164, 113, 155, 137), (136, 186),
        (131, 199, 126, 204, 115, 204), (87, 204),
        (78, 204, 83, 197, 87, 190),
        (103, 165, 108, 141, 117, 114),
        (121, 101, 132, 92, 143, 88),
    ])
    # Transfer the *actual* Z front-face texture row by row to the new stroke.
    # This avoids sampling the Z's lower bar, which does not belong in a T.
    za = np.asarray(z)
    src_mask = np.asarray(diagonal)
    target_mask = np.asarray(stem_mask)
    texture = np.zeros_like(za)
    for y in range(88, 205):
        sx = np.flatnonzero(src_mask[y] > 220)
        tx = np.flatnonzero(target_mask[y] > 0)
        if not len(sx) or not len(tx):
            continue
        u = np.linspace(0.04, 0.90, len(tx))
        positions = sx[0] + u*(sx[-1]-sx[0])
        for c in range(3):
            texture[y, tx, c] = np.interp(positions, np.arange(256), za[y,:,c]).astype(np.uint8)
        texture[y, tx, 3] = 255
    stem_texture = Image.fromarray(texture)
    affine = "row-wise original ribbon texture transfer into T silhouette"
    def clipped(image, mask):
        result = image.copy()
        result.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
        return result
    top = clipped(z, top_mask)
    stem = clipped(stem_texture, stem_mask)
    silhouette = ImageChops.lighter(top.getchannel("A"), stem.getchannel("A"))
    # The original has a broad amber, rather than black, halo. Match its low
    # opacity and source hue; shadow lives behind the ribbon, not as an outline.
    glow_alpha = silhouette.filter(ImageFilter.GaussianBlur(12)).point(lambda a: round(a*.26))
    glow = Image.new("RGBA", z.size, (255, 148, 28, 0)); glow.putalpha(glow_alpha)
    dark_alpha = silhouette.filter(ImageFilter.GaussianBlur(5)).point(lambda a: round(a*.30))
    dark = Image.new("RGBA", z.size, (77, 40, 0, 0)); dark.putalpha(dark_alpha)
    result = Image.alpha_composite(glow, dark)
    result = Image.alpha_composite(result, stem)
    result = Image.alpha_composite(result, top)
    # Store the same native resolution as Z; upscale never invents a new style.
    out = ROOT / "assets"
    result.save(out / "logo.png", optimize=True)
    result.save(out / "logo.ico", format="ICO", sizes=[(n,n) for n in (16,20,24,32,40,48,64,96,128,256)])
    meta = {"source_z_sha256": hashlib.sha256(REF.read_bytes()).hexdigest(),
            "method": "actual Z top-ribbon pixels + original diagonal ribbon texture on an italic T stem; amber halo; no added bevel",
            "source_hue": "#FF941C (original HSV recolor preserves saturation/value/alpha)",
            "stem_texture_mapping": affine, "logo_sha256": hashlib.sha256((out/"logo.png").read_bytes()).hexdigest()}
    (ROOT / "dist/logo-style-v1.1.5.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))

if __name__ == "__main__":
    main()

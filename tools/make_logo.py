"""Genera logo.png y logo.ico a partir de una imagen de origen.

Si la imagen trae las esquinas en negro (fondo opaco en vez de transparente),
las recorta con una mascara de esquinas redondeadas para que queden
transparentes (sin esquinas negras).

Guarda el resultado en la carpeta assets/ del proyecto.
Uso: python tools/make_logo.py <ruta_imagen>
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

# Carpeta assets/ (este script vive en tools/, la raiz es la carpeta superior).
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

if len(sys.argv) < 2:
    print("Uso: python tools/make_logo.py <ruta_de_la_imagen>")
    sys.exit(1)
src = sys.argv[1]
img = Image.open(src).convert("RGBA")

# Recorte al contenido VISIBLE. Usamos un umbral de alpha (>10) para ignorar
# halos/sombras casi invisibles que, si no, dejarian el dibujo pequeno dentro
# del cuadro. Asi el logo ocupa el maximo posible.
mask = img.split()[3].point(lambda p: 255 if p > 10 else 0)
bbox = mask.getbbox()
if bbox:
    img = img.crop(bbox)

# Cuadrar.
w, h = img.size
side = max(w, h)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)


def is_black(px, thr=24):
    return px[0] <= thr and px[1] <= thr and px[2] <= thr


def detect_corner_radius(im):
    """Estima el radio de la esquina redondeada midiendo, en la columna del
    borde izquierdo, cuanto negro hay desde arriba hasta el primer pixel de
    color (el inicio del tramo recto del cuadrado)."""
    s = im.size[0]
    px = im.load()
    x = 1
    for y in range(s):
        if not is_black(px[x, y]):
            return y
    return 0


def add_rounded_corners(im):
    """Pone transparente lo que quede fuera de un rectangulo redondeado que
    encaja con la forma del icono. Solo afecta a pixeles negros de las esquinas,
    asi que no recorta el degradado."""
    s = im.size[0]
    radius = detect_corner_radius(im)
    # Margenes de seguridad: si la deteccion falla, usar ~22% (estilo iOS).
    if radius < s * 0.05 or radius > s * 0.45:
        radius = int(s * 0.22)

    # Mascara del rectangulo redondeado (255 dentro, 0 fuera).
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1],
                                           radius=radius, fill=255)

    # Combinar: alpha final = alpha original AND mascara. Asi solo recortamos
    # las esquinas; el resto del icono se mantiene intacto.
    r, g, b, a = im.split()
    a = Image.composite(a, Image.new("L", (s, s), 0), mask)
    im.putalpha(a)
    return im, radius


def corners_are_opaque(im, thr=200):
    """True si las 4 esquinas son opacas (fondo solido). Si son transparentes,
    no hace falta recortar esquinas (el logo ya viene recortado)."""
    s = im.size[0]
    a = im.split()[3]
    pts = [(1, 1), (s - 2, 1), (1, s - 2), (s - 2, s - 2)]
    return all(a.getpixel(p) >= thr for p in pts)


# Solo recortamos esquinas si el logo trae fondo opaco (p. ej. cuadrado negro).
# Si ya tiene fondo transparente, lo dejamos tal cual.
if corners_are_opaque(canvas):
    canvas, radius = add_rounded_corners(canvas)
else:
    radius = 0

canvas.save(ASSETS_DIR / "logo.png")
canvas.save(ASSETS_DIR / "logo.ico",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                   (64, 64), (128, 128), (256, 256)])
print(f"Logo aplicado en {ASSETS_DIR}. Cuadro: {canvas.size}, "
      f"radio esquinas: {radius}px")

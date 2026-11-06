"""Compose actual Windows UI captures and original/new logo comparisons."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/"dist"
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
font=ImageFont.truetype(FONT,18)
small=ImageFont.truetype(FONT,14)
for state,version in [("before","1.1.4"),("after","1.1.5")]:
    out=Image.new("RGBA",(810,620),"#0B0E14");d=ImageDraw.Draw(out)
    d.text((24,18),("ANTES" if state=="before" else "DESPUÉS")+" · v"+version,font=font,fill="#E8EAED")
    d.text((24,64),"Z original · OptimiZation",font=small,fill="#929CAB")
    d.text((410,64),"T · Transcripta",font=small,fill="#929CAB")
    z=Image.open(ROOT/"tools/logo-reference/optimization-Z.png").convert("RGBA").resize((280,280))
    t=Image.open(ROOT/("dist/logo-before-v1.1.4.png" if state=="before" else "assets/logo.png")).convert("RGBA").resize((280,280))
    out.alpha_composite(z,(24,89));out.alpha_composite(t,(410,89))
    d.text((24,380),"Cabecera real",font=small,fill="#929CAB")
    head=Image.open(DIST/("header-"+state+"-v1.1.5.png")).convert("RGBA").crop((12,35,420,87))
    out.alpha_composite(head,(24,405))
    d.text((24,468),"«Preparando Transcripta» · captura real",font=small,fill="#929CAB")
    splash=Image.open(DIST/("splash-"+state+"-v1.1.5.png")).convert("RGBA").resize((336,120))
    out.alpha_composite(splash,(24,493))
    d.text((410,496),"Vista de pruebas con Wine.",font=small,fill="#929CAB")
    d.text((410,520),"El color DWM de la barra requiere",font=small,fill="#929CAB")
    d.text((410,544),"verificación nativa en Windows.",font=small,fill="#929CAB")
    out.convert("RGB").save(DIST/("preview-"+state+"-v1.1.5.png"))

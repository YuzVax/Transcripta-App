# Referencia de estilo, no se distribuye en el payload

`optimization-Z.png` es la Z naranja original de OptimiZation, 256×256,
SHA256 `9cd61eacafc4c6830718a17ca88e90c4acf520030c4a7ff0fe21ef90f2a8fe0e`.
La referencia procede de los recursos gráficos originales de OptimiZation.

No hay SVG ni generador vectorial original en esas fuentes. El código original
`packer/RecolorLogo.py` conserva forma/alpha/saturación/valor del raster morado
y cambia solo el matiz HSV (235–335° → 31,72°, #FF941C).

`../redraw_logo.py` conserva los píxeles de la cinta superior y traslada la
textura real de la diagonal a un asta T inclinada y curva. Por tanto se conserva
la luz oro pálido arriba-derecha, naranja cálido, pliegue marrón/ámbar y borde
suave. Se eliminó el bisel duro y el volumen negro añadido en v1.1.4.

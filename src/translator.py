"""
Traduccion LOCAL y privada con Argos Translate.

- No usa servicios externos: la traduccion se hace en tu equipo.
- El paquete de idioma se DESCARGA bajo demanda la primera vez que eliges ese
  idioma (necesita internet solo en esa primera descarga). Despues queda
  instalado y funciona sin conexion.
- Si no existe un par directo, se traduce haciendo pivote por inglés
  (instalando origen→inglés e inglés→destino).
"""

# Idiomas disponibles para traducir: nombre mostrado -> codigo ISO de Argos.
TARGET_LANGS = {
    # Destinos Argos (Inglés incluido). Sin ja/ko/ar/zh.
    "Español": "es",
    "Inglés": "en",
    "Italiano": "it",
    "Portugués": "pt",
    "Francés": "fr",
    "Alemán": "de",
    "Ruso": "ru",
}


def _is_installed(from_code, to_code):
    import argostranslate.translate as t
    langs = t.get_installed_languages()
    src = next((l for l in langs if l.code == from_code), None)
    dst = next((l for l in langs if l.code == to_code), None)
    if not src or not dst:
        return False
    try:
        return src.get_translation(dst) is not None
    except Exception:
        return False


def _install_pair(from_code, to_code, status=None):
    """Descarga e instala el paquete directo from->to si existe."""
    import argostranslate.package as pkg
    available = pkg.get_available_packages()
    match = next((p for p in available
                  if p.from_code == from_code and p.to_code == to_code), None)
    if match is None:
        return False
    if status:
        status(f"Descargando idioma {from_code} → {to_code}...")
    path = match.download()
    pkg.install_from_path(path)
    return True


def ensure_languages(from_code, to_code, status=None):
    """Asegura que se puede traducir from->to, descargando lo necesario.
    Devuelve True si queda listo. Usa pivote por ingles si hace falta.
    """
    import argostranslate.package as pkg

    if from_code == to_code:
        return True
    if _is_installed(from_code, to_code):
        return True

    # Actualiza el indice de paquetes (requiere internet la primera vez).
    if status:
        status("Buscando paquetes de idioma disponibles...")
    pkg.update_package_index()

    # 1) Intento de par directo.
    if _install_pair(from_code, to_code, status):
        if _is_installed(from_code, to_code):
            return True

    # 2) Pivote por ingles: from->en y en->to.
    if from_code != "en":
        _install_pair(from_code, "en", status)
    if to_code != "en":
        _install_pair("en", to_code, status)

    return _is_installed(from_code, to_code)


def translate(text, from_code, to_code, status=None):
    """Traduce 'text' de 'from_code' a 'to_code' localmente."""
    text = (text or "").strip()
    if not text:
        return ""
    if from_code == to_code:
        return text

    if not ensure_languages(from_code, to_code, status):
        raise RuntimeError(
            f"No hay paquete de traduccion disponible para {from_code} → "
            f"{to_code} (ni directo ni por ingles). Prueba otro idioma.")

    import argostranslate.translate as t
    langs = t.get_installed_languages()
    src = next(l for l in langs if l.code == from_code)
    dst = next(l for l in langs if l.code == to_code)
    if status:
        status(f"Traduciendo a {to_code}...")
    return src.get_translation(dst).translate(text)

# Empaquetado Windows x64 desde Linux

```sh
python3 packer/Build.py
```

Necesita Python 3.11+ con `packaging` para las pruebas, `msiextract` (msitools),
7-Zip, PowerShell 7 con Roslyn y las reference assemblies de .NET Framework 4.8.
Los dos últimos caminos se pueden pasar como `--pwsh` y `--reference-dir`.
Utiliza rutas de herramientas disponibles en tu propio entorno de construcción.

Las descargas tienen URL y SHA256 fijados en `downloads.lock.json`. Si están en
`packer/downloads`, se comprueban sin descargarlas de nuevo. No se ejecuta pip,
ningún instalador ni código Windows durante la construcción. Las wheels se
extraen a `python/Lib/site-packages`; se reubican sus carpetas purelib/platlib.
El runtime no necesita pip. Se omiten las bibliotecas estáticas, cabeceras de
desarrollo y bytecode precalculado innecesarios; se conservan las DLL de ejecución
y las licencias. Tcl/Tk se añade explícitamente, porque el paquete
embebible de Python no lo incluye. Se añaden las DLL de Microsoft app-local.

`Build.py --assemble-only` prepara la carpeta para pruebas sin comprimir.
`Build.py --compile-only` recompila un payload ya construido.
`Compile.ps1` utiliza Roslyn sobre Linux; no necesita Visual Studio ni Windows.

Cada archivo del payload se verifica después de extraerlo. Se rechazan rutas
fuera de la sesión, duplicados y enlaces. El lanzador usa un mutex por usuario
y un Job Object Windows con `KILL_ON_JOB_CLOSE`, para no dejar FFmpeg ni otros
procesos hijos ejecutándose cuando termine la sesión. La marca de sesión guarda
PID y hora de inicio, evitando confundir PID reutilizados con una sesión viva.

`Bootstrap.py --self-test` comprueba importaciones nativas, Tcl/Tk, CPU, FFmpeg y
rutas de caché sin descargar modelos. Para probar toda la extracción y limpieza
en Windows se puede ejecutar `Transcripta_v2.exe --self-test`.

## Pruebas antes de publicar

Verificar el PE y los hashes en Linux no sustituye una prueba en Windows 10/11.
Abrir, transcribir un audio corto, traducir y exportar; cerrar y comprobar que no
queda `%LocalAppData%\Transcripta`. Probar también cerrar durante una descarga,
reiniciar después de forzar el cierre y abrir con una GPU NVIDIA instalada
(esta edición debe seguir usando CPU). El ejecutable no está firmado; véase [AVISO_SMARTSCREEN.md](../AVISO_SMARTSCREEN.md).

## Regresiones de interfaz y cancelación

`python -B tests/test_session_ui.py` utiliza una ventana Tk real, sin descargar
modelos. Comprueba TkDND, rutas con espacios/tildes/llaves, filtrado, carpetas de
sesión, exportación, controles de la cola, progreso global y cancelación de
conversión/segmentos. En Linux necesita una pantalla (por ejemplo Xvfb); también
puede ejecutarse con el Python Windows integrado. La prueba con Wine no sustituye
un arrastre real desde el Explorador de Windows 10/11.

TkinterDnD2 0.6.3 está fijado por SHA256; se incluye su extensión nativa para
Windows x64 y Tcl/Tk 8.6. `--self-test` también crea la interfaz y verifica que
TkDND se cargue. La ruta `USERPROFILE` real se conserva para los diálogos;
modelos y cachés siguen redirigidos a la sesión temporal que se borra al cerrar.

## Identidad visual v1.1.5

- `python3 tools/redraw_logo.py` reproduce el PNG/ICO a partir del raster real de
  la Z (fuente fijada por SHA256 en `tools/logo-reference/`), sin inventar otro
  bisel. `python3 -B tests/test_logo_assets.py` comprueba la fidelidad de colores
  y los 10 tamaños ICO.
- El wordmark recorta por alpha >220 (la cinta, no el halo) en Tk y en WinForms.
- CTk añadía su icono azul a los 200 ms: `_windows_set_titlebar_icon` está
  anulado y las llamadas HWND/LRESULT tienen prototipos correctos de 64 bits.
- `tools/preview_branding.py` captura ventanas Tk reales con el Python Windows.
  `packer/PreviewSplash.cs` llama al splash real por reflexión sin extraer el
  payload ni iniciar el motor. El progreso se pinta en naranja/gris, sin
  depender de temas nativos que pudieran ignorar ForeColor.
- Pruebas Wine: usar el UCRT nativo de Microsoft ya instalado en el prefijo
  (`WINEDLLOVERRIDES=ucrtbase=n`); el self-test completo necesita además
  `KMP_AFFINITY=disabled OMP_NUM_THREADS=1` por una API NUMA no implementada en
  Wine. Son ajustes del entorno de pruebas, no cambios al EXE ni requisitos de
  Windows. Se debe revisar la barra DWM en Windows 10/11 real.

## Icono del archivo portátil (v1.1.10)

El entregable es `Transcripta_v2.exe`; la versión interna es 1.1.10.
Se usa `CreateDefaultWin32Resources(..., manifest, assets/logo.ico)`, exactamente
como OptimiZation, no solo un recurso .NET. `Build.py` ejecuta `VerifyIcon.py`
y falla si hay otro grupo/icono antiguo o si cualquiera de los 10 tamaños no
coincide byte a byte con la T naranja. La verificación requiere `pefile` y Pillow.

```sh
python3 packer/VerifyIcon.py dist/Transcripta_v2.exe --output dist/icon-proof-v1.1.10
```

Si Windows muestra un icono antiguo, el nuevo nombre evita reutilizar su entrada
anterior. Una caché del Explorador obsoleta puede necesitar actualizar la vista o
reiniciar el Explorador; el verificador prueba los píxeles del PE, no esa caché.

# Componentes de terceros

Transcripta es de YuzVax. La licencia de los materiales propios está en
`LICENSE`; no sustituye las licencias de terceros ni revoca permisos de
publicaciones anteriores. El EXE reutilizado conserva los avisos de su
compilación original. Los componentes siguientes se redistribuyen sin modificar
su motor y conservan sus respectivas licencias:

- CPython 3.11.9 Windows embeddable AMD64 y Tcl/Tk del MSI oficial de la misma
  versión: https://www.python.org/ftp/python/3.11.9/ (PSF y Tcl/Tk).
- Wheels Windows AMD64 o Python universal descargados de PyPI, incluida su
  metadata y licencias `*.dist-info/licenses` / `LICENSE`. Versiones, URL y
  hashes exactos: `packer/downloads.lock.json` y `packer/requirements-win.lock`.
- PyTorch 2.7.1+cpu: https://download.pytorch.org/whl/cpu/ (licencia BSD).
  Argos/Stanza lo importan; la transcripción usa CTranslate2, no PyTorch.
- FFmpeg / FFprobe 9.0.2 essentials static AMD64, compilación Gyan Doshi:
  https://www.gyan.dev/ffmpeg/builds/ (GPLv3, licencia y README originales
  incluidos en `ffmpeg/`). Procedencia exacta y checksum fijados en el lock.
  Código fuente de la versión: https://github.com/FFmpeg/FFmpeg/tree/n9.0.2
  y commit de la compilación: https://github.com/FFmpeg/FFmpeg/commit/946fcce07b
  Las opciones y versiones de bibliotecas están en el README del distribuidor.
  FFmpeg se ejecuta como proceso separado; no se enlaza al lanzador de Transcripta.
- Microsoft Visual C++ 2015–2022 runtime x64 14.44.35211: DLL app-local del
  redistribuible oficial https://aka.ms/vs/17/release/vc_redist.x64.exe .
  Se incluye su licencia RTF. No se ejecuta el instalador ni se cambia el sistema.

No se incluyen nvidia-cublas, nvidia-cudnn ni DLL cuDNN/cuBLAS. El lanzador
selecciona CPU explícitamente. Los modelos Whisper/Argos/MiniSBD se descargan
bajo demanda de sus proveedores y conservan sus propias licencias.

## Arrastrar y soltar

TkinterDnD2 0.6.3 (MIT) y la extensión TkDND incluida permiten arrastrar
archivos desde el Explorador. Sus avisos y licencias se conservan en
`python/Lib/site-packages/tkinterdnd2-0.6.3.dist-info/` y en los encabezados
de los archivos Tcl de `tkinterdnd2/tkdnd/win-x64/`.

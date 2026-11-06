"""
Motor de transcripcion.
- Usa faster-whisper (CTranslate2) como nucleo: rapido y preciso.
- Usa FFmpeg para convertir CUALQUIER formato de entrada (incluido .opus de
  WhatsApp, .ogg, .amr, .m4a, .mp4, .mkv, etc.) a WAV 16 kHz mono.
- Detecta GPU NVIDIA (CUDA) automaticamente y cae a CPU si no esta disponible.

No necesita PyTorch: faster-whisper corre sobre CTranslate2.
"""

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

# Formatos que aceptamos en la app (FFmpeg soporta muchos mas; estos cubren
# los casos reales de mensajeria, grabadoras y video).
SUPPORTED_EXTENSIONS = {
    ".opus", ".ogg", ".oga",          # WhatsApp / Telegram / web
    ".mp3", ".m4a", ".aac", ".wav",   # audio comun
    ".flac", ".wma", ".amr",          # otros audio
    ".mp4", ".mkv", ".mov", ".webm",  # video (extraemos la pista de audio)
    ".avi", ".mpeg", ".mpga",
}


def _add_cuda_dll_dirs():
    """En Windows, faster-whisper (CTranslate2) necesita encontrar las DLL de
    cuBLAS y cuDNN. Si se instalaron via pip (paquetes nvidia-*), sus carpetas
    'bin' no estan en el PATH; las anadimos aqui antes de importar la libreria.

    Buscamos todas las carpetas site-packages/nvidia/<lib>/bin y las
    registramos tanto con os.add_dll_directory como en el PATH (algunas DLL
    dependen de otras y necesitan resolverse via PATH).
    """
    if os.name != "nt":
        return
    try:
        import site
        roots = list(site.getsitepackages())
        roots.append(os.path.join(sys.prefix, "Lib", "site-packages"))
        seen = set()
        for root in roots:
            nvidia_dir = Path(root) / "nvidia"
            if not nvidia_dir.is_dir():
                continue
            for bin_dir in nvidia_dir.glob("*/bin"):
                key = str(bin_dir).lower()
                if key in seen or not bin_dir.is_dir():
                    continue
                seen.add(key)
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        # Si algo falla, simplemente intentaremos CPU mas adelante.
        pass


_add_cuda_dll_dirs()

from faster_whisper import WhisperModel  # noqa: E402


class TranscriptionCancelled(Exception):
    """Cancelación solicitada por el usuario, no un fallo de transcripción."""


def check_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise TranscriptionCancelled()


def ffmpeg_path() -> str:
    """Devuelve la ruta a ffmpeg o lanza un error claro si no esta instalado."""
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "FFmpeg no encontrado en el PATH. Instalalo con: winget install Gyan.FFmpeg"
        )
    return path


def convert_to_wav(input_path: str, cancel_event=None) -> str:
    """Convierte cualquier archivo de audio/video a WAV 16 kHz mono usando
    FFmpeg. Devuelve la ruta de un archivo temporal .wav.

    Este paso es el que garantiza el soporte universal de formatos, incluido
    .opus de WhatsApp.
    """
    check_cancelled(cancel_event)
    ffmpeg = ffmpeg_path()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    cmd = [
        ffmpeg,
        "-y",                  # sobrescribir
        "-i", input_path,
        "-vn",                 # ignorar video
        "-ac", "1",            # mono
        "-ar", "16000",        # 16 kHz (lo que espera Whisper)
        "-c:a", "pcm_s16le",
        tmp.name,
    ]
    process = None
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        while True:
            check_cancelled(cancel_event)
            try:
                _, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
        check_cancelled(cancel_event)
        if process.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-800:]
            raise RuntimeError(f"FFmpeg falló al convertir '{input_path}':\n{err}")
        return tmp.name
    except BaseException:
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def pick_device():
    """Elige (device, compute_type). Intenta CUDA y cae a CPU si no hay GPU."""
    if os.environ.get("TRANSCRIPTA_CPU_ONLY") == "1":
        return "cpu", "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def to_pinyin(text: str) -> str:
    """Convierte texto chino (hanzi) a pinyin con marcas de tono.
    Los caracteres no chinos (puntuacion, numeros, otras letras) se conservan
    tal cual. Si pypinyin no estuviera instalado, devuelve el texto original.
    """
    try:
        from pypinyin import pinyin, Style
    except ImportError:
        return text
    partes = pinyin(text, style=Style.TONE, errors="default")
    return " ".join(p[0] for p in partes if p and p[0]).strip()


class Transcriber:
    """Carga el modelo una sola vez y lo reutiliza para varios archivos."""

    def __init__(self, model_size: str = "large-v3", device: str = None,
                 compute_type: str = None):
        if device is None or compute_type is None:
            auto_device, auto_compute = pick_device()
            device = device or auto_device
            compute_type = compute_type or auto_compute
        self.device = device
        self.compute_type = compute_type
        self.model_size = model_size
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, input_path: str, language: str = None,
                   progress_cb=None, pinyin: bool = False, vocab: str = "",
                   cancel_event=None):
        """Transcribe un archivo. Devuelve (texto, info, segmentos).

        - language=None -> deteccion automatica.
        - progress_cb(fraccion_0a1, texto_parcial) se llama por cada segmento.
        - pinyin=True -> convierte la salida china (hanzi) a pinyin con tonos.
        - vocab -> nombres propios / palabras clave (separados por comas) para
          que el modelo los reconozca mejor. Se pasan como pista de contexto.
        """
        check_cancelled(cancel_event)
        vocab = (vocab or "").strip()
        # Construimos una frase de contexto natural con los nombres/vocabulario.
        # Esto sesga el reconocimiento hacia esas palabras concretas.
        initial_prompt = None
        hotwords = None
        if vocab:
            palabras = [w.strip() for w in vocab.replace("\n", ",").split(",") if w.strip()]
            if palabras:
                hotwords = " ".join(palabras)
                initial_prompt = "Vocabulario y nombres propios: " + ", ".join(palabras) + "."

        wav = convert_to_wav(input_path, cancel_event=cancel_event)
        segments = None
        try:
            check_cancelled(cancel_event)
            segments, info = self.model.transcribe(
                wav,
                language=language,
                vad_filter=True,  # filtra silencios -> mas rapido y limpio
                beam_size=5,
                initial_prompt=initial_prompt,
                hotwords=hotwords,
            )
            full_text = []
            seg_list = []
            duration = info.duration or 0
            iterator = iter(segments)
            while True:
                check_cancelled(cancel_event)
                try:
                    seg = next(iterator)  # El cálculo nativo no se interrumpe a la fuerza.
                except StopIteration:
                    break
                check_cancelled(cancel_event)
                text = to_pinyin(seg.text) if pinyin else seg.text
                full_text.append(text)
                seg_list.append((seg.start, seg.end, text.strip()))
                if progress_cb and duration:
                    progress_cb(min(seg.end / duration, 1.0), text)
            check_cancelled(cancel_event)
            joined = (" " if pinyin else "").join(full_text).strip()
            return joined, info, seg_list
        finally:
            try:
                if segments is not None and hasattr(segments, "close"):
                    segments.close()
            finally:
                try:
                    os.unlink(wav)
                except OSError:
                    pass


# ---- Exportadores de subtitulos -------------------------------------------

def _fmt_ts(seconds: float, sep: str = ",") -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(segments) -> str:
    lines = []
    for i, (start, end, text) in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def to_vtt(segments) -> str:
    lines = ["WEBVTT", ""]
    for start, end, text in segments:
        lines.append(f"{_fmt_ts(start, '.')} --> {_fmt_ts(end, '.')}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


# ---- Modo CLI (opcional, util para depurar) -------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python transcriber.py <archivo_de_audio>")
        sys.exit(1)
    dev, comp = pick_device()
    print(f"Dispositivo: {dev} ({comp})")
    t = Transcriber(model_size="large-v3", device=dev, compute_type=comp)
    text, info, segs = t.transcribe(sys.argv[1])
    print(f"Idioma detectado: {info.language} (prob {info.language_probability:.2f})")
    print("-" * 40)
    print(text)

"""
Transcripta - App de escritorio de transcripcion de audio.

GUI moderna (customtkinter) sobre el motor faster-whisper.
- Acepta multiples archivos (incluido .opus de WhatsApp).
- Transcribe en un hilo aparte para que la ventana no se congele.
- Exporta a .txt, .srt y .vtt.
"""

import os
import json
import threading
import queue
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES, COPY, REFUSE_DROP
    DnDBase = TkinterDnD.DnDWrapper
except ImportError:
    TkinterDnD = None
    DnDBase = object
    COPY, REFUSE_DROP = "copy", "refuse_drop"

try:
    from PIL import Image
except ImportError:
    Image = None

import transcriber as core
import translator as trans

# app.py vive en src/. La raiz del proyecto es la carpeta superior.
APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = Path(os.environ.get("TRANSCRIPTA_ROOT", APP_DIR.parent)).resolve()
ASSETS_DIR = ROOT_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"
ICON_PATH = ASSETS_DIR / "logo.ico"
WORDMARK_PATH = ASSETS_DIR / "wordmark.png"
TITLEBAR_ICON_PATH = ASSETS_DIR / "titlebar.ico"
CONFIG_PATH = ROOT_DIR / "config.json"
CREATOR = "YuzVax"
APP_VERSION = "1.1.10"
APP_TITLE = f"v{APP_VERSION}"  # Solo versión en la barra de título (sin nombre ni icono).

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")  # base; overridden below with YuzVax orange

# Paleta alineada con OptimiZation (oscuro + naranja)
BG = "#0B0E14"
CARD = "#141A24"
CARD_BORDER = "#222A37"
TEXT = "#E8EAED"
MUTED = "#929CAB"
TITLEBAR = "#0B0E14"  # Mismo DWM/caption que OptimiZation.
ACCENT = "#FF8C00"
ACCENT_HOVER = "#E67700"
ACCENT_SOFT = "#FFAA42"
DANGER = "#C62828"

MODELS = ["small", "medium", "large-v3"]
LANGS = {
    # Whisper (+ Detectar). Inglés incluido. Sin ja/ko/ar/zh.
    "Detectar automáticamente": None,
    "Español": "es",
    "Inglés": "en",
    "Italiano": "it",
    "Portugués": "pt",
    "Francés": "fr",
    "Alemán": "de",
    "Ruso": "ru",
}


def _carpeta_inicial():
    """Carpeta inicial del diálogo: Documentos/Escritorio reales, nunca la sesión temporal."""
    candidates = [
        os.environ.get("TRANSCRIPTA_USER_DOCUMENTS"),
        os.environ.get("TRANSCRIPTA_USER_DESKTOP"),
        os.environ.get("TRANSCRIPTA_USER_PROFILE"),
    ]
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(260)
            for csidl in (5, 0):  # Personal, Desktop
                if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0:
                    candidates.append(buf.value)
        except Exception:
            pass
    root = os.environ.get("TRANSCRIPTA_ROOT") or ""
    for c in candidates:
        if not c:
            continue
        try:
            path = Path(c)
            if not path.is_dir():
                continue
            # Evitar el home falso de la sesión empaquetada
            if root and Path(root) in path.resolve().parents:
                continue
            if "transcripta" in str(path).lower() and "sesion-" in str(path).lower():
                continue
            return str(path)
        except Exception:
            continue
    return None


class App(ctk.CTk, DnDBase):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x740")
        self.minsize(780, 640)
        self.configure(fg_color=BG)

        self.files = []
        self.transcriber = None
        self.last_segments = []
        self.msg_queue = queue.Queue()
        self.busy = False
        self._task = None
        self._last_dir = None  # Solo en memoria; nunca se guarda en config.json.
        self.cancel_event = threading.Event()
        self.last_text = ""
        self.last_lang = None
        self.config_data = self._load_config()

        self._set_window_icon()
        self._build_ui()
        self._setup_dnd()
        self.after(100, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if self.busy and not messagebox.askyesno(
                "Cerrar Transcripta",
                "Hay una tarea en curso. ¿Quieres detenerla y cerrar?\n"
                "Los resultados sin exportar se perderán."):
            return
        self.cancel_event.set()
        self.destroy()

    # ---- Preferencias (en el EXE, dentro de la sesión que se borra) --------------------
    def _load_config(self):
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_config(self):
        try:
            CONFIG_PATH.write_text(
                json.dumps(self.config_data, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def _set_window_icon(self):
        # AppUserModelID for the process. Caption shows only the version text:
        # the caption icon is a solid #0B0E14 square (invisible on the DWM bar).
        # Explorer still uses the orange T from the PE Win32 icon resource.
        try:
            if os.name == "nt":
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "YuzVax.Transcripta.v1")
        except Exception:
            pass
        self.after(50, self._apply_dark_titlebar)
        self.after(80, self._apply_invisible_titlebar_icon)
        self.after(250, self._apply_invisible_titlebar_icon)
        self.after(450, self._apply_invisible_titlebar_icon)
        self.bind("<Map>", self._refresh_titlebar, add="+")

    def _windows_set_titlebar_icon(self):
        """CTk calls this ~200 ms after init; replace its blue icon with ours."""
        self._apply_invisible_titlebar_icon()

    def _refresh_titlebar(self, event=None):
        if event is None or event.widget is self:
            self.after(30, self._apply_dark_titlebar)
            self.after(40, self._apply_invisible_titlebar_icon)

    def _native_window(self):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        hwnd = user32.GetAncestor(wintypes.HWND(self.winfo_id()), 2)  # GA_ROOT
        return user32, hwnd

    def _apply_dark_titlebar(self):
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes
            _, hwnd = self._native_window()
            DwmSetWindowAttribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            DwmSetWindowAttribute.argtypes = [
                wintypes.HWND, ctypes.c_uint,
                ctypes.POINTER(ctypes.c_int), ctypes.c_uint]
            value = ctypes.c_int(1)
            # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE; 19 = variante antigua.
            if DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), 4) < 0:
                DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), 4)
            background = ctypes.c_int(0x00140E0B)  # COLORREF BGR de #0B0E14 (OptimiZation)
            DwmSetWindowAttribute(hwnd, 34, ctypes.byref(background), 4)
            DwmSetWindowAttribute(hwnd, 35, ctypes.byref(background), 4)
            round_mode = ctypes.c_int(2)
            DwmSetWindowAttribute(hwnd, 33, ctypes.byref(round_mode), 4)
        except Exception:
            pass

    def _apply_invisible_titlebar_icon(self):
        """Caption icon = solid #0B0E14 (same as DWM bar → invisible)."""
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes
            # Prefer the solid caption-colored ICO so CTk cannot show its blue mark.
            if TITLEBAR_ICON_PATH.exists():
                try:
                    self.iconbitmap(default=str(TITLEBAR_ICON_PATH))
                except Exception:
                    try:
                        self.iconbitmap(str(TITLEBAR_ICON_PATH))
                    except Exception:
                        pass
            user32, hwnd = self._native_window()
            user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                wintypes.WPARAM, wintypes.LPARAM]
            user32.SendMessageW.restype = ctypes.c_ssize_t
            LoadImageW = ctypes.windll.user32.LoadImageW
            LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            LoadImageW.restype = wintypes.HANDLE
            # IMAGE_ICON=1, LR_LOADFROMFILE=0x10, LR_DEFAULTSIZE=0x40
            path = str(TITLEBAR_ICON_PATH) if TITLEBAR_ICON_PATH.exists() else None
            if not path:
                return
            small = LoadImageW(None, path, 1, 16, 16, 0x10)
            big = LoadImageW(None, path, 1, 32, 32, 0x10)
            if small:
                user32.SendMessageW(hwnd, 0x0080, 0, small)  # ICON_SMALL
            if big:
                user32.SendMessageW(hwnd, 0x0080, 1, big)  # ICON_BIG
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
        except Exception:
            pass

    # ---- Construccion de la interfaz --------------------------------------
    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 4))
        # Una sola imagen T+ranscripta (kerning fijo). Sin icono+label sueltos.
        wordmark = ctk.CTkFrame(header, fg_color="transparent")
        wordmark.pack(side="left")
        mark_path = WORDMARK_PATH if WORDMARK_PATH.exists() else LOGO_PATH
        if Image is not None and mark_path.exists():
            try:
                src = Image.open(mark_path).convert("RGBA")
                target_h = 36 if mark_path == WORDMARK_PATH else 34
                target_w = max(1, round(target_h * src.width / src.height))
                self._logo_img = ctk.CTkImage(
                    light_image=src, dark_image=src, size=(target_w, target_h))
                ctk.CTkLabel(
                    wordmark, image=self._logo_img, text="",
                    width=target_w, height=target_h,
                ).pack(side="left")
            except Exception:
                ctk.CTkLabel(
                    wordmark, text="Transcripta",
                    font=ctk.CTkFont(size=26, weight="bold"),
                    text_color=TEXT,
                ).pack(side="left")
        else:
            ctk.CTkLabel(
                wordmark, text="Transcripta",
                font=ctk.CTkFont(size=26, weight="bold"),
                text_color=TEXT,
            ).pack(side="left")

        ctk.CTkLabel(
            self,
            text="Audio a texto en local. Soporta .opus (WhatsApp), .mp3, .ogg, .m4a, .wav, .mp4 y más.",
            text_color=MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 10))

        opts = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        opts.pack(fill="x", padx=16, pady=4)

        menu_kw = dict(fg_color="#1A1D24", button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                       dropdown_fg_color="#1A1D24", dropdown_hover_color="#302117")
        ctk.CTkLabel(opts, text="Modelo:", text_color=TEXT).grid(row=0, column=0, padx=(12, 4), pady=10)
        self.model_var = ctk.StringVar(value="small" if os.environ.get("TRANSCRIPTA_CPU_ONLY") == "1" else "large-v3")
        ctk.CTkOptionMenu(opts, values=MODELS, variable=self.model_var,
                          width=120, **menu_kw).grid(row=0, column=1, padx=4)

        ctk.CTkLabel(opts, text="Idioma:", text_color=TEXT).grid(row=0, column=2, padx=(16, 4))
        self.lang_var = ctk.StringVar(value="Detectar automáticamente")
        ctk.CTkOptionMenu(opts, values=list(LANGS.keys()), variable=self.lang_var,
                          width=200, **menu_kw).grid(row=0, column=3, padx=4)

        self.device_label = ctk.CTkLabel(opts, text="Dispositivo: ...",
                                         text_color=MUTED)
        self.device_label.grid(row=0, column=4, padx=16)
        self._detect_device()

        vocab_frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        vocab_frame.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(
            vocab_frame,
            text="Nombres propios / vocabulario (separados por comas):",
            text_color=MUTED,
        ).pack(anchor="w", padx=12, pady=(8, 0))
        self.vocab_entry = ctk.CTkEntry(
            vocab_frame,
            placeholder_text="Ej: nombres de personas, marcas, lugares...",
            fg_color="#101216", border_color=CARD_BORDER, text_color=TEXT,
        )
        self.vocab_entry.pack(fill="x", padx=12, pady=(2, 10))

        btns = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        btns.pack(fill="x", padx=16, pady=4)
        self.add_btn = ctk.CTkButton(
            btns, text="Añadir archivos",
            fg_color="#262B35", hover_color="#303B4C", text_color=TEXT,
            command=self._add_files)
        self.add_btn.pack(side="left", padx=8, pady=8)
        self.clear_btn = ctk.CTkButton(
            btns, text="Limpiar lista",
            fg_color="#262B35", hover_color="#303B4C", text_color=TEXT,
            command=self._clear_files)
        self.clear_btn.pack(side="left", padx=4)
        self.files_label = ctk.CTkLabel(btns, text="0 archivos", text_color=MUTED)
        self.files_label.pack(side="left", padx=12)

        self.start_btn = ctk.CTkButton(
            btns, text="Transcribir", fg_color=ACCENT,
            hover_color=ACCENT_HOVER, text_color="#12161E",
            font=ctk.CTkFont(weight="bold"),
            command=self._start)
        self.start_btn.pack(side="right", padx=8)
        self.cancel_btn = ctk.CTkButton(
            btns, text="Cancelar", width=85, state="disabled",
            fg_color="#262B35", hover_color="#49302A", text_color=TEXT,
            command=self._cancel)
        self.cancel_btn.pack(side="right", padx=4)

        self.files_box = ctk.CTkTextbox(self, height=80, fg_color="#101216",
                                        border_color=CARD_BORDER, border_width=1, text_color=TEXT)
        self.files_box.pack(fill="x", padx=16, pady=4)
        self.files_box.configure(state="disabled")

        self.progress = ctk.CTkProgressBar(self, progress_color=ACCENT, fg_color="#303744")
        self.progress.pack(fill="x", padx=16, pady=(8, 2))
        self.progress.set(0)
        self.status = ctk.CTkLabel(self, text="Listo.", text_color=MUTED)
        self.status.pack(pady=(0, 4))

        # IMPORTANTE: las barras de abajo se anclan PRIMERO con side="bottom"
        # para que el sistema les reserve su espacio. Asi, al encoger la
        # ventana, el panel de resultados cede tamano pero los botones de
        # traducir/exportar nunca se ocultan.

        # Exportar (la mas abajo del todo)
        exp = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        exp.pack(side="bottom", fill="x", padx=16, pady=(4, 12))
        ctk.CTkLabel(exp, text="Exportar:", text_color=TEXT).pack(side="left", padx=(12, 6))
        self.export_btns = []
        for label, fmt in (("TXT", "txt"), ("SRT", "srt"), ("VTT", "vtt")):
            button = ctk.CTkButton(
                exp, text=label, width=70,
                fg_color="#262B35", hover_color="#303B4C", text_color=TEXT,
                command=lambda f=fmt: self._export(f))
            button.pack(side="left", padx=4)
            self.export_btns.append(button)
        # Única marca «by YuzVax»: abajo a la derecha (no en título ni cabecera).
        ctk.CTkLabel(
            exp, text=f"by {CREATOR}",
            font=ctk.CTkFont(size=10),
            text_color="#BE854C",
        ).pack(side="right", padx=(8, 12), pady=8)

        tr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        tr.pack(side="bottom", fill="x", padx=16, pady=4)
        ctk.CTkLabel(
            tr, text="Traducción local (offline). Al traducir eliges el idioma.",
            text_color=MUTED,
        ).pack(side="left", padx=(12, 4), pady=8)
        self.translate_btn = ctk.CTkButton(
            tr, text="Traducir", width=120,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#12161E",
            command=self._start_translate)
        self.translate_btn.pack(side="right", padx=8)

        self.result = ctk.CTkTextbox(
            self, font=ctk.CTkFont(size=14),
            fg_color="#101216", border_color=CARD_BORDER, border_width=1, text_color=TEXT)
        self.result.pack(fill="both", expand=True, padx=16, pady=4)
        self._make_readonly(self.result)

    def _make_readonly(self, textbox):
        """Permite seleccionar y copiar texto, pero bloquea la escritura.

        Mantenemos el widget en estado 'normal' (para poder insertar texto por
        codigo y poder seleccionar con el raton), pero interceptamos las teclas:
        dejamos pasar copiar (Ctrl+C), seleccionar todo (Ctrl+A) y las teclas de
        navegacion; cualquier otra pulsacion se descarta.
        """
        def on_key(event):
            ctrl = bool(event.state & 0x4)
            if ctrl and event.keysym.lower() in ("c", "a", "insert"):
                return  # copiar / seleccionar todo
            if event.keysym in (
                "Left", "Right", "Up", "Down", "Home", "End",
                "Prior", "Next", "Shift_L", "Shift_R",
                "Control_L", "Control_R",
            ):
                return  # navegacion y modificadores
            return "break"  # bloquea escritura/borrado

        textbox.bind("<Key>", on_key)
        # Bloquea pegar con el boton central del raton (estilo X11).
        textbox.bind("<Button-2>", lambda e: "break")

    def _detect_device(self):
        dev, comp = core.pick_device()
        nice = "GPU NVIDIA (CUDA)" if dev == "cuda" else "CPU"
        self.device_label.configure(text=f"Dispositivo: {nice}")
        self._device = dev
        self._compute = comp

    # ---- Archivos y arrastrar/soltar ---------------------------------------
    def _dialog_dir(self):
        if self._last_dir and Path(self._last_dir).is_dir():
            return self._last_dir
        return _carpeta_inicial()

    def _include_files(self, paths):
        """Misma validación para el diálogo y los archivos del Explorador."""
        if self.busy:
            return 0
        known = {os.path.normcase(os.path.abspath(p)) for p in self.files}
        added = ignored = 0
        for value in paths:
            path = Path(value)
            if path.suffix.lower() not in core.SUPPORTED_EXTENSIONS or not path.is_file():
                ignored += 1
                continue
            key = os.path.normcase(os.path.abspath(path))
            self._last_dir = str(path.resolve().parent)
            if key not in known:
                self.files.append(str(path))
                known.add(key)
                added += 1
        self._refresh_files()
        note = f"Añadidos: {added}. Total en cola: {len(self.files)}."
        if ignored:
            note += f" Omitidos: {ignored} (carpetas o formatos no admitidos)."
        self.status.configure(text=note)
        return added

    def _setup_dnd(self):
        self._dnd_available = False
        if TkinterDnD is None:
            self.status.configure(text="Arrastrar no disponible. Usa Añadir archivos.")
            return
        try:
            self.TkdndVersion = TkinterDnD.require(self)
            # Registrar también los widgets internos de CTk (incluido el Text
            # de la lista), para aceptar archivos sobre cualquier zona visible.
            pending = [self]
            while pending:
                widget = pending.pop()
                pending.extend(widget.winfo_children())
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<DropEnter>>", self._drop_action)
                widget.dnd_bind("<<DropPosition>>", self._drop_action)
                widget.dnd_bind("<<Drop>>", self._drop_files)
            self._dnd_available = True
            self.status.configure(text="Arrastra audios o vídeos a la ventana, o usa Añadir archivos.")
        except Exception as exc:
            print(f"Arrastrar archivos no disponible: {exc}")
            self.status.configure(text="Arrastrar no disponible. Usa Añadir archivos.")

    def _drop_action(self, _event):
        return REFUSE_DROP if self.busy else COPY

    def _drop_files(self, event):
        if self.busy:
            return REFUSE_DROP
        try:
            # Tcl conserva rutas con espacios, tildes y llaves; no usar split().
            paths = self.tk.splitlist(event.data)
        except Exception:
            self.status.configure(text="No se pudieron leer los archivos. Usa Añadir archivos.")
            return REFUSE_DROP
        self._include_files(paths)
        # Siempre copiar referencias; nunca mover ni borrar el audio original.
        return COPY

    def _add_files(self):
        if self.busy:
            return
        patterns = " ".join("*" + ext for ext in sorted(core.SUPPORTED_EXTENSIONS))
        opts = {
            "title": "Selecciona audios o vídeos",
            "filetypes": [("Audio y vídeo", patterns), ("Todos los archivos", "*.*")],
        }
        start = self._dialog_dir()
        if start:
            opts["initialdir"] = start
        try:
            paths = filedialog.askopenfilenames(**opts)
        except Exception:
            opts.pop("initialdir", None)
            paths = filedialog.askopenfilenames(**opts)
        if paths:
            self._include_files(paths)

    def _clear_files(self):
        if self.busy:
            return
        self.files = []
        self._refresh_files()

    def _refresh_files(self):
        self.files_label.configure(text=f"{len(self.files)} archivos")
        self.files_box.configure(state="normal")
        self.files_box.delete("1.0", "end")
        for number, path in enumerate(self.files, 1):
            self.files_box.insert("end", f"{number}. {Path(path).name}\n")
        self.files_box.configure(state="disabled")

    # ---- Cola y transcripción (en hilo) -----------------------------------
    def _set_busy(self, task):
        self.busy = bool(task)
        self._task = task
        state = "disabled" if self.busy else "normal"
        for button in (self.start_btn, self.translate_btn, self.add_btn,
                       self.clear_btn, *self.export_btns):
            button.configure(state=state)
        self.start_btn.configure(text="Transcribiendo..." if task == "transcribe" else "Transcribir")
        self.translate_btn.configure(text="Traduciendo..." if task == "translate" else "Traducir")
        self.cancel_btn.configure(state="normal" if task == "transcribe" else "disabled")

    def _cancel(self):
        if not self.busy or self._task != "transcribe":
            return
        self.cancel_event.set()
        self.cancel_btn.configure(state="disabled")
        self.status.configure(text="Cancelando... la descarga o el cálculo actual puede tardar en detenerse.")

    def _start(self):
        if self.busy:
            return
        if not self.files:
            messagebox.showwarning("Sin archivos", "Añade al menos un archivo.")
            return
        self.cancel_event.clear()
        self._set_busy("transcribe")
        self.progress.set(0)
        self.status.configure(text=f"Preparando cola de {len(self.files)} archivos...")
        self.result.delete("1.0", "end")
        self.last_segments = []
        self.last_text = ""
        self.last_lang = None
        selected = self.lang_var.get()
        lang = LANGS[selected]
        model = self.model_var.get()
        vocab = self.vocab_entry.get()
        threading.Thread(
            target=self._worker,
            args=(list(self.files), model, lang, vocab),
            daemon=True).start()

    def _worker(self, files, model, lang, vocab=""):
        completed = 0
        try:
            core.check_cancelled(self.cancel_event)
            if self.transcriber is None or self.transcriber.model_size != model:
                self.msg_queue.put(("status", f"Descargando/cargando modelo '{model}' (CPU)..."))
                self.transcriber = core.Transcriber(
                    model_size=model, device=self._device,
                    compute_type=self._compute)
            core.check_cancelled(self.cancel_event)
            total = len(files)
            for idx, path in enumerate(files, 1):
                core.check_cancelled(self.cancel_event)
                name = Path(path).name
                self.msg_queue.put(("file_progress", (idx, total, name, 0.0)))

                def cb(frac, _txt):
                    self.msg_queue.put(("file_progress", (idx, total, name, frac)))

                text, info, segs = self.transcriber.transcribe(
                    path, language=lang, progress_cb=cb,
                    vocab=vocab, cancel_event=self.cancel_event)
                core.check_cancelled(self.cancel_event)
                header = (f"===== {name}  "
                          f"(idioma: {info.language}, "
                          f"{info.language_probability:.0%}) =====\n")
                self.msg_queue.put(("completed_file", (header, text, info.language, segs)))
                completed += 1
                self.msg_queue.put(("file_progress", (idx, total, name, 1.0)))
            self.msg_queue.put(("done", f"Transcripción completada: {completed}/{total} archivos."))
        except core.TranscriptionCancelled:
            self.msg_queue.put(("cancelled", f"Cancelado. Completados: {completed}/{len(files)}. Puedes exportar los resultados terminados."))
        except Exception as exc:
            if self.cancel_event.is_set():
                self.msg_queue.put(("cancelled", f"Cancelado. Completados: {completed}/{len(files)}."))
            else:
                self.msg_queue.put(("error", str(exc)))

    # ---- Traduccion (local con Argos Translate, en hilo) -----------------
    def _start_translate(self):
        if self.busy:
            return
        source = (getattr(self, "last_text", "") or
                  self.result.get("1.0", "end")).strip()
        if not source:
            messagebox.showinfo("Nada que traducir", "Primero transcribe algo.")
            return
        self._open_lang_dialog(source)

    def _open_lang_dialog(self, source):
        """Popup que pide el idioma de destino de una lista."""
        win = ctk.CTkToplevel(self)
        win.title("Traducir")
        win.geometry("380x210")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text="Elige el idioma de destino:",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 6))
        ctk.CTkLabel(
            win, text="La primera vez se descargará ese idioma.",
            text_color="gray70").pack(pady=(0, 8))
        var = ctk.StringVar(value="Español")
        ctk.CTkOptionMenu(win, values=list(trans.TARGET_LANGS.keys()),
                          variable=var, width=220).pack(pady=4)

        def go():
            target_name = var.get()
            win.destroy()
            self._run_translate(source, target_name)

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(pady=16)
        ctk.CTkButton(btns, text="Traducir", command=go, width=110,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#12161E").pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cancelar", command=win.destroy, width=110,
                      fg_color="#262B35", hover_color="#303B4C", text_color=TEXT).pack(side="left", padx=6)

    def _run_translate(self, source, target_name):
        target_code = trans.TARGET_LANGS[target_name]
        from_code = getattr(self, "last_lang", None) or "en"
        self._set_busy("translate")
        threading.Thread(
            target=self._translate_worker,
            args=(source, from_code, target_code, target_name),
            daemon=True).start()

    def _translate_worker(self, source, from_code, target_code, target_name):
        try:
            def st(msg):
                self.msg_queue.put(("status", msg))
            translated = trans.translate(source, from_code, target_code, status=st)
            header = f"\n===== TRADUCCIÓN ({target_name}) =====\n"
            self.msg_queue.put(("append", header + translated + "\n\n"))
            self.msg_queue.put(("tr_done", "Traducción completada."))
        except Exception as e:
            self.msg_queue.put(("tr_error", str(e)))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "status":
                    if not (self._task == "transcribe" and self.cancel_event.is_set()):
                        self.status.configure(text=payload)
                elif kind == "file_progress":
                    if not self.cancel_event.is_set():
                        idx, total, name, frac = payload
                        frac = max(0.0, min(1.0, frac))
                        self.progress.set((idx - 1 + frac) / total)
                        self.status.configure(text=f"{idx}/{total} {name} · {frac:.0%}")
                elif kind == "completed_file":
                    header, text, language, segments = payload
                    self.result.insert("end", header + text + "\n\n")
                    self.result.see("end")
                    self.last_segments.extend(segments)
                    self.last_text += text + "\n\n"
                    if not self.last_lang:
                        self.last_lang = language
                elif kind == "progress":
                    self.progress.set(payload)
                elif kind == "append":
                    self.result.insert("end", payload)
                    self.result.see("end")
                elif kind == "done":
                    self.status.configure(text=payload)
                    self.progress.set(1.0)
                    self._finish()
                elif kind == "cancelled":
                    self.status.configure(text=payload)
                    self._finish()
                elif kind == "error":
                    self.status.configure(text="Error de transcripción. Los archivos terminados se pueden exportar.")
                    messagebox.showerror("Error", payload)
                    self._finish()
                elif kind == "tr_done":
                    self.status.configure(text=payload)
                    self._finish_translate()
                elif kind == "tr_error":
                    self.status.configure(text="Error de traducción")
                    messagebox.showerror("Error de traducción", payload)
                    self._finish_translate()
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _finish(self):
        self._set_busy(None)

    def _finish_translate(self):
        self._set_busy(None)

    # ---- Exportar ---------------------------------------------------------
    def _export(self, fmt):
        if self.busy:
            return
        content = self.result.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Nada que exportar", "Primero transcribe algo.")
            return
        if fmt == "srt":
            data = core.to_srt(self.last_segments)
        elif fmt == "vtt":
            data = core.to_vtt(self.last_segments)
        else:
            data = content
        save_opts = {
            "defaultextension": f".{fmt}",
            "filetypes": [(fmt.upper(), f"*.{fmt}")],
            "initialfile": f"transcripcion.{fmt}",
        }
        start = self._dialog_dir()
        if start:
            save_opts["initialdir"] = start
        try:
            path = filedialog.asksaveasfilename(**save_opts)
        except Exception:
            save_opts.pop("initialdir", None)
            path = filedialog.asksaveasfilename(**save_opts)
        if path:
            try:
                Path(path).write_text(data, encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("No se pudo guardar", str(exc))
                return
            self._last_dir = str(Path(path).resolve().parent)
            self.status.configure(text=f"Guardado: {os.path.basename(path)}")


if __name__ == "__main__":
    App().mainloop()

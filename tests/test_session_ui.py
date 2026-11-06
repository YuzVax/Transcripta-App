"""Regression tests: use a real Tk display; no model downloads or inference.

Run with the bundled Windows python.exe, or Python with the requirements installed:
    python -B tests/test_session_ui.py
"""
import os
import queue
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tkinter import _join

ROOT = Path(__file__).resolve().parents[1]
os.environ["TRANSCRIPTA_CPU_ONLY"] = "1"
sys.path.insert(0, str(ROOT / "src"))
import app
import transcriber as core


class SessionUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.media = self.folder / "audio con tildes á y {llaves}.OPUS"
        self.media.write_bytes(b"test")
        self.window = app.App()
        self.window.update()

    def tearDown(self):
        for event in self.window.tk.call("after", "info"):
            self.window.tk.call("after", "cancel", event)
        self.window.destroy()
        self.temp.cleanup()

    def test_native_dnd_loaded_and_registered(self):
        self.assertTrue(self.window._dnd_available)
        self.assertTrue(self.window.TkdndVersion)
        self.assertTrue(self.window.dnd_bind("<<Drop>>"))
        self.assertTrue(self.window.files_box._textbox.dnd_bind("<<Drop>>"))

    def test_drop_filters_duplicates_unicode_and_directories(self):
        bad = self.folder / "no.txt"
        bad.write_text("x")
        data = _join([str(self.media), str(self.media), str(bad), str(self.folder)])
        result = self.window._drop_files(SimpleNamespace(data=data))
        self.assertEqual(result, "copy")
        self.assertEqual(self.window.files, [str(self.media)])
        self.assertEqual(self.window._last_dir, str(self.folder.resolve()))
        self.assertIn("Omitidos: 2", self.window.status.cget("text"))
        self.assertTrue(self.media.exists())

    def test_add_save_share_last_dir_without_config_write(self):
        with patch.object(app.filedialog, "askopenfilenames", return_value=[str(self.media)]) as add:
            self.window._add_files()
        self.assertEqual(self.window._dialog_dir(), str(self.folder.resolve()))
        self.window.result.insert("end", "Transcripción de prueba")
        destination = self.folder / "exportado"
        destination.mkdir()
        output = destination / "texto.txt"
        with patch.object(app.filedialog, "asksaveasfilename", return_value=str(output)) as save:
            self.window._export("txt")
        self.assertEqual(save.call_args.kwargs["initialdir"], str(self.folder.resolve()))
        self.assertEqual(self.window._last_dir, str(destination.resolve()))
        self.assertEqual(output.read_text(encoding="utf-8"), "Transcripción de prueba")
        with patch.object(app.filedialog, "askopenfilenames", return_value=[]) as add:
            self.window._add_files()
        self.assertEqual(add.call_args.kwargs["initialdir"], str(destination.resolve()))
        self.assertEqual(self.window.config_data, {})

    def test_last_folder_starts_empty_and_missing_folder_falls_back(self):
        self.assertIsNone(self.window._last_dir)
        self.window._last_dir = str(self.folder / "deleted")
        with patch.object(app, "_carpeta_inicial", return_value="REAL_DOCUMENTS"):
            self.assertEqual(self.window._dialog_dir(), "REAL_DOCUMENTS")

    def test_dialog_initialdir_retry_and_cancellation(self):
        self.window._last_dir = str(self.folder)
        with patch.object(app.filedialog, "askopenfilenames", side_effect=[OSError("bad dir"), ()]) as pick:
            self.window._add_files()
        self.assertIn("initialdir", pick.call_args_list[0].kwargs)
        self.assertNotIn("initialdir", pick.call_args_list[1].kwargs)
        self.assertEqual(self.window.files, [])
        self.window.result.insert("end", "text")
        with patch.object(app.filedialog, "asksaveasfilename", side_effect=[OSError("bad dir"), ""]) as save:
            self.window._export("txt")
        self.assertNotIn("initialdir", save.call_args_list[1].kwargs)
        self.assertEqual(self.window._last_dir, str(self.folder))

    def test_busy_controls_and_drop_guard(self):
        self.window._set_busy("transcribe")
        self.assertEqual(self.window.start_btn.cget("state"), "disabled")
        self.assertEqual(self.window.cancel_btn.cget("state"), "normal")
        self.assertEqual(self.window._drop_files(SimpleNamespace(data=str(self.media))), "refuse_drop")
        self.assertEqual(self.window.files, [])
        self.window._cancel()
        self.assertTrue(self.window.cancel_event.is_set())
        self.assertEqual(self.window.cancel_btn.cget("state"), "disabled")
        self.window._finish()
        self.assertFalse(self.window.busy)
        self.assertEqual(self.window.start_btn.cget("state"), "normal")
        self.assertEqual(self.window.start_btn.cget("text"), "Transcribir")
        self.window._set_busy("translate")
        self.assertEqual(self.window.start_btn.cget("state"), "disabled")
        self.assertEqual(self.window.cancel_btn.cget("state"), "disabled")
        self.window._finish_translate()

    def fake_engine(self):
        def transcribe(path, **kwargs):
            kwargs["progress_cb"](0.25, "")
            kwargs["progress_cb"](0.75, "")
            return "texto", SimpleNamespace(language="es", language_probability=1), [(0, 1, "texto")]
        return SimpleNamespace(model_size="base", transcribe=transcribe)

    def test_worker_overall_progress_monotonic_and_results_on_ui_thread(self):
        self.window.transcriber = self.fake_engine()
        self.window._set_busy("transcribe")
        self.window._worker([str(self.media)] * 3, "base", None)
        self.assertEqual(self.window.last_segments, [])  # The worker does not touch UI state.
        progress = []
        real_set = self.window.progress.set
        with patch.object(self.window.progress, "set", side_effect=lambda v: (progress.append(v), real_set(v))):
            self.window._poll_queue()
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[-1], 1)
        self.assertIn(0.75, progress)
        self.assertEqual(len(self.window.last_segments), 3)
        self.assertIn("3/3", self.window.status.cget("text"))
        self.assertFalse(self.window.busy)

    def test_cancel_between_files_preserves_completed_results(self):
        self.window.transcriber = self.fake_engine()
        self.window._set_busy("transcribe")
        real_put = self.window.msg_queue.put
        def cancel_after_first(item):
            real_put(item)
            if item[0] == "completed_file":
                self.window.cancel_event.set()
        with patch.object(self.window.msg_queue, "put", side_effect=cancel_after_first):
            self.window._worker([str(self.media)] * 3, "base", None)
        self.window._poll_queue()
        self.assertEqual(len(self.window.last_segments), 1)
        self.assertIn("Cancelado", self.window.status.cget("text"))
        self.assertIn("1/3", self.window.status.cget("text"))
        self.assertFalse(self.window.busy)

    def test_cancel_before_model_load_does_not_start_download(self):
        self.window.cancel_event.set()
        with patch.object(core, "Transcriber") as engine:
            self.window._worker([str(self.media)], "base", None)
        engine.assert_not_called()
        self.window._poll_queue()
        self.assertIn("Cancelado", self.window.status.cget("text"))

    def test_cancel_during_model_load_stops_before_first_file(self):
        def constructor(**_kwargs):
            self.window.cancel_event.set()
            return self.fake_engine()
        with patch.object(core, "Transcriber", side_effect=constructor):
            self.window._worker([str(self.media)], "base", None)
        self.window._poll_queue()
        self.assertEqual(self.window.last_segments, [])
        self.assertIn("0/1", self.window.status.cget("text"))


    def test_branding_wordmark_and_single_watermark(self):
        self.assertEqual(self.window.title(), app.APP_TITLE)
        self.assertNotIn("by YuzVax", self.window.title())
        self.assertEqual(self.window.title(), "v1.1.5")
        self.assertEqual(len([code for code in app.LANGS.values() if code]), 10)
        self.assertNotIn("zh", app.LANGS.values())
        # The delayed CTk callback must not inject the blue framework icon.
        self.window._windows_set_titlebar_icon()
        self.assertFalse(self.window._iconbitmap_method_called)
        self.assertEqual(app.TITLEBAR, "#1A1F28")
        labels = []
        pending = [self.window]
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            if not isinstance(widget, app.ctk.CTkLabel):
                continue  # CTk's internal Tk label mirrors the wrapper, not another visible signature.
            text = widget.cget("text")
            if text:
                labels.append(text)
        joined = " | ".join(labels)
        self.assertTrue(any(value == "ranscripta" for value in labels), joined)
        self.assertFalse(any(value == "Transcripta" for value in labels), joined)
        self.assertEqual(sum(1 for value in labels if value == "by YuzVax"), 1, joined)

    @unittest.skipUnless(os.name == "nt", "native Windows caption")
    def test_no_titlebar_icon_after_framework_delay(self):
        import ctypes
        from ctypes import wintypes
        self.window.after(450, self.window.quit)
        self.window.mainloop()
        user32, hwnd = self.window._native_window()
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        self.assertEqual(user32.SendMessageW(hwnd, 0x007F, 0, 0), 0)  # WM_GETICON small
        self.assertEqual(user32.SendMessageW(hwnd, 0x007F, 1, 0), 0)  # large
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.assertTrue(user32.GetWindowLongPtrW(hwnd, -20) & 0x1)


class EngineCancelTests(unittest.TestCase):
    def test_pre_cancelled_conversion_never_starts_ffmpeg(self):
        event = threading.Event()
        event.set()
        with patch.object(core.subprocess, "Popen") as popen:
            with self.assertRaises(core.TranscriptionCancelled):
                core.convert_to_wav("no-file", cancel_event=event)
        popen.assert_not_called()

    def test_segment_cancel_closes_generator_and_removes_wav(self):
        event = threading.Event()
        state = {"next": 0, "closed": False}
        def segments():
            try:
                for i in range(3):
                    state["next"] += 1
                    yield SimpleNamespace(start=i, end=i + 1, text="hola")
            finally:
                state["closed"] = True
        with tempfile.TemporaryDirectory() as folder:
            wav = Path(folder) / "audio.wav"
            wav.write_bytes(b"fake")
            engine = object.__new__(core.Transcriber)
            engine.model = SimpleNamespace(transcribe=lambda *_a, **_k: (segments(), SimpleNamespace(duration=3)))
            with patch.object(core, "convert_to_wav", return_value=str(wav)):
                with self.assertRaises(core.TranscriptionCancelled):
                    engine.transcribe("x", progress_cb=lambda *_a: event.set(), cancel_event=event)
            self.assertEqual(state["next"], 1)
            self.assertTrue(state["closed"])
            self.assertFalse(wav.exists())

    def test_conversion_cancel_terminates_process_and_removes_wav(self):
        event = threading.Event()
        started = threading.Event()
        files = []
        real_tmp = core.tempfile.NamedTemporaryFile
        def temporary(**kwargs):
            value = real_tmp(**kwargs)
            files.append(value.name)
            return value
        class Process:
            returncode = None
            terminated = False
            def communicate(self, timeout=None):
                started.set()
                if self.terminated:
                    return None, b""
                event.set()
                raise core.subprocess.TimeoutExpired("ffmpeg", timeout)
            def poll(self):
                return None
            def terminate(self):
                self.terminated = True
        process = Process()
        with patch.object(core, "ffmpeg_path", return_value="ffmpeg"), patch.object(core.subprocess, "Popen", return_value=process), patch.object(core.tempfile, "NamedTemporaryFile", side_effect=temporary):
            with self.assertRaises(core.TranscriptionCancelled):
                core.convert_to_wav("input.opus", cancel_event=event)
        self.assertTrue(started.is_set())
        self.assertTrue(process.terminated)
        self.assertTrue(files)
        self.assertFalse(Path(files[0]).exists())



if __name__ == "__main__":
    unittest.main(verbosity=2)

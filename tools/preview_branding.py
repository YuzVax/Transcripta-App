"""Render the real Windows Tk header and caption with bundled Python (no models)."""
import ctypes
import importlib.util
import os
from pathlib import Path
import sys
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
os.environ["TRANSCRIPTA_ROOT"] = str(ROOT)
os.environ["TRANSCRIPTA_CPU_ONLY"] = "1"
sys.path.insert(0, str(ROOT / "src"))
from ctypes import wintypes
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

for state in ("before", "after"):
    source = ROOT / ("dist/app-before-v1.1.4.py" if state == "before" else "src/app.py")
    spec = importlib.util.spec_from_file_location("preview_app_" + state, source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    if state == "before":
        module.LOGO_PATH = ROOT / "dist/logo-before-v1.1.4.png"
    window = module.App()
    window.geometry("920x740+50+40")
    def save():
        hwnd = user32.GetAncestor(wintypes.HWND(window.winfo_id()), 2)
        rect = wintypes.RECT()
        assert user32.GetWindowRect(hwnd, ctypes.byref(rect))
        screen = ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom))
        screen.save(ROOT / ("dist/ui-" + state + "-v1.1.5.png"))
        screen.crop((0, 0, min(460,screen.width), min(145,screen.height))).save(
            ROOT / ("dist/header-" + state + "-v1.1.5.png"))
        print(state, "window", screen.size, "title", window.title(), flush=True)
        window.quit()
    window.after(700, save)
    window.mainloop()
    for event in window.tk.call("after", "info"):
        window.tk.call("after", "cancel", event)
    window.destroy()

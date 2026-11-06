"""Run with bundled python.exe on Windows or Wine; no model downloads."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

runtime = Path(sys.executable).parent
session = Path(sys.argv[1]).resolve()
session.mkdir(parents=True, exist_ok=True)
for key, sub in {
    'HOME':'home','USERPROFILE':'home','APPDATA':'profile/Roaming','LOCALAPPDATA':'profile/Local',
    'TEMP':'temp','TMP':'temp','XDG_CACHE_HOME':'cache','XDG_DATA_HOME':'data','XDG_CONFIG_HOME':'config',
    'HF_HOME':'cache/huggingface','HF_HUB_CACHE':'cache/huggingface/hub',
    'HUGGINGFACE_HUB_CACHE':'cache/huggingface/hub','HF_XET_CACHE':'cache/huggingface/xet',
    'ARGOS_PACKAGES_DIR':'data/argos-translate/packages','TORCH_HOME':'cache/torch',
    'STANZA_RESOURCES_DIR':'cache/stanza',
}.items():
    directory=session/sub;directory.mkdir(parents=True,exist_ok=True);os.environ[key]=str(directory)
os.environ.update(TRANSCRIPTA_ROOT=str(session),TRANSCRIPTA_CPU_ONLY='1',
                  ARGOS_DEVICE_TYPE='cpu',ARGOS_COMPUTE_TYPE='int8',ARGOS_CHUNK_TYPE='MINISBD',
                  TCL_LIBRARY=str(runtime/'tcl/tcl8.6'),TK_LIBRARY=str(runtime/'tcl/tk8.6'))
sys.path.insert(0,str(runtime.parent/'src'))
handles=[os.add_dll_directory(str(p)) for p in [runtime,runtime/'Lib/site-packages/torch/lib']]
for name in ['tkinter','customtkinter','PIL','numpy','ctranslate2','onnxruntime',
             'faster_whisper','torch','spacy','stanza','argostranslate.settings','argostranslate.translate','app']:
    print('IMPORT',name,flush=True);__import__(name)
import transcriber
assert transcriber.pick_device()==('cpu','int8')
import argostranslate.settings as settings
import tempfile
for path in [settings.data_dir,settings.cache_dir,settings.package_data_dir,Path(tempfile.gettempdir())]:
    assert path.resolve().is_relative_to(session),str(path)
import app
assert app.CREATOR=='YuzVax'
assert app.ROOT_DIR==session
window=app.App()
window.after(800,window.destroy)
window.mainloop()
print('GUI OK',flush=True)
for name in ['ffmpeg.exe','ffprobe.exe']:
    subprocess.run([str(runtime.parent/'ffmpeg/bin'/name),'-version'],stdout=subprocess.DEVNULL,check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
print('NATIVE SMOKE OK',flush=True)

"""Optional Windows/Wine CPU inference test using a pre-downloaded tiny model."""
from pathlib import Path
import os
import runpy
import sys
import wave

smoke=runpy.run_path(str(Path(__file__).with_name('NativeSmoke.py')),run_name='__main__')
session=Path(sys.argv[1]).resolve()
runtime=Path(sys.executable).parent
os.environ['PATH']=str(runtime.parent/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')
source=session/'silence.wav'
with wave.open(str(source),'wb') as f:
    f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\x00\x00'*16000)
import transcriber
wav=transcriber.convert_to_wav(str(source))
from faster_whisper import WhisperModel
model=WhisperModel(str(session/'model'),device='cpu',compute_type='int8',cpu_threads=2,local_files_only=True)
segments,info=model.transcribe(wav,language='en',beam_size=1,vad_filter=False)
print('CPU INFERENCE OK:',len(list(segments)),'segments;',info.language,flush=True)
os.unlink(wav)

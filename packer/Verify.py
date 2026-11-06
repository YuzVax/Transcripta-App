"""Static payload/PE/Windows dependency verification. Run after Build.py."""
from pathlib import Path
import email
import hashlib
import json
import mmap
import sys
import zipfile
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/'packer/build'
lock=json.loads((ROOT/'packer/downloads.lock.json').read_text())
env=default_environment()
env.update(sys_platform='win32',os_name='nt',platform_system='Windows',platform_machine='AMD64',
           platform_python_implementation='CPython',python_version='3.11',python_full_version='3.11.9',extra='')
packages={}
for item in lock:
    if not item['path'].endswith('.whl'):continue
    with zipfile.ZipFile(ROOT/'packer/downloads'/item['path']) as z:
        meta=email.message_from_bytes(z.read(next(n for n in z.namelist() if n.endswith('.dist-info/METADATA'))))
    packages[canonicalize_name(meta['Name'])]=meta
    assert not meta['Requires-Python'] or SpecifierSet(meta['Requires-Python']).contains('3.11.9'),meta['Name']
extras={key:{''} for key in packages}
changed=True
while changed:
    changed=False
    for key,meta in packages.items():
        for text in meta.get_all('Requires-Dist',[]):
            req=Requirement(text)
            if req.marker and not any(req.marker.evaluate(dict(env,extra=extra)) for extra in extras[key]):continue
            name=canonicalize_name(req.name)
            assert name in packages,(key,text)
            assert req.specifier.contains(packages[name]['Version']),(key,text,packages[name]['Version'])
            new=req.extras-extras[name]
            if new:extras[name].update(new);changed=True
print('Windows dependency closure OK:',len(packages),'wheels')
expected={line.split('  ',1)[1]:line[:64] for line in (BUILD/'sha256.txt').read_text().splitlines()}
with zipfile.ZipFile(BUILD/'payload.zip') as z:
    assert len(z.namelist())==len(set(n.lower() for n in z.namelist()))==len(expected)
    for info in z.infolist():
        assert '__pycache__' not in info.filename and '/nvidia/' not in info.filename.lower(),info.filename
        assert not (info.filename.lower().endswith('.dll') and any(n in info.filename.lower() for n in ['cudnn','cublas'])),info.filename
        with z.open(info) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected[info.filename],info.filename
        if info.filename.startswith('src/') or info.filename in ['bootstrap.py','LICENSE','README.md']:
            data=z.read(info)
            assert b'YuzVaxx' not in data and b'Cris.' not in data,info.filename
    assert 'ffmpeg/bin/ffmpeg.exe' in expected and 'ffmpeg/bin/ffprobe.exe' in expected
    assert 'python/_tkinter.pyd' in expected
print('Payload hashes and branding OK:',len(expected),'files')
exe=ROOT/'dist/Transcripta_v2.exe'
with exe.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as image:
    assert image[:2]==b'MZ'
    assert image.find('YuzVax.Transcripta.v1'.encode('utf-16le')) >= 0
    for value in [b'YuzVaxx',b'Cris.','YuzVaxx'.encode('utf-16le'),'Cris.'.encode('utf-16le')]:
        assert image.find(value)==-1,value
    with (BUILD/'payload.zip').open('rb') as payload:
        signature=payload.read(64);offset=image.find(signature);assert offset>0
        length=(BUILD/'payload.zip').stat().st_size
        digest=hashlib.sha256()
        for p in range(offset,offset+length,1048576):digest.update(image[p:min(p+1048576,offset+length)])
        with (BUILD/'payload.zip').open('rb') as source:assert digest.hexdigest()==hashlib.file_digest(source,'sha256').hexdigest()
print('Embedded ZIP matches build payload')
sys.path.insert(0,str(next((ROOT/'packer/downloads/wheels').glob('pefile-*.whl'))))
import pefile
pe=pefile.PE(str(exe),fast_load=True)
assert pe.FILE_HEADER.Machine==0x8664
assert pe.OPTIONAL_HEADER.Subsystem==2
assert pe.OPTIONAL_HEADER.DATA_DIRECTORY[14].VirtualAddress>0
print('Windows PE x64 .NET GUI OK')
print('SIZE_BYTES',exe.stat().st_size)
with exe.open('rb') as f:print('SHA256',hashlib.file_digest(f,'sha256').hexdigest())

#!/usr/bin/env python3
"""Cross-assemble a self-contained Windows x64 EXE on Linux. No Wine required.

Inputs are pinned by URL and SHA256 in downloads.lock.json. Runtime contains
only Windows/universal wheels, official CPython/Tk, and a static FFmpeg build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

PACKER = Path(__file__).resolve().parent
ROOT = PACKER.parent
BUILD = PACKER / "build"
DOWNLOADS = PACKER / "downloads"
TOOLS = PACKER / "tools"
PAYLOAD = BUILD / "payload"


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def fetch_locked():
    lock = json.loads((PACKER / "downloads.lock.json").read_text())
    for item in lock:
        path = DOWNLOADS / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temp = path.with_suffix(path.suffix + ".part")
            print("Download:", item["path"], flush=True)
            urllib.request.urlretrieve(item["url"], temp)
            temp.replace(path)
        if sha(path) != item["sha256"]:
            raise RuntimeError("SHA256 mismatch: " + str(path))
    return lock


def utility(name, rel):
    found = shutil.which(name)
    path = TOOLS / rel
    if found:
        return found
    if not path.exists():
        raise RuntimeError("Install " + name + " (Debian: msitools / 7zip), or place it at " + str(path))
    return str(path)


def extract_msi(source, destination):
    exe = utility("msiextract", "usr/bin/msiextract")
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(TOOLS / "usr/lib/x86_64-linux-gnu") + ":" + env.get("LD_LIBRARY_PATH", "")
    with (BUILD / "msiextract.log").open("a") as log:
        subprocess.run([exe, "-C", str(destination), str(source)], env=env,
                       check=True, stdout=log, stderr=subprocess.STDOUT)


def vcrt():
    destination = BUILD / "vcruntime"
    if not (destination / "System64/msvcp140.dll").exists():
        seven = utility("7z", "usr/lib/7zip/7z")
        data = (DOWNLOADS / "vc_redist.x64.exe").read_bytes()
        start, cabinets = 0, []
        while (start := data.find(b"MSCF", start)) >= 0:
            size = struct.unpack_from("<I", data, start + 8)[0]
            if 36 < size < len(data) - start:
                cabinet = BUILD / ("vc-cab-" + str(len(cabinets)) + ".cab")
                cabinet.write_bytes(data[start:start + size])
                output = BUILD / ("vc-cab-" + str(len(cabinets)))
                subprocess.run([seven, "x", "-y", "-o" + str(output), str(cabinet)],
                               check=True, stdout=subprocess.DEVNULL)
                cabinets.append(output)
            start += 4
        manifest = ET.parse(cabinets[0] / "0").getroot()
        mapped = BUILD / "vcredist-mapped"
        for elem in manifest:
            if elem.tag.endswith("Payload") and "vcRuntime" in elem.attrib.get("FilePath", ""):
                target = mapped / elem.attrib["FilePath"].replace("\\", "/")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cabinets[1] / elem.attrib["SourcePath"], target)
        for source in mapped.rglob("*.msi"):
            extract_msi(source, destination)
    return destination / "System64"


def unpack_wheel(wheel, site):
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError("Invalid wheel entry: " + name)
            if path.parts[0].endswith(".data"):
                if path.parts[1] not in ("purelib", "platlib"):
                    # Entry-point scripts/headers are not needed by this app.
                    continue
                path = PurePosixPath(*path.parts[2:])
            target = site.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)



def strip_payload(site):
    """Drop docs/tests/demos and unused spaCy langs / Chinese extras. Keep Whisper+FFmpeg+CPU."""
    keep_langs = {"es", "en", "it", "pt", "fr", "de", "ru", "xx", "__pycache__"}
    drop_dir_names = {
        "tests", "test", "docs", "doc", "examples", "example",
        "demo", "demos", "samples", "benchmark", "benchmarks", "tutorials",
    }
    # Whole unused packages (Argos uses MINISBD; no runtime need for pypinyin/zh).
    # Keep torchgen: torch.utils._python_dispatch imports it at runtime.
    for name in ("pypinyin", "pypinyin-0.55.0.dist-info"):
        path = site / name
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
    # spaCy language packs outside the supported set.
    lang_root = site / "spacy" / "lang"
    if lang_root.is_dir():
        for child in list(lang_root.iterdir()):
            if child.is_dir() and child.name not in keep_langs and not child.name.startswith("_"):
                shutil.rmtree(child, ignore_errors=True)
    # Nested noise dirs.
    for directory in list(site.rglob("*")):
        if directory.is_dir() and directory.name.lower() in drop_dir_names:
            shutil.rmtree(directory, ignore_errors=True)
    # Cython leftovers / docs beside binaries.
    for pattern in ("*.cpp", "*.pxd", "*.pyx", "*.md", "*.rst", "*.htm", "*.html"):
        for source in list(site.rglob(pattern)):
            # Keep package licenses and top-level notices copied separately.
            if source.name.upper().startswith("LICENSE") or source.name.upper().startswith("COPYING"):
                continue
            if source.suffix.lower() in {".md", ".rst", ".htm", ".html"} and source.parent == site:
                continue
            try:
                source.unlink()
            except OSError:
                pass
    # Names such as torch.testing / numpy.testing are runtime APIs, not test
    # suites. Torch imports torch.testing and torchgen unconditionally; keep them.
    for directory in list(site.rglob("__pycache__")):
        shutil.rmtree(directory, ignore_errors=True)

def assemble(lock):
    if PAYLOAD.exists():
        shutil.rmtree(PAYLOAD)
    runtime = PAYLOAD / "python"
    runtime.mkdir(parents=True)
    with zipfile.ZipFile(DOWNLOADS / "python-3.11.9-embed-amd64.zip") as archive:
        archive.extractall(runtime)
    (runtime / "python311._pth").write_text("python311.zip\n.\nLib\nLib\\site-packages\nimport site\n", encoding="utf-8")
    tk = BUILD / "tcltk"
    if not (tk / "DLLs/_tkinter.pyd").exists():
        extract_msi(DOWNLOADS / "tcltk.msi", tk)
    shutil.copytree(tk / "Lib/tkinter", runtime / "Lib/tkinter")
    shutil.copytree(tk / "tcl", runtime / "tcl")
    for source in (tk / "DLLs").glob("*"):
        shutil.copy2(source, runtime / source.name)
    for source in vcrt().glob("*.dll"):
        if source.name.startswith(("msvcp", "vcruntime", "vcomp", "concrt")):
            shutil.copy2(source, runtime / source.name)
    site = runtime / "Lib/site-packages"
    site.mkdir(parents=True)
    for item in lock:
        if item["path"].endswith(".whl"):
            unpack_wheel(DOWNLOADS / item["path"], site)
    # Solo se distribuye Windows x64 con Tcl/Tk 8.6.
    dnd = site / "tkinterdnd2/tkdnd"
    if dnd.is_dir():
        for directory in dnd.iterdir():
            if directory.is_dir() and directory.name != "win-x64":
                shutil.rmtree(directory)
    # Linker/debug SDK material is not needed for inference (dnnl.lib alone is
    # ~700 MB). Keep all runtime DLLs, Python modules and license metadata.
    for pattern in ("*.lib", "*.pdb", "*.exp"):
        for source in site.rglob(pattern):
            source.unlink()
    for directory in list(site.rglob("__pycache__")):
        shutil.rmtree(directory, ignore_errors=True)
    for source in site.rglob("*.pyc"):
        source.unlink()
    for sub in ("include", "share/cmake"):
        shutil.rmtree(site / "torch" / sub, ignore_errors=True)
    # CTranslate2 can also use CUDA, but this package is deliberately CPU-only.
    for source in site.rglob("cudnn*.dll"):
        source.unlink()
    for source in site.rglob("cublas*.dll"):
        source.unlink()
    strip_payload(site)
    shutil.copytree(ROOT / "src", PAYLOAD / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "assets", PAYLOAD / "assets")
    for name in ("LICENSE", "README.md", "AVISO_SMARTSCREEN.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, PAYLOAD / name)
    shutil.copy2(PACKER / "Bootstrap.py", PAYLOAD / "bootstrap.py")
    with zipfile.ZipFile(DOWNLOADS / "ffmpeg-release-essentials.zip") as archive:
        for name in archive.namelist():
            relative = PurePosixPath(*PurePosixPath(name).parts[1:])
            if str(relative) in ("bin/ffmpeg.exe", "bin/ffprobe.exe", "LICENSE", "README.txt"):
                target = PAYLOAD / "ffmpeg" / str(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
    # Include the Microsoft runtime license, without installing its MSI.
    license_source = BUILD / "vc-cab-0/u4"
    if not license_source.exists():
        license_source = BUILD / "vcredist/u4"
    if license_source.exists():
        shutil.copy2(license_source, PAYLOAD / "Microsoft-Visual-C-Runtime-LICENSE.rtf")


def zip_payload():
    paths = sorted(p for p in PAYLOAD.rglob("*") if p.is_file())
    hashes = []
    with zipfile.ZipFile(BUILD / "payload.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            relative = path.relative_to(PAYLOAD).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            hashes.append(sha(path) + "  " + relative)
            with archive.open(info, "w", force_zip64=True) as target, path.open("rb") as source:
                shutil.copyfileobj(source, target)
    (BUILD / "sha256.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    print("Payload:", len(paths), "files;", (BUILD / "payload.zip").stat().st_size, "bytes", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assemble-only", action="store_true")
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--pwsh", default="")
    parser.add_argument("--reference-dir", default="")
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    if not args.compile_only:
        assemble(fetch_locked())
        if not args.assemble_only:
            zip_payload()
    if not args.assemble_only:
        subprocess.run([args.pwsh, "-NoProfile", "-File", str(PACKER / "Compile.ps1"),
                        "-ReferenceDir", args.reference_dir, "-OutDir", str(ROOT / "dist")], check=True)
        exe = ROOT / "dist/Transcripta_v2.exe"
        subprocess.run([sys.executable, str(PACKER / "VerifyIcon.py"), str(exe)], check=True)
        result = {"path": str(exe), "size_bytes": exe.stat().st_size, "sha256": sha(exe)}
        (ROOT / "dist/build-info.json").write_text(json.dumps(result, indent=2) + "\n")
        (ROOT / "dist/Transcripta_v2.exe.sha256").write_text(result["sha256"] + "  Transcripta_v2.exe\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

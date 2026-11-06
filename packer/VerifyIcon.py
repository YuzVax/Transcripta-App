#!/usr/bin/env python3
"""Reject stale/extra native icons and extract the actual Explorer icon as proof."""
import argparse
import hashlib
from io import BytesIO
from pathlib import Path
import struct
import zipfile

import pefile
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SIZES = {(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)}


def ico_frames(data):
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind, count) == (0, 1, 10), "Expected a 10-frame ICO"
    frames = []
    for index in range(count):
        entry = data[6 + 16 * index:22 + 16 * index]
        length, offset = struct.unpack_from("<II", entry, 8)
        assert offset + length <= len(data), "Truncated ICO"
        frames.append((entry[:12], data[offset:offset + length]))
    return frames


def assert_orange_t(data):
    with Image.open(BytesIO(data)) as image:
        assert image.ico.sizes() == SIZES, "Wrong Explorer icon resolutions"
        for size in SIZES:
            frame = image.ico.getimage(size).convert("RGBA")
            pixels = [frame.getpixel((x, y)) for y in range(frame.height) for x in range(frame.width)]
            color = [p for p in pixels if p[3] > 200 and max(p[:3]) - min(p[:3]) > 30]
            assert color, (size, "Missing colored pixels")
            orange = sum(r > g * 1.1 and g > b * 1.4 and r > 90 for r, g, b, a in color)
            purple = sum(b > g * 1.3 and r > g * 1.3 for r, g, b, a in color)
            assert orange / len(color) > .8, (size, "Icon is not orange")
            assert purple == 0, (size, "Purple microphone pixels detected")


def verify(exe, output=None):
    expected = (ROOT / "assets/logo.ico").read_bytes()
    expected_frames = ico_frames(expected)
    assert_orange_t(expected)
    pe = pefile.PE(str(exe), fast_load=True)
    try:
        pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
        types = {entry.id: entry for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries}
        groups = types[14].directory.entries
        assert len(groups) == 1, "Old/secondary native icon group remains"
        assert groups[0].id == 32512, "Primary icon group differs from OptimiZation"
        group_languages = groups[0].directory.entries
        assert len(group_languages) == 1, "Unexpected duplicate icon languages"
        entry = group_languages[0].data.struct
        group = pe.get_data(entry.OffsetToData, entry.Size)
        assert struct.unpack_from("<HHH", group) == (0, 1, 10), "Wrong primary icon group"
        native = {}
        for name in types[3].directory.entries:
            assert len(name.directory.entries) == 1, "Unexpected duplicate icon languages"
            resource = name.directory.entries[0].data.struct
            native[name.id] = pe.get_data(resource.OffsetToData, resource.Size)
        assert len(native) == 10, "Stale/extra native icon images remain"
        entries, images, used = [], [], set()
        offset = 6 + 16 * len(expected_frames)
        for index, (expected_entry, expected_image) in enumerate(expected_frames):
            group_entry = group[6 + 14 * index:20 + 14 * index]
            icon_id = struct.unpack_from("<H", group_entry, 12)[0]
            assert group_entry[:12] == expected_entry, (icon_id, "Native icon metadata differs")
            assert native[icon_id] == expected_image, (icon_id, "Native icon pixels differ")
            used.add(icon_id)
            entries.append(group_entry[:12] + struct.pack("<I", offset))
            images.append(native[icon_id])
            offset += len(native[icon_id])
        assert used == set(native), "Unreferenced legacy native icon remains"
        extracted = struct.pack("<HHH", 0, 1, 10) + b"".join(entries + images)
        assert extracted == expected, "Extracted icon does not match the approved T"
        assert_orange_t(extracted)
        if output:
            output.mkdir(parents=True, exist_ok=True)
            (output / "extracted-main-icon.ico").write_bytes(extracted)
            with Image.open(BytesIO(extracted)) as image:
                for size in sorted(SIZES):
                    image.ico.getimage(size).save(output / ("pe-icon-%d.png" % size[0]))
        with zipfile.ZipFile(ROOT / "packer/build/payload.zip") as payload:
            assert payload.read("assets/logo.ico") == expected, "Stale payload icon"
            assert not any(Path(n).name.lower() == "mic.ico" for n in payload.namelist()), "mic.ico remains"
        print("PASS: one primary RT_GROUP_ICON 32512, 10/10 orange T frames, byte-identical to assets/logo.ico")
        print("PASS: no extra native icons, no purple pixels, no mic.ico in payload")
        with exe.open("rb") as source:
            print("EXE_SHA256", hashlib.file_digest(source, "sha256").hexdigest())
    finally:
        pe.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path, nargs="?", default=ROOT / "dist/Transcripta_v2.exe")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    verify(args.exe, args.output)

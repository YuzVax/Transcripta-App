"""Source-style and asset identity regression checks; no model or Tk needed."""
import hashlib
from pathlib import Path
import struct
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

class LogoAssetTests(unittest.TestCase):
    def test_original_z_source_is_pinned(self):
        data=(ROOT/"tools/logo-reference/optimization-Z.png").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), "9cd61eacafc4c6830718a17ca88e90c4acf520030c4a7ff0fe21ef90f2a8fe0e")

    def test_actual_top_ribbon_colors_are_preserved(self):
        with Image.open(ROOT/"tools/logo-reference/optimization-Z.png") as z, Image.open(ROOT/"assets/logo.png") as t:
            for xy in [(100,60),(200,60),(60,80),(160,80),(100,70),(220,60)]:
                self.assertEqual(t.getpixel(xy), z.getpixel(xy), xy)
            self.assertEqual(t.mode,"RGBA")
            self.assertEqual(t.size,(256,256))
            self.assertEqual(t.getpixel((0,0))[3],0)
            self.assertGreater(t.getpixel((110,180))[3],220)  # T stem
            self.assertLess(t.getpixel((200,190))[3],30)  # no Z bottom bar

    def test_ico_contains_all_sizes_and_matches_png(self):
        data=(ROOT/"assets/logo.ico").read_bytes()
        self.assertEqual(struct.unpack_from("<HH",data),(0,1))
        with Image.open(ROOT/"assets/logo.ico") as ico, Image.open(ROOT/"assets/logo.png") as png:
            self.assertEqual(ico.ico.sizes(),{(n,n) for n in (16,20,24,32,40,48,64,96,128,256)})
            self.assertEqual(ico.ico.getimage((256,256)).convert("RGBA").tobytes(),png.convert("RGBA").tobytes())

if __name__=="__main__":
    unittest.main(verbosity=2)

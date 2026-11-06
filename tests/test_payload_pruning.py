"""Protect runtime modules from over-aggressive size trimming."""
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packer.Build import strip_payload


class PayloadPruningTests(unittest.TestCase):
    def test_runtime_testing_apis_and_torchgen_survive(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            required = ["torchgen/__init__.py", "torch/testing/__init__.py",
                        "numpy/testing/__init__.py", "torch/bin/torch_shm_manager.exe"]
            for name in required:
                path = site / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("runtime")
            strip_payload(site)
            for name in required:
                self.assertTrue((site / name).exists(), name)

    def test_actual_test_suites_docs_and_unsupported_langs_are_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            removed = ["somepackage/tests/test_one.py", "somepackage/docs/guide.txt",
                       "somepackage/examples/example.py", "spacy/lang/zh/__init__.py"]
            kept = ["spacy/lang/es/__init__.py", "spacy/lang/en/__init__.py",
                    "spacy/lang/ru/__init__.py", "somepackage/LICENSE.md"]
            for name in removed + kept:
                path = site / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("content")
            strip_payload(site)
            for name in removed:
                self.assertFalse((site / name).exists(), name)
            for name in kept:
                self.assertTrue((site / name).exists(), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)

import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("drive_iso",Path(__file__).resolve().parents[1]/"tools"/"download-private-iso.py")
iso=importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)
class HeaderTest(unittest.TestCase):
    def header(self):
        h=bytearray(32);h[:6]=b"RMCP01";h[24:28]=iso.WII_MAGIC;return h
    def test_pal(self):
        iso.verify_header(self.header())
    def test_wrong_region(self):
        h=self.header();h[3]=ord("E")
        with self.assertRaises(ValueError):iso.verify_header(h)
    def test_wrong_magic(self):
        h=self.header();h[24:28]=b"abcd"
        with self.assertRaises(ValueError):iso.verify_header(h)
    def test_truncated(self):
        with self.assertRaises(ValueError):iso.verify_header(b"RMCP01")
    def test_revision(self):
        h=self.header();h[7]=1
        with self.assertRaises(ValueError):iso.verify_header(h)

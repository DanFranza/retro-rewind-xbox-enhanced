import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
pkg=load('prepare-package')

class PackageTest(unittest.TestCase):
    def test_version(self):
        self.assertEqual(pkg.version('1.02.0.0'),'1.2.0.0')
        for bad in ['0.1.0.0','1.0','1.0.0.65536','1.0.0.-1','1.0.x.0']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                pkg.version(bad)

    def test_manifest_stable(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            for sub,ver in [('a','1.1.0.0'),('b','1.2.0.0')]:
                pkg.prepare(ROOT/'package',p/sub,'RetroRewind.Enhanced','CN=RetroRewindEnhanced',ver,'retro')
                for file,size in pkg.TILES.items():
                    data=(p/sub/'Assets'/file).read_bytes()
                    self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
                    self.assertEqual(struct.unpack('>II',data[16:24]),size)
            a,b=[ET.parse(p/x/'Package.appxmanifest').getroot() for x in ['a','b']]
            for attr in ['Name','Publisher']:
                self.assertEqual(a.find(f'{{{pkg.NS}}}Identity').get(attr),b.find(f'{{{pkg.NS}}}Identity').get(attr))
            self.assertEqual(a.find(f'{{{pkg.MP}}}PhoneIdentity').get('PhoneProductId'),b.find(f'{{{pkg.MP}}}PhoneIdentity').get('PhoneProductId'))
            self.assertEqual(b.find(f'{{{pkg.NS}}}Identity').get('Version'),'1.2.0.0')

    def test_reject_bad_identity(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):
                pkg.prepare(ROOT/'package',Path(t)/'a','bad name','CN=Test','1.0.0.0','retro')

class CompileTest(unittest.TestCase):
    def test_empty_database_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t); db=d/'compile_commands.json';db.write_text('[]')
            env=dict(os.environ,MKW_TOOLKIT=t,MKW_UWP_DEP=t,MKW_UWP_SDL=t)
            r=subprocess.run([sys.executable,str(ROOT/'tools/compile-check.py'),str(db),str(d/'out')],env=env,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('No compilation units selected',r.stderr)

    def test_compile_failure_propagates(self):
        # On Linux simulate clang.exe returning nonzero; no game data required.
        if os.name=='nt': self.skipTest('POSIX fake compiler')
        with tempfile.TemporaryDirectory() as t:
            d=Path(t); runtime=d/'runtime';runtime.mkdir()
            source=runtime/'example.cpp';source.write_text('int x;')
            clang=d/'clang.exe';clang.write_text('#!/bin/sh\nexit 1\n');clang.chmod(0o755)
            db=d/'compile_commands.json'
            db.write_text(json.dumps([{'file':str(source),'directory':t,'command':f'clang++ -c "{source}" -o example.o'}]))
            env=dict(os.environ,MKW_TOOLKIT=t,MKW_UWP_DEP=t,MKW_UWP_SDL=t)
            r=subprocess.run([sys.executable,str(ROOT/'tools/compile-check.py'),str(db),str(d/'out'),'--jobs=1'],env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,1,r.stderr)
            report=json.loads((d/'out'/'informe.json').read_text())
            self.assertEqual(report['resumen']['runtime']['fail'],1)

if __name__=='__main__': unittest.main()

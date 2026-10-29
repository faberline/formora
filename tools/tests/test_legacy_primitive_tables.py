import hashlib
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from generate_legacy_primitive_tables import render


class AuthoredSourceTables(unittest.TestCase):
    def test_pinned_author_source_reproduces_the_compiled_tables(self):
        source=(ROOT/'docs/evidence/remaining-primitives/source/bmo_primitive.cc').read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest()
        self.assertEqual(blob,'bc52d28c18b9518442c46518ab67a627b7b8bacf')
        self.assertEqual(render(source),(ROOT/'src/mesh/primitives/legacy_tables.rs').read_text())

    def test_changed_or_measured_input_cannot_replace_the_authored_source(self):
        source=(ROOT/'docs/evidence/remaining-primitives/source/bmo_primitive.cc').read_bytes()
        for wrong in [source+b'\n',source.replace(b'144.72f',b'144.73f',1),b'{"vertices":[]}']:
            with self.assertRaises(AssertionError):render(wrong)


if __name__=='__main__':unittest.main()

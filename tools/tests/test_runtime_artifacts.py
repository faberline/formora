import gzip
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime_artifacts import read_json,write_json


class RuntimeArtifactTests(unittest.TestCase):
    def test_compression_preserves_every_original_json_byte(self):
        data={'unicode':'吸附','position':[-0.0,1.2345678912345,1e-30],'outcome':'ERROR','error':'source rejected'}
        with tempfile.TemporaryDirectory() as temporary:
            raw=write_json(Path(temporary)/'raw.json',data)
            compressed=write_json(Path(temporary)/'compressed.json',data,True)
            self.assertEqual(gzip.decompress(compressed.read_bytes()),raw.read_bytes())
            self.assertEqual(read_json(compressed),data)
            self.assertEqual(read_json(raw),data)
            self.assertEqual(raw.read_bytes(),(json.dumps(data,allow_nan=False)+'\n').encode())

    def test_truncation_and_existing_artifacts_cannot_silently_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'sample.json';compressed=write_json(path,{'sample':1},True)
            with self.assertRaises(FileExistsError):write_json(path,{'sample':2},True)
            broken=Path(temporary)/'broken.json.gz';broken.write_bytes(compressed.read_bytes()[:-3])
            with self.assertRaises((EOFError,OSError)):read_json(broken)

    def test_nonfinite_output_is_rejected_before_a_file_is_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'invalid.json'
            with self.assertRaises(ValueError):write_json(path,{'v':float('nan')},True)
            self.assertEqual(list(Path(temporary).iterdir()),[])

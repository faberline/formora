"""Fail-closed controls against actual fixed native merge captures."""
from collections import Counter
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_mesh_merge_reference import author, compare_case, compare, provenance_inputs


class MergeNativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.folder = cls.root / 'docs/evidence/mesh-merge-baseline'
        cls.suite_path = cls.root / 'baseline/fixtures/mesh-merge.json'
        cls.suite = author(); cls.by_id = {r['id']: r for r in cls.suite['runs']}
        cls.first = cls.folder / 'native-01'; cls.second = cls.folder / 'native-02'
        cls.receipts = cls.folder / 'native-processes.json'

    def load(self, id='merge_0000', pilot=True):
        return json.loads(gzip.decompress(((self.folder / 'pilot-01' if pilot else self.first)
                                           / (id + '.json.gz')).read_bytes()))

    def rejected(self, mutate, id='merge_0000', both=True):
        a = self.load(id); b = copy.deepcopy(a); mutate(b)
        if both: a = copy.deepcopy(b)
        with self.assertRaises((ValueError, KeyError, AssertionError)):
            compare_case(self.suite, self.by_id[id], a, b)

    def test_all_actual_pilot_records(self):
        for id in json.loads((self.folder / 'pilot-cases.json').read_text()):
            v = self.load(id); compare_case(self.suite, self.by_id[id], v, copy.deepcopy(v))

    def test_duplicate_inherited_tags_do_not_drop_vertices(self):
        v = self.load('merge_0008', pilot=False)
        mesh = v['after']['meshes']['target']
        tags = mesh['source_component_ids']['VERT']
        self.assertGreater(Counter(tags.values())[3], 1)
        self.assertEqual(len(tags), len(mesh['geometry']['vertices']))
        self.assertEqual(len(tags), 50)
        compare_case(self.suite, self.by_id['merge_0008'], v, copy.deepcopy(v))

    def test_wrong_merge_position_rejected(self):
        self.rejected(lambda v: v['after']['meshes']['target']['geometry']['vertices']['v000000'].__setitem__(0, 50.))

    def test_wrong_history_endpoint_rejected(self):
        self.rejected(lambda v: v['before']['meshes']['target']['history'].reverse(), id='merge_0480')

    def test_uv_difference_is_compared(self):
        def mutate(v):
            mesh = v['after']['meshes']['target']; layer = next(iter(mesh['geometry']['uv_layers'].values()))
            next(iter(layer.values()))[0][0] += .25
        self.rejected(mutate, both=False)

    def test_zero_weight_is_bound_to_authored_input(self):
        self.rejected(lambda v: v['before']['meshes']['target']['groups']['weights']['v000000'].pop('pin'))

    def test_inactive_uv_layer_is_required(self):
        self.rejected(lambda v: v['after']['meshes']['target']['geometry']['uv_layers'].pop('DetailUV'))

    def test_missing_topology_is_rejected(self):
        self.rejected(lambda v: v['after']['meshes']['target']['geometry']['edges'].pop('e000000'))

    def test_capture_tags_are_compared_separately(self):
        self.rejected(lambda v: v['after']['meshes']['target']['source_component_ids']['VERT'].__setitem__('v000000', 999), both=False)

    def test_false_sharing_is_rejected(self):
        self.rejected(lambda v: v['after'].__setitem__('sharing', [['target'], ['secondary']]))

    def test_unexpected_enum_rejection_is_rejected(self):
        self.rejected(lambda v: v.__setitem__('result', {'status': ['ENUM_REJECTED'], 'error': 'enum unavailable'}))

    def test_same_process_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'same native process'):
            compare(self.suite_path, self.first, self.first, self.receipts)

    def test_missing_case_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest = json.loads((self.first / 'manifest.json').read_text())
            manifest['runs'].pop()
            (folder / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'missing/reordered'):
                compare(self.suite_path, folder, self.second, self.receipts)

    def test_missing_or_failed_terminal_exit_is_rejected(self):
        receipts = json.loads(self.receipts.read_text())
        for bad in [[], [{**receipts['runs'][0], 'terminal_exit_code': 1}]]:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'receipts.json'; path.write_text(json.dumps({'runs': bad}))
                with self.assertRaisesRegex(ValueError, 'terminal exit missing/failed'):
                    compare(self.suite_path, self.first, self.second, path)

    def test_wrong_capture_input_hash_is_rejected(self):
        manifest = json.loads((self.first / 'manifest.json').read_text())
        key = next(k for k in manifest['input_hashes'] if k.endswith('/tools/blender_mesh_merge_reference.py'))
        manifest['input_hashes'][key] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'provenance changed'):
            provenance_inputs(self.first, manifest, self.suite_path)


if __name__ == '__main__':
    unittest.main()

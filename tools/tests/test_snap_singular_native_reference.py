"""Controls against retained actual zero-scale native pilot data."""
import copy
import gzip
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_snap_singular_reference import compare_case, author


class SingularNativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.folder = cls.root / 'docs/evidence/snap-singular-baseline/pilot-01'
        cls.suite = author()
        cls.by_id = {r['id']: r for r in cls.suite['runs']}
        cls.ids = json.loads((cls.folder.parent / 'pilot-cases.json').read_text())

    def load(self, id='singular_snap_0003'):
        return json.loads(gzip.decompress((self.folder / (id + '.json.gz')).read_bytes()))

    def rejected(self, mutate, id='singular_snap_0003'):
        value = self.load(id); mutate(value)
        with self.assertRaises((ValueError, KeyError, AssertionError)):
            compare_case(self.suite, self.by_id[id], value, copy.deepcopy(value))

    def test_actual_native_pilot_all_twenty_one(self):
        for id in self.ids:
            value = self.load(id)
            compare_case(self.suite, self.by_id[id], value, copy.deepcopy(value))

    def test_changed_zero_mask_is_not_accepted(self):
        self.rejected(lambda v: v['before']['objects']['target']['scale'].__setitem__(0, .01))

    def test_raw_inactive_channels_are_bound(self):
        self.rejected(lambda v: v['before']['rotation_channels']['target']['quaternion_wxyz'].__setitem__(0, 2.))

    def test_delta_translation_is_bound(self):
        self.rejected(lambda v: v['before']['delta_channels']['target']['location'].__setitem__(0, 0.))

    def test_zero_local_getter_is_not_replaced_by_basis(self):
        self.rejected(lambda v: v['after']['objects']['child'].__setitem__('matrix_local',
                         v['after']['objects']['child']['matrix_basis']))

    def test_world_matrix_cannot_be_stale(self):
        self.rejected(lambda v: v['after']['objects']['target']['matrix_world'][0].__setitem__(3, 20.))

    def test_world_vertices_cannot_be_changed(self):
        self.rejected(lambda v: v['after']['meshes']['target']['world_vertices']['v000000'].__setitem__(0, 20.))

    def test_real_geometry_attributes_are_bound(self):
        def mutate(v):
            v['before']['meshes']['target']['geometry']['edges'].pop(next(iter(
                v['before']['meshes']['target']['geometry']['edges'])))
        self.rejected(mutate)

    def test_sharing_and_child_identity_are_bound(self):
        self.rejected(lambda v: v['before'].__setitem__('sharing', []))
        self.rejected(lambda v: v['after']['objects'].pop('child'))

    def test_source_error_is_not_numeric_success(self):
        self.rejected(lambda v: v.__setitem__('result', {'status': ['ERROR'], 'error': 'source failed'}))

    def test_cancelled_mutation_is_not_accepted(self):
        self.rejected(lambda v: v.__setitem__('result', {'status': ['CANCELLED'], 'error': None}))

    def test_rank_one_adjugate_blocks_translation_but_rank_two_does_not(self):
        rank_two = self.load('singular_snap_0083')
        before = rank_two['before']['objects']['target']['location']
        after = rank_two['after']['objects']['target']['location']
        self.assertNotEqual(before[0], after[0])
        self.assertEqual(before[1:], after[1:])
        for id in ['singular_snap_0403', 'singular_snap_1043']:
            value = self.load(id)
            self.assertEqual(value['before']['objects']['target']['location'],
                             value['after']['objects']['target']['location'])


if __name__ == '__main__':
    unittest.main()

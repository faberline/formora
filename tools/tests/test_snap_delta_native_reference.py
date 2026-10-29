"""Negative controls using actual native delta source pilot output."""
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_snap_delta_reference import compare_case, provenance_inputs, compare, world_point
from generate_snap_delta_cases import author


class DeltaNativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.folder = cls.root / 'docs/evidence/snap-delta-baseline/pilot-01'
        cls.suite = author()
        cls.case = next(r for r in cls.suite['runs'] if r['id'] == 'delta_snap_0437')
        cls.value = json.loads(gzip.decompress((cls.folder / (cls.case['id'] + '.json.gz')).read_bytes()))

    def rejected(self, edit, both=True):
        a = copy.deepcopy(self.value); b = copy.deepcopy(self.value); edit(b)
        if both:
            a = copy.deepcopy(b)
        with self.assertRaises((ValueError, KeyError, AssertionError)):
            compare_case(self.suite, self.case, a, b)

    def test_actual_pilot(self):
        compare_case(self.suite, self.case, self.value, self.value)

    def test_sequential_native_halfway_rounding(self):
        matrix = [[-1.2999999523162842, 1.77635686587003e-16, 1.4432898790731443e-16, -1.0625],
            [-2.8865797581462886e-16, -.800000011920929, 1.4432898790731443e-16, .125],
            [-2.8865797581462886e-16, 1.77635686587003e-16, .6499999761581421, .125], [0.,0.,0.,1.]]
        point = [.4999999701976776, -.5000000596046448, .5000000596046448]
        self.assertEqual(world_point(matrix, point), [-1.7124998569488525, .5250000357627869, .45000001788139343])

    def test_missing_delta_translation(self):
        self.rejected(lambda v: v['before']['delta_channels']['target'].update(location=[0.]*3))

    def test_wrong_delta_scale(self):
        self.rejected(lambda v: v['before']['delta_channels']['target']['scale'].__setitem__(0, -1.2))

    def test_stored_delta_sign_is_not_folded(self):
        def edit(v):
            for state in ['before','after']:
                q = v[state]['delta_channels']['target']['quaternion_wxyz']
                v[state]['delta_channels']['target']['quaternion_wxyz'] = [-x for x in q]
                v[state]['rotation_channels']['target']['delta_quaternion_wxyz'] = [-x for x in q]
        self.rejected(edit)

    def test_stored_delta_normalization_is_not_allowed(self):
        def edit(v):
            q = v['before']['delta_channels']['target']['quaternion_wxyz']
            v['before']['delta_channels']['target']['quaternion_wxyz'] = [x/2 for x in q]
            v['before']['rotation_channels']['target']['delta_quaternion_wxyz'] = [x/2 for x in q]
        self.rejected(edit)

    def test_altered_inactive_delta_euler(self):
        self.rejected(lambda v: v['before']['delta_channels']['target']['euler'].__setitem__(0, .123))

    def test_operation_cannot_change_delta(self):
        self.rejected(lambda v: v['after']['delta_channels']['target']['location'].__setitem__(0, .25))

    def test_delta_multiplication_cannot_be_reversed(self):
        def edit(v):
            from compare_snap_rotation_reference import rotation_matrix
            from compare_snap_menu_reference import f32
            r = rotation_matrix(self.case['rotations']['objects'])
            d = rotation_matrix({'mode':'QUATERNION', 'euler':self.case['deltas']['euler'],
                'quaternion_wxyz':self.case['deltas']['quaternion_wxyz'], 'axis_angle':[0.,0.,1.,0.]})
            m = v['before']['objects']['target']['matrix_basis']
            p = self.suite['profiles'][self.case['context']['profile']]
            for i in range(3):
                for j in range(3):
                    m[i][j] = f32(sum(r[i][k]*d[k][j] for k in range(3)) * f32(f32(p['scale'][j])*f32(self.case['deltas']['scale'][j])))
        self.rejected(edit)

    def test_wrong_world_matrix(self):
        self.rejected(lambda v: v['after']['objects']['target']['matrix_world'][0].__setitem__(3, 99.))

    def test_wrong_lock(self):
        self.rejected(lambda v: v['before']['objects']['target']['lock_location'].__setitem__(0, True))

    def test_false_sharing(self):
        self.rejected(lambda v: v['before'].update(sharing=[['target'], ['secondary']]))

    def test_wrong_geometry(self):
        self.rejected(lambda v: v['before']['meshes']['target']['geometry']['vertices']['v000000'].__setitem__(0, 99.))

    def test_wrong_uv(self):
        def edit(v):
            layers=v['before']['meshes']['target']['geometry']['uv_layers']
            next(iter(next(iter(layers.values())).values()))[0][0]=99.
        self.rejected(edit)

    def test_request_cannot_read_source_answers(self):
        self.rejected(lambda v: v['run']['deltas']['scale'].__setitem__(0, 99.))

    def test_source_error_cannot_pass(self):
        self.rejected(lambda v: v.update(result={'status':['ERROR'], 'error':'failure'}))

    def test_missing_delta_field(self):
        self.rejected(lambda v: v['after']['delta_channels']['target'].pop('scale'))

    def test_nonfinite(self):
        self.rejected(lambda v: v['after']['delta_channels']['target']['euler'].__setitem__(0, float('nan')))

    def test_changed_capture_program_hash(self):
        manifest = json.loads((self.folder/'manifest.json').read_text())
        path = str(self.root/'tools/blender_snap_delta_reference.py')
        manifest['input_hashes'][path] = '0'*64
        with self.assertRaisesRegex(ValueError, 'capture provenance changed'):
            provenance_inputs(self.folder, manifest, self.root/'baseline/fixtures/snap-delta.json')

    def test_same_native_process_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, 'same native process'):
            compare(self.root/'baseline/fixtures/snap-delta.json', self.folder, self.folder,
                    self.root/'unused-receipts.json')

    def test_pilot_cannot_pass_complete_gate(self):
        a = json.loads((self.folder/'manifest.json').read_text()); b = copy.deepcopy(a)
        b['process_id'] += 1
        with tempfile.TemporaryDirectory() as temporary:
            x, y = Path(temporary)/'a', Path(temporary)/'b'; x.mkdir(); y.mkdir()
            for folder, value in [(x,a),(y,b)]:
                (folder/'manifest.json').write_text(json.dumps(value))
            receipt = Path(temporary)/'receipts.json'; receipt.write_text('{"runs":[]}')
            with self.assertRaisesRegex(ValueError, 'incomplete/native mode differs'):
                compare(self.root/'baseline/fixtures/snap-delta.json', x, y, receipt)

    def test_missing_full_source_case_cannot_pass(self):
        first = self.root/'baseline/reference/blender-5.2.3/snap-delta'
        second = self.root/'baseline/reference/blender-5.2.3/snap-delta-repeat'
        a = json.loads((first/'manifest.json').read_text())
        b = json.loads((second/'manifest.json').read_text())
        a['runs'].pop()
        with tempfile.TemporaryDirectory() as temporary:
            x, y = Path(temporary)/'a', Path(temporary)/'b'; x.mkdir(); y.mkdir()
            for folder, value in [(x,a),(y,b)]:
                (folder/'manifest.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'missing/reordered source case'):
                compare(self.root/'baseline/fixtures/snap-delta.json', x, y,
                    self.root/'docs/evidence/snap-delta-baseline/native-processes.json')


if __name__ == '__main__':
    unittest.main()

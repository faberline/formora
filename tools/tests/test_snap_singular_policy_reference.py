"""Protect the precise approved unavailable-local-query exception."""
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_snap_singular_policy_reference import author, compare_case, compare, validate_capture


class SingularPolicyControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.folder = cls.root / 'docs/evidence/snap-singular-baseline'
        cls.first = cls.folder / 'diagnostic-01'
        cls.second = cls.folder / 'diagnostic-02'
        cls.suite_path = cls.root / 'baseline/fixtures/snap-singular.json'
        cls.suite = author(); cls.runs = {r['id']: r for r in cls.suite['runs']}
        cls.receipts = cls.folder / 'native-processes.json'

    def load(self, id='singular_snap_0581'):
        return json.loads(gzip.decompress((self.first / (id + '.json.gz')).read_bytes()))

    def rejected(self, mutate, id='singular_snap_0581'):
        value = self.load(id); mutate(value)
        with self.assertRaises((ValueError, KeyError, TypeError, AssertionError)):
            compare_case(self.suite, self.runs[id], value, copy.deepcopy(value))

    def test_approved_query_error_is_separate_from_seven_numeric_getters(self):
        value = self.load()
        counts, tags = compare_case(self.suite, self.runs[value['run']['id']], value, copy.deepcopy(value))
        self.assertEqual(counts['unavailable_local_queries'], 1)
        self.assertEqual(counts['available_numeric_local_queries'], 7)
        self.assertEqual(len(tags), 16)

    def test_finite_zero_getters_keep_their_original_numeric_checks(self):
        value = self.load('singular_snap_0003')
        counts, tags = compare_case(self.suite, self.runs[value['run']['id']], value, copy.deepcopy(value))
        self.assertEqual(counts['unavailable_local_queries'], 0)
        self.assertEqual(counts['available_numeric_local_queries'], 6)
        self.assertEqual(tags, [])

    def test_fake_numeric_zero_is_not_an_unavailable_result(self):
        self.rejected(lambda v: v['after']['objects']['child'].__setitem__('matrix_local', [[0.] * 4 for _ in range(4)]))

    def test_wrong_nan_bits_are_not_accepted(self):
        self.rejected(lambda v: v['after']['objects']['child']['matrix_local'][0][0]
                      ['__source_nonfinite_diagnostic__'].__setitem__('f32_little_endian_hex', '0000807f'))

    def test_wrong_path_is_not_accepted(self):
        self.rejected(lambda v: v['after']['objects']['child']['matrix_local'][0][0]
                      ['__source_nonfinite_diagnostic__'].__setitem__('path', '/after/objects/target/matrix_local/0/0'))

    def test_no_additional_query_or_case_is_excused(self):
        def mutate(v):
            v['before']['objects']['child']['matrix_local'][0][0] = copy.deepcopy(
                v['after']['objects']['child']['matrix_local'][0][0])
        self.rejected(mutate)
        def mutate_regular(v):
            v['after']['objects']['child']['matrix_local'][0][0] = copy.deepcopy(
                self.load()['after']['objects']['child']['matrix_local'][0][0])
        self.rejected(mutate_regular, 'singular_snap_0003')

    def test_valid_world_result_is_still_independently_required(self):
        self.rejected(lambda v: v['after']['objects']['child']['matrix_world'][0].__setitem__(3, 50.))

    def test_geometry_change_cannot_hide_behind_local_query_error(self):
        self.rejected(lambda v: v['after']['meshes']['target']['geometry']['vertices']['v000000'].__setitem__(0, 50.))

    def test_whole_operation_rejection_does_not_satisfy_policy(self):
        self.rejected(lambda v: v.__setitem__('result', {'status': ['ERROR'], 'error': 'cannot invert'}))

    def test_available_matrix_cells_must_be_numeric(self):
        self.rejected(lambda v: v['after']['objects']['target']['matrix_local'][0].__setitem__(0, False))

    def test_unapproved_input_witness_is_rejected(self):
        value = self.load(); run = copy.deepcopy(self.runs[value['run']['id']])
        run['parameters']['use_rotation'] = False; value['run'] = run
        with self.assertRaisesRegex(ValueError, 'input witness'):
            compare_case(self.suite, run, value, copy.deepcopy(value))

    def test_same_process_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'same native process'):
            compare(self.suite_path, self.first, self.first, self.receipts)

    def test_missing_case_is_rejected(self):
        manifest = json.loads((self.first / 'manifest.json').read_text())
        manifest['runs'].pop()
        with self.assertRaisesRegex(ValueError, 'missing/reordered'):
            validate_capture(self.first, manifest, self.suite_path, [])

    def test_missing_or_failed_terminal_exit_is_rejected(self):
        manifest = json.loads((self.first / 'manifest.json').read_text())
        receipts = json.loads(self.receipts.read_text())['runs']
        row = next(r for r in receipts if r['process_id'] == manifest['process_id'])
        for rows in [[], [{**row, 'terminal_exit_code': 1}]]:
            with self.assertRaisesRegex(ValueError, 'terminal exit missing/failed'):
                validate_capture(self.first, manifest, self.suite_path, rows)


if __name__ == '__main__':
    unittest.main()

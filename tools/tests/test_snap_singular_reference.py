"""Before-capture controls for the exact-zero authored domain."""
from collections import Counter
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_snap_delta_reference import delta_matrix
from compare_snap_singular_reference import check_local, zero_column
from generate_snap_singular_cases import author, effective_suite, FORMS_ALL
from generate_snap_rotation_cases import MODES, channels
from generate_snap_delta_cases import delta


class SingularPreparationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = author()

    def test_complete_authored_domain(self):
        suite = self.suite
        self.assertEqual(len(suite['runs']), 1764)
        self.assertEqual(len({r['id'] for r in suite['runs']}), 1764)
        self.assertEqual(Counter(r['label'] for r in suite['runs']), suite['groups_expected'])
        normal = [r for r in suite['runs'] if r['label'] == 'normal_scale']
        self.assertEqual({r['operator'] for r in normal}, {x[0] for x in FORMS_ALL})
        self.assertEqual({r['rotations']['objects']['mode'] for r in normal}, set(MODES))
        self.assertEqual(Counter((r['zero_scale']['role'], r['zero_scale']['mask'])
                                 for r in normal), Counter({(a, b): 80
                                 for a in ['target', 'parent'] for b in range(1, 8)}))

    def test_each_mask_has_exact_zero_components(self):
        for run in self.suite['runs']:
            z = run['zero_scale']; p = self.suite['profiles'][run['context']['profile']]
            if z['channel'] == 'normal':
                scale = (p if z['role'] == 'target' else p['parent'])['scale']
            else:
                scale = (run['deltas'] if z['role'] == 'target'
                         else run['role_deltas']['parent'])['scale']
            self.assertEqual([i for i, v in enumerate(scale) if v == 0.],
                             [i for i in range(3) if z['mask'] & (1 << i)])

    def test_zero_scale_world_basis_is_not_rejected(self):
        for mode in MODES:
            for mask in range(1, 8):
                scale = [0. if mask & (1 << i) else 1. for i in range(3)]
                m = delta_matrix({'location': [1., 2., 3.], 'scale': scale},
                                 channels(mode), delta('combined'))
                for axis in range(3):
                    if mask & (1 << axis):
                        self.assertTrue(all(m[row][axis] == 0. for row in range(3)))

    def test_local_getter_zero_inverse_is_not_basis(self):
        run = self.suite['runs'][0]
        basis = [[float(i == j) for j in range(4)] for i in range(4)]
        singular = copy.deepcopy(basis); singular[0][0] = 0.
        state = {'objects': {'target': {'parent': 'parent', 'matrix_local': [[0.] * 4 for _ in range(4)]},
                             'parent': {'parent': None, 'matrix_world': singular}}}
        check_local(self.suite, run, 'target', state, basis)
        state['objects']['target']['matrix_local'] = basis
        with self.assertRaises(ValueError):
            check_local(self.suite, run, 'target', state, basis)

    def test_no_near_zero_determinant_threshold(self):
        matrix = [[float(i == j) for j in range(4)] for i in range(4)]
        matrix[0][0] = 1e-30
        self.assertFalse(zero_column(matrix))
        matrix[0][0] = 0.
        self.assertTrue(zero_column(matrix))

    def test_per_case_role_deltas_do_not_mutate_shared_inputs(self):
        run = next(r for r in self.suite['runs'] if r['label'] == 'delta_scale'
                   and r['zero_scale']['role'] == 'parent')
        before = copy.deepcopy(self.suite['role_deltas'])
        value = effective_suite(self.suite, run)
        self.assertEqual(value['role_deltas'], run['role_deltas'])
        value['role_deltas']['parent']['scale'][0] = 99.
        self.assertEqual(self.suite['role_deltas'], before)
        self.assertEqual(run['role_deltas']['parent']['scale'][0], 0.)


if __name__ == '__main__':
    unittest.main()

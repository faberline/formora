"""Before-capture analytic controls for authored native merge inputs."""
from collections import Counter
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_mesh_merge_reference import expected_positions, inverse_affine, match_positions
from compare_snap_menu_reference import tree
from compare_snap_delta_reference import world_point
from generate_mesh_merge_cases import author, METHODS


class MergePreparationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = author()

    def test_authored_cases_and_all_selection_masks(self):
        suite = self.suite
        self.assertEqual(len(suite['runs']), 1024)
        self.assertEqual(len({r['id'] for r in suite['runs']}), 1024)
        self.assertEqual(Counter(r['label'] for r in suite['runs']), suite['groups_expected'])
        self.assertEqual({r['parameters']['type'] for r in suite['runs']}, set(METHODS))
        self.assertEqual(len({tuple(r['initial_mode']) for r in suite['runs']}), 7)
        self.assertTrue(all(0 not in p['scale'] for p in suite['profiles'].values()))

    def test_history_orders_are_authored_before_capture(self):
        a, b = self.suite['runs'][:2]
        self.assertEqual(a['seed']['indices'], list(reversed(b['seed']['indices'])))
        self.assertEqual(a['context'], b['context'])
        self.assertEqual(a['parameters'], b['parameters'])

    def test_source_geometry_and_inactive_uv_layer_are_present(self):
        mesh = self.suite['mesh']
        self.assertEqual(len(mesh['vertices']), 52)
        self.assertEqual(len(mesh['faces']), 34)
        self.assertEqual([v['name'] for v in mesh['uv_layers']], ['UVMap', 'DetailUV'])
        self.assertTrue(mesh['hidden']['vertices'])
        self.assertEqual(mesh['group_scenarios']['authored']['weights']['v000000']['pin'], 0.)

    def example(self, method):
        vertices = {'v000000': [0., 0., 0.], 'v000001': [2., 0., 0.],
                    'v000002': [10., 0., 0.], 'v000003': [14., 0., 0.],
                    'v000004': [20., 1., 0.]}
        mesh = {'geometry': {'vertices': vertices,
                            'edges': {'e000000': ['v000000', 'v000001'],
                                      'e000001': ['v000002', 'v000003']}},
                'selected': {'VERT': list(vertices)[:4], 'EDGE': ['e000000', 'e000001']},
                'history': [{'domain': 'VERT', 'id': 'v000003'},
                            {'domain': 'VERT', 'id': 'v000000'}]}
        state = {'meshes': {'target': mesh}, 'objects': {'target': {'matrix_world':
                 [[1., 0., 0., 1.], [0., 1., 0., 2.], [0., 0., 1., 3.], [0., 0., 0., 1.]]}},
                 'cursor': {'location': [4., 6., 8.]}}
        return {'parameters': {'type': method}}, state

    def test_center_is_vertex_mean_and_preserves_unselected_point(self):
        run, state = self.example('CENTER')
        match_positions([[6.5, 0., 0.], [20., 1., 0.]], expected_positions(run, state))

    def test_cursor_uses_local_coordinates(self):
        run, state = self.example('CURSOR')
        match_positions([[3., 4., 5.], [20., 1., 0.]], expected_positions(run, state))

    def test_first_and_last_follow_history_not_native_order(self):
        for method, expected in [('FIRST', [14., 0., 0.]), ('LAST', [0., 0., 0.])]:
            run, state = self.example(method)
            match_positions([expected, [20., 1., 0.]], expected_positions(run, state))

    def test_collapse_keeps_disconnected_components_separate(self):
        run, state = self.example('COLLAPSE')
        match_positions([[1., 0., 0.], [12., 0., 0.], [20., 1., 0.]], expected_positions(run, state))
        with self.assertRaises(ValueError):
            match_positions([[6.5, 0., 0.], [20., 1., 0.]], expected_positions(run, state))

    def test_analytic_inverse_handles_reflection_and_quarter_turn(self):
        matrix = [[0., -2., 0., 1.], [-3., 0., 0., 2.],
                  [0., 0., 4., 3.], [0., 0., 0., 1.]]
        original = copy.deepcopy(matrix)
        tree([2., 3., 4.], world_point(inverse_affine(matrix), [-5., -4., 19.]))
        self.assertEqual(matrix, original)


if __name__ == '__main__':
    unittest.main()

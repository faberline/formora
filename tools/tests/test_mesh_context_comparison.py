import copy
import hashlib
import json
from pathlib import Path
import unittest
from test_mesh_comparison import comparison, renumber

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT/'baseline/reference/blender-5.2.3/mesh-contexts'
SUITE = ROOT/'baseline/fixtures/mesh-creation-contexts.json'
LIMITS = json.loads(SUITE.read_bytes())['comparison']


def load(name):
    return json.loads((DATA/(name+'.json')).read_bytes())


class ContextComparisonTests(unittest.TestCase):
    def test_incident_uv_matching_is_injective_and_tolerant_without_sort_order(self):
        actual = [(3, [0.0, 0.9e-6]), (3, [0.9e-6, 0.0])]
        expected = [(3, [0.0, 0.0]), (3, [0.9e-6, 1.8e-6])]
        self.assertTrue(comparison.uv_signatures_match(actual, expected, 1e-6))
        self.assertFalse(comparison.uv_signatures_match(
            [(3, [0.0, 0.0]), (3, [0.0, 0.0])],
            [(3, [0.0, 0.0]), (3, [3e-6, 0.0])], 1e-6))

    def test_context_capture_binds_inputs_and_the_unchanged_first_adapter(self):
        suite = json.loads(SUITE.read_bytes())
        manifest = json.loads((DATA/'manifest.json').read_bytes())
        self.assertEqual(manifest['suite_sha256'], hashlib.sha256(SUITE.read_bytes()).hexdigest())
        for field, file in [('adapter_sha256', 'blender_mesh_context_reference.py'),
                            ('base_adapter_sha256', 'blender_mesh_reference.py')]:
            self.assertEqual(manifest[field], hashlib.sha256((ROOT/'tools'/file).read_bytes()).hexdigest())
        self.assertEqual([r['id'] for r in manifest['runs']], [r['id'] for r in suite['runs']])
        for record in manifest['runs']:
            path = DATA/record['file']
            self.assertEqual(record['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            mesh = json.loads(path.read_bytes())
            self.assertEqual(mesh['run_id'], record['id'])
            for count, field in [('vertex_count', 'vertices'), ('edge_count', 'edges'),
                                 ('face_count', 'faces'), ('uv_layer_count', 'uv_layers')]:
                self.assertEqual(record[count], len(mesh[field]))
        for run in suite['runs']:
            expected = 'EDIT' if run['state']['creation_kind'] == 'append_mesh' or run['parameters'].get('enter_editmode') else 'OBJECT'
            self.assertEqual(load(run['id'])['reference_mode_after'], expected)
        self.assertEqual(manifest['formora_execution'], 'unrun')
        self.assertEqual(manifest['product_acceptance'], 'unrun')

    def test_context_attributes_survive_consistent_renumbering(self):
        source = load('cube_append_uv2_1')
        self.assertTrue(comparison.compare(source, renumber(source), LIMITS)['creation_attributes_match_reference'])

    def test_reference_modes_are_verified_without_requiring_a_legacy_product_gui(self):
        source = load('cube_append_uv2_1')
        changed = copy.deepcopy(source)
        changed['reference_mode_after'] = 'OBJECT'
        with self.assertRaisesRegex(comparison.Mismatch, 'reference_mode_after'):
            comparison.compare(source, changed, LIMITS, upstream_repeat=True)
        self.assertTrue(comparison.compare(source, changed, LIMITS)['creation_attributes_match_reference'])

    def test_active_uv_layer_change_is_not_hidden_by_identical_geometry(self):
        source = load('cube_append_uv2_1')
        changed = copy.deepcopy(source)
        changed['active_uv_index'] = 0
        with self.assertRaisesRegex(comparison.Mismatch, 'active_uv_index'):
            comparison.compare(source, changed, LIMITS)

    def test_material_and_selection_changes_are_rejected(self):
        source = load('cube_append_uv2_1')
        for field in ['face_materials', 'vertex_selected', 'edge_selected', 'face_selected']:
            with self.subTest(field=field):
                changed = copy.deepcopy(source)
                changed[field][0] = 1-source[field][0] if field == 'face_materials' else not source[field][0]
                with self.assertRaises(comparison.Mismatch):
                    comparison.compare(source, changed, LIMITS)

    def test_existing_components_cannot_be_relabelled_as_created(self):
        source = load('cube_append_uv2_1')
        for field in ['vertex_origin', 'edge_origin', 'face_origin']:
            with self.subTest(field=field):
                changed = copy.deepcopy(source)
                changed[field][0] = 'created'
                with self.assertRaises(comparison.Mismatch):
                    comparison.compare(source, changed, LIMITS)

    def test_explicit_seed_fixture_matches_all_preserved_insertions(self):
        seed = json.loads((ROOT/'baseline/fixtures/mesh-creation-seed.json').read_bytes())
        suite = json.loads(SUITE.read_bytes())
        for run in suite['runs']:
            if run['state']['creation_kind'] != 'append_mesh':
                continue
            mesh = load(run['id'])
            with self.subTest(run=run['id']):
                self.assertEqual(mesh['matrix_world'], seed['matrix_world'])
                self.assertEqual(mesh['material_slots'], seed['material_slots'])
                for field, original in seed['geometry'].items():
                    self.assertEqual(mesh[field][:len(original)], original)
                profile = seed['uv_profiles'][str(run['state']['seed_uv_layers'])]
                for i, layer in enumerate(profile['uv_layers']):
                    self.assertEqual(mesh['uv_layers'][i]['name'], layer['name'])
                    self.assertEqual(mesh['uv_layers'][i]['faces'][:6], layer['faces'])

    def test_material_slot_bindings_are_checked_beyond_face_indices(self):
        source = load('cube_append_uv2_1')
        changed = copy.deepcopy(source)
        changed['material_slots'].reverse()
        with self.assertRaisesRegex(comparison.Mismatch, 'material_slots'):
            comparison.compare(source, changed, LIMITS)
        changed = copy.deepcopy(source)
        changed['active_material_index'] = 0
        with self.assertRaisesRegex(comparison.Mismatch, 'active_material_index'):
            comparison.compare(source, changed, LIMITS)

    def test_upstream_nan_reproduction_is_not_finite_candidate_conformance(self):
        source = load('circle_zero_ngon')
        result = comparison.compare(source, source, LIMITS, upstream_repeat=True)
        self.assertEqual(result['undefined_reference_uv_components'], 14)
        self.assertEqual(result['compared_finite_uv_components'], 0)
        self.assertIsNone(result['maximum_face_corner_uv_error'])
        self.assertFalse(result['undefined_uv_fallback_verified'])
        with self.assertRaisesRegex(comparison.Mismatch, 'finite zero fallback'):
            comparison.compare(source, source, LIMITS)

    def test_undefined_uv_fallback_requires_zero_and_an_explicit_diagnostic(self):
        source = load('circle_zero_ngon')
        changed = copy.deepcopy(source)
        for layer in changed['uv_layers']:
            for face in layer['faces']:
                for corner in face:
                    corner[:] = [0.0, 0.0]
        changed['diagnostics'] = ['degenerate_default_uv']
        result = comparison.compare(source, changed, LIMITS)
        self.assertEqual(result['undefined_reference_uv_components'], 14)
        self.assertTrue(result['undefined_uv_fallback_verified'])
        del changed['diagnostics']
        with self.assertRaisesRegex(comparison.Mismatch, 'requires a diagnostic'):
            comparison.compare(source, changed, LIMITS)
        changed['diagnostics'] = ['degenerate_default_uv']
        changed['uv_layers'][0]['faces'][0][0][0] = 0.25
        with self.assertRaisesRegex(comparison.Mismatch, 'finite zero fallback'):
            comparison.compare(source, changed, LIMITS)

    def test_undefined_uv_policy_cannot_cover_unlisted_inputs(self):
        source = load('circle_zero_ngon')
        source['run_id'] = 'unlisted_case'
        with self.assertRaisesRegex(comparison.Mismatch, 'no fixed policy'):
            comparison.compare(source, source, LIMITS, upstream_repeat=True)

    def test_zero_size_meshes_can_be_renumbered_without_welding_vertices(self):
        for name in ['cube_zero_size', 'monkey_zero_size']:
            with self.subTest(name=name):
                source = load(name)
                self.assertTrue(comparison.compare(source, renumber(source), LIMITS)['oriented_topology_matches_reference'])


if __name__ == '__main__':
    unittest.main()

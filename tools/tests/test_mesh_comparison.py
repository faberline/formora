import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('mesh_comparison', ROOT/'tools/compare_mesh_reference.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
DATA = ROOT/'baseline/reference/blender-5.2.3/mesh-primitives'
LIMITS = json.loads((ROOT/'baseline/fixtures/mesh-primitives.json').read_text())['comparison']


def load(name):
    return json.loads((DATA/(name+'.json')).read_text())


def renumber(mesh):
    result = copy.deepcopy(mesh)
    n = len(mesh['vertices'])
    result['vertices'] = list(reversed(mesh['vertices']))
    result['edges'] = [[n-1-v for v in reversed(edge)] for edge in reversed(mesh['edges'])]
    result['faces'] = []
    result['face_normals'] = []
    result['corner_normals'] = []
    result['smooth_faces'] = []
    result['uv_layers'] = [{'name': l['name'], 'faces': []} for l in mesh['uv_layers']]
    starts = []
    offset = 0
    for face in mesh['faces']:
        starts.append(offset)
        offset += len(face)
    for i in reversed(range(len(mesh['faces']))):
        face = mesh['faces'][i]
        result['faces'].append(comparison.rotate([n-1-v for v in face], 1))
        result['face_normals'].append(mesh['face_normals'][i])
        result['smooth_faces'].append(mesh['smooth_faces'][i])
        corners = mesh['corner_normals'][starts[i]:starts[i]+len(face)]
        result['corner_normals'].extend(comparison.rotate(corners, 1))
        for a, b in zip(result['uv_layers'], mesh['uv_layers']):
            a['faces'].append(comparison.rotate(b['faces'][i], 1))
    return result


class ComparisonTests(unittest.TestCase):
    def test_capture_binds_every_mesh_to_the_frozen_input_and_adapter(self):
        suite_path = ROOT/'baseline/fixtures/mesh-primitives.json'
        suite = json.loads(suite_path.read_text())
        manifest = json.loads((DATA/'manifest.json').read_text())
        self.assertEqual(manifest['suite_sha256'], hashlib.sha256(suite_path.read_bytes()).hexdigest())
        self.assertEqual(manifest['adapter_sha256'], hashlib.sha256((ROOT/'tools/blender_mesh_reference.py').read_bytes()).hexdigest())
        self.assertEqual(manifest['operator_properties_sha256'], hashlib.sha256((DATA/'operator-properties.json').read_bytes()).hexdigest())
        self.assertEqual(manifest['reference']['version'], suite['reference']['version'])
        self.assertEqual(manifest['reference']['build_hash'], suite['reference']['build_hash'])
        self.assertEqual([r['id'] for r in manifest['runs']], [r['id'] for r in suite['runs']])
        self.assertEqual(manifest['product_acceptance'], 'unrun')
        self.assertEqual(manifest['formora_execution'], 'unrun')
        for record in manifest['runs']:
            with self.subTest(run=record['id']):
                path = DATA/record['file']
                self.assertEqual(record['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
                mesh = json.loads(path.read_text())
                self.assertEqual(mesh['run_id'], record['id'])
                for count, field in [('vertex_count', 'vertices'), ('edge_count', 'edges'),
                                     ('face_count', 'faces'), ('uv_layer_count', 'uv_layers')]:
                    self.assertEqual(record[count], len(mesh[field]))

    def test_vertex_edge_face_and_corner_numbering_do_not_define_equivalence(self):
        for name in ['cube_default', 'uv_sphere_coarse', 'monkey_default']:
            with self.subTest(name=name):
                source = load(name)
                self.assertTrue(comparison.compare(source, renumber(source), LIMITS)['oriented_topology_matches_reference'])

    def test_face_winding_cannot_be_reversed(self):
        source = load('cube_default')
        changed = copy.deepcopy(source)
        changed['faces'][0].reverse()
        with self.assertRaisesRegex(comparison.Mismatch, 'oriented face topology'):
            comparison.compare(source, changed, LIMITS)

    def test_equal_counts_do_not_hide_a_broken_loose_edge(self):
        source = load('circle_nothing')
        changed = copy.deepcopy(source)
        changed['edges'][0] = [0, 3]
        with self.assertRaises(comparison.Mismatch):
            comparison.compare(source, changed, LIMITS)

    def test_uv_error_above_the_frozen_tolerance_fails(self):
        source = load('cube_default')
        changed = copy.deepcopy(source)
        changed['uv_layers'][0]['faces'][0][0][0] += 0.01
        with self.assertRaisesRegex(comparison.Mismatch, 'UV error'):
            comparison.compare(source, changed, LIMITS)

    def test_corrupted_corner_normal_fails(self):
        source = load('cube_default')
        changed = copy.deepcopy(source)
        changed['corner_normals'][0][0] += 0.01
        with self.assertRaisesRegex(comparison.Mismatch, 'normal error'):
            comparison.compare(source, changed, LIMITS)

    def test_position_error_has_a_fixed_boundary(self):
        source = load('cube_default')
        changed = copy.deepcopy(source)
        changed['vertices'][0][0] += 0.5e-6
        self.assertTrue(comparison.compare(source, changed, LIMITS)['oriented_topology_matches_reference'])
        changed['vertices'][0][0] += 1.0e-6
        with self.assertRaisesRegex(comparison.Mismatch, 'no position/topology match'):
            comparison.compare(source, changed, LIMITS)

    def test_small_local_error_cannot_be_amplified_past_the_world_tolerance(self):
        source = load('cube_default')
        for i in range(3):
            source['matrix_world'][i][i] = 100.0
        source['bounds_world'] = [[value*100 for value in side] for side in source['bounds_local']]
        changed = copy.deepcopy(source)
        # Move one corner inward. Other corners keep the same bounding box.
        for axis in range(3):
            changed['vertices'][0][axis] *= 1.0 - 0.5e-6
        with self.assertRaisesRegex(comparison.Mismatch, 'world position error'):
            comparison.compare(source, changed, LIMITS)

    def test_coincident_vertices_are_not_welded(self):
        source = load('monkey_default')
        changed = copy.deepcopy(source)
        duplicate = next(i for i, v in enumerate(source['vertices']) if v in source['vertices'][:i])
        del changed['vertices'][duplicate]
        with self.assertRaisesRegex(comparison.Mismatch, 'vertex count'):
            comparison.compare(source, changed, LIMITS)

    def test_missing_uv_corners_and_nonfinite_coordinates_fail(self):
        source = load('cube_default')
        changed = copy.deepcopy(source)
        changed['uv_layers'][0]['faces'][0].pop()
        with self.assertRaisesRegex(comparison.Mismatch, 'UV corner count'):
            comparison.compare(source, changed, LIMITS)
        changed = copy.deepcopy(source)
        changed['vertices'][0][0] = float('nan')
        with self.assertRaisesRegex(comparison.Mismatch, 'finite'):
            comparison.compare(source, changed, LIMITS)


if __name__ == '__main__':
    unittest.main()

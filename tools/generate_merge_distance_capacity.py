"""Author attributed class-A distance workloads without source answers."""
import argparse
import gzip
import hashlib
from itertools import product
import json
from pathlib import Path

from generate_merge_distance_cases import asset
from generate_merge_distance_diagnostic import diagnostic


def grid(kind):
    side = 100
    points = [[x*.125, y*.125, ((x*7+y*11) % 5)*.015625 if kind == 'a' else -((x*3+y*5) % 7)*.0078125]
              for y in range(side+1) for x in range(side+1)]
    faces = [[y*(side+1)+x, y*(side+1)+x+1, (y+1)*(side+1)+x+1, (y+1)*(side+1)+x]
             for y in range(side) for x in range(side)]
    result = asset(points, faces)
    assert [len(result[key]) for key in ['vertices', 'edges', 'polygons']] == [10201, 20200, 10000]
    return result


def assets():
    return {'mesh_a': grid('a'), 'mesh_b': grid('b')}


def registry(asset_identity):
    template = diagnostic(); runs = []
    for options, context, selection, normals, sample in product(
            range(8), ['single_a', 'multi_a_first'], ['all', 'alternating'], ['automatic', 'custom_constant'], range(3)):
        factors = {name: levels[0] for name, levels in template['factors'].items()}
        factors.update(context=context, selection=selection, frame='noncommuting', history='forward')
        factors['options'] = options
        runs.append({'id': f'distance_class_a_{len(runs):03}', 'purpose': 'attributed_class_a_distance_merge',
                     'factors': factors, 'selection_mask': ['VERT'], 'sample': sample, 'normal_profile': normals,
                     'parameters': {'threshold': .1875, 'use_centroid': bool(options & 1),
                                    'use_unselected': bool(options & 2), 'use_sharp_edge_from_normals': bool(options & 4)}})
    return {'schema_version': 1, 'scope': 'complete_distance_merge_class_a_capacity_registry',
            'source_commit': template['source_commit'], 'scene_template': template,
            'capacity_assets': asset_identity, 'runs': runs,
            'capacity_gate': {'class_a_vertices': 10201, 'class_a_edges': 20200, 'class_a_quads': 10000,
                              'forms': 64, 'samples_each': 3, 'all_samples_required': True,
                              'per_data_core_ms': 250, 'per_data_pipeline_ms': 2000,
                              'two_data_core_ms': 500, 'two_data_pipeline_ms': 4000,
                              'full_validation_inside_clocks': True,
                              'core_clock': 'initial validation, native operation, complete output snapshot and validation',
                              'pipeline_clock': 'core, native save, independent native file reopen and complete validation',
                              'source_measurements_are_not_rust_product_timing': True},
            'normal_requests': {'custom_constant': [1., 0., 1.]},
            'native_source_execution': 'unrun', 'rust_distance_implementation': 'unrun', 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = (json.dumps(assets(), separators=(',', ':'), allow_nan=False)+'\n').encode()
    compressed = gzip.compress(raw, mtime=0)
    with args.assets.open('xb') as stream: stream.write(compressed)
    identity = {'file': args.assets.name, 'stored_sha256': hashlib.sha256(compressed).hexdigest(),
                'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw)}
    suite = registry(identity)
    with args.output.open('x') as stream: json.dump(suite, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'capacity_cases': len(suite['runs']), 'forms': 64, 'samples_per_form': 3,
                      'raw_asset_bytes': len(raw), 'stored_asset_bytes': len(compressed), 'source_execution': 'unrun'}))

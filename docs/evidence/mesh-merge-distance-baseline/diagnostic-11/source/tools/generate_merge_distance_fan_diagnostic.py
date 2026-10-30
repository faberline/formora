"""Author open and cyclic smooth-fan inputs before their native capture."""
import argparse
import copy
import json
from pathlib import Path

from generate_merge_distance_cases import asset
from generate_merge_distance_normal_diagnostic import normal_diagnostic


def fan_diagnostic():
    suite = normal_diagnostic()
    fixtures = {
        'smooth_open': asset([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.],
                              [2., 0., .25], [2., 1., .25]], [[0, 1, 2, 3], [1, 4, 5, 2]]),
        'smooth_cyclic': asset([[0., 0., .5], [1., 0., 0.], [0., 1., 0.], [-1., 0., 0.], [0., -1., 0.]],
                                [[0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 1]])}
    for name, mesh in fixtures.items():
        mesh['sharp_edges'] = []
        for face in mesh['polygons'].values(): face['smooth'] = True
        suite['mesh_fixtures'][name] = mesh; suite['factors']['fixture'].append(name)
    suite['custom_normal_vectors']['fan_constant'] = [[1., 0., 1.]]
    suite['factors']['normals'].append('fan_constant')
    for fixture in fixtures:
        for preset in ['fan_constant', 'custom_split', 'probe_zero']:
            for options in [1, 5]:
                run = copy.deepcopy(suite['runs'][13]); run['id'] = f'distance_diag_{len(suite["runs"]):03}'
                run['purpose'] = fixture+'_'+preset+'_sharp'+str(bool(options & 4)).lower()
                run['factors'].update(fixture=fixture, normals=preset, options=options, selection='all', mode=1)
                run['selection_mask'] = ['VERT']
                run['parameters'].update(use_centroid=True, use_unselected=False, use_sharp_edge_from_normals=bool(options & 4))
                suite['runs'].append(run)
    suite['scope'] = 'targeted_source_cluster_and_smooth_fan_diagnostics_only'
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); suite = fan_diagnostic()
    with args.output.open('x') as stream: json.dump(suite, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'diagnostic_cases': len(suite['runs']), 'full_source_gate': 'unrun'}))

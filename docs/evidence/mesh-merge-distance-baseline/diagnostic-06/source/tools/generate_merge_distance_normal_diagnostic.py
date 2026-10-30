"""Add independently specified normal-codec probes before final source freezing."""
import argparse
import copy
import json
from pathlib import Path

from generate_merge_distance_diagnostic import diagnostic


def normal_diagnostic():
    suite = diagnostic()
    profiles = {'diagonal': [[1., 1., 1.], [-1., 2., 3.]],
                'negative': [[0., 0., -1.], [-1., 0., 0.], [0., -1., 0.]],
                'nonunit': [[3., 4., 5.], [0., 0., 7.]],
                'near_auto': [[.00005, 0., 1.]],
                'tiny': [[1e-20, 0., 1e-20]],
                'zero': [[0., 0., 0.]]}
    for name, vectors in profiles.items():
        preset = 'probe_'+name
        suite['custom_normal_vectors'][preset] = vectors
        suite['factors']['normals'].append(preset)
        run = copy.deepcopy(suite['runs'][13]); run['id'] = f'distance_diag_{len(suite["runs"]):03}'
        run['purpose'] = 'normal_codec_'+name; run['factors']['normals'] = preset
        suite['runs'].append(run)
    suite['scope'] = 'targeted_source_and_single_corner_codec_diagnostics_only'
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); suite = normal_diagnostic()
    with args.output.open('x') as stream: json.dump(suite, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'diagnostic_cases': len(suite['runs']), 'full_source_gate': 'unrun'}))

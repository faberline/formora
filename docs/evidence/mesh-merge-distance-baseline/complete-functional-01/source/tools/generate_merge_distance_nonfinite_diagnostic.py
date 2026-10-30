"""Author native Python nonfinite probes; these are not valid JSON numbers."""
import argparse
import copy
import json
from pathlib import Path

from generate_merge_distance_parameter_diagnostic import parameter_diagnostic


def nonfinite_diagnostic():
    suite = parameter_diagnostic(); base = suite['runs'][1]
    for name in ['threshold', 'use_centroid', 'use_unselected', 'use_sharp_edge_from_normals']:
        for token in ['nan', 'positive_infinity', 'negative_infinity']:
            run = copy.deepcopy(base); run['id'] = f'distance_diag_{len(suite["runs"]):03}'
            run.update(purpose='native_nonfinite_'+name+'_'+token, native_nonfinite_probe=True)
            run['parameters'][name] = {'$native_float': token}
            suite['runs'].append(run)
    suite['scope'] = 'targeted_native_nonfinite_scalar_diagnostics_only'
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); suite = nonfinite_diagnostic()
    with args.output.open('x') as stream: json.dump(suite, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'diagnostic_cases': len(suite['runs']), 'native_nonfinite_probes': 12,
                      'json_numeric_nonfinite_inputs_admitted': False, 'full_source_gate': 'unrun'}))

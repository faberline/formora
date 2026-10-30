"""Author omitted, bounded and invalid scalar operator arguments."""
import argparse
import copy
import json
import struct
from pathlib import Path

from generate_merge_distance_cases import f32
from generate_merge_distance_fan_diagnostic import fan_diagnostic


def parameter_diagnostic():
    suite = fan_diagnostic(); base = copy.deepcopy(suite['runs'][1])
    fields = ['threshold', 'use_centroid', 'use_unselected', 'use_sharp_edge_from_normals']
    def add(purpose, parameters):
        run = copy.deepcopy(base); run['id'] = f'distance_diag_{len(suite["runs"]):03}'
        run.update(purpose=purpose, parameters=parameters, parameter_probe=True)
        suite['runs'].append(run)
    for mask in range(1, 16):
        add('omit_parameters_'+str(mask), {name: value for i, (name, value) in enumerate(base['parameters'].items()) if not mask & (1 << i)})
    bits = lambda x: struct.unpack('<I', struct.pack('<f', x))[0]
    value = lambda b: struct.unpack('<f', struct.pack('<I', b))[0]
    thresholds = [('below_hard_min', value(bits(f32(1e-6))-1)), ('hard_min', f32(1e-6)),
                  ('soft_min', f32(1e-5)), ('soft_max', 10.), ('hard_max', 50.),
                  ('above_hard_max', value(bits(50.)+1)), ('zero_float', 0.), ('negative_zero', -0.),
                  ('negative_float', -1.), ('integer_zero', 0), ('integer_one', 1),
                  ('boolean_false', False), ('boolean_true', True), ('numeric_string', '.125'),
                  ('none', None), ('list', []), ('dict', {}), ('f32_overflow', 1e40),
                  ('integer_overflow', 10**400)]
    for name, threshold in thresholds:
        parameters = copy.deepcopy(base['parameters']); parameters['threshold'] = threshold
        add('threshold_'+name, parameters)
    for field in fields[1:]:
        for name, value in [('integer_zero', 0), ('integer_one', 1), ('negative_integer', -1),
                            ('integer_two', 2), ('float_zero', 0.), ('float_one', 1.), ('float_half', .5),
                            ('string', 'false'), ('none', None), ('list', []), ('dict', {}),
                            ('integer_i32_overflow', 2**31)]:
            parameters = copy.deepcopy(base['parameters']); parameters[field] = value
            add(field+'_'+name, parameters)
    parameters = copy.deepcopy(base['parameters']); parameters['not_a_parameter'] = True
    add('unknown_keyword', parameters)
    suite['scope'] = 'targeted_source_scalar_parameter_diagnostics_only'
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); suite = parameter_diagnostic()
    with args.output.open('x') as stream: json.dump(suite, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'diagnostic_cases': len(suite['runs']), 'scalar_parameter_probes': sum(bool(r.get('parameter_probe')) for r in suite['runs']),
                      'nonfinite_probes': 'pending', 'full_source_gate': 'unrun'}))

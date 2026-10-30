"""Author targeted source-adapter diagnostics, not a complete source baseline."""
import copy
import json
from pathlib import Path
import argparse

from generate_merge_distance_cases import author


def diagnostic():
    suite = author()
    definitions = [
        ('pair_below', dict(distance='below_pair')),
        ('pair_equal', dict(distance='equal_pair')),
        ('pair_above_keep', dict(distance='above_pair')),
        ('pair_above_centroid', dict(distance='above_pair', options=1)),
        ('triplet_centroid', dict(fixture='unequal_triplet', distance='above_pair', options=1)),
        ('distance_chain', dict(fixture='distance_chain', distance='equal_pair', options=1)),
        ('centroid_tie', dict(fixture='centroid_tie', distance='above_pair', options=0)),
        ('concave_face_mode', dict(fixture='concave_face', distance='equal_pair', mode=4, options=1)),
        ('nonmanifold_edges', dict(fixture='nonmanifold_fan', selection='alternating', mode=2)),
        ('coincident_zero_axis', dict(fixture='disconnected_coincident_faces', context='multi_b_first',
                                      frame='zero_axis', units='metric_large', history='forward', options=1)),
        ('pair_zero_parent', dict(frame='zero_parent', distance='above_pair', options=1)),
        ('hidden_vertex', dict(fixture='quad_strip', context='multi_a_first', distance='above_pair', options=1)),
        ('custom_flat', dict(fixture='quad_strip', normals='custom_flat', mode=4, distance='above_pair')),
        ('custom_split_alias', dict(fixture='quad_strip', normals='custom_split', options=7, context='multi_alias_first',
                                    selection='alternating', frame='noncommuting', units='metric_small', history='reverse')),
        ('empty_selection', dict(fixture='quad_strip', selection='none', context='multi_a_first', distance='hard_max', options=7)),
    ]
    runs = []
    for i, (purpose, changes) in enumerate(definitions):
        factors = {name: levels[0] for name, levels in suite['factors'].items()}; factors.update(changes)
        for name, value in factors.items(): assert value in suite['factors'][name]
        options = factors['options']
        run = {'id': f'distance_diag_{i:03}', 'purpose': purpose, 'factors': factors,
               'parameters': {'threshold': suite['distance_values'][factors['distance']],
                              'use_centroid': bool(options & 1), 'use_unselected': bool(options & 2),
                              'use_sharp_edge_from_normals': bool(options & 4)},
               'selection_mask': [name for bit, name in [(1, 'VERT'), (2, 'EDGE'), (4, 'FACE')] if factors['mode'] & bit]}
        if purpose == 'hidden_vertex': run['hidden_pattern'] = 'last_vertex'
        runs.append(run)
    suite = copy.deepcopy(suite); suite['runs'] = runs
    suite['scope'] = 'targeted_source_adapter_diagnostics_only'
    suite['state'] = 'before_diagnostic_native_execution_not_final_input_freeze'
    suite['comparison'] = {'continuous_absolute_limit': 1e-6, 'discrete': 'exact'}
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); value = diagnostic()
    with args.output.open('x') as stream: json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'diagnostic_cases': len(value['runs']), 'full_source_gate': 'unrun', 'product_acceptance': 'unrun'}))

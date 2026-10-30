"""Author the complete distance source registry before full native execution."""
import argparse
import copy
from itertools import combinations, product
import json
from pathlib import Path

from generate_merge_distance_cases import author
from generate_merge_distance_nonfinite_diagnostic import nonfinite_diagnostic


SCOPE = 'complete_distance_merge_functional_source_registry'


def complete():
    original = author(); suite = nonfinite_diagnostic()
    diagnostics = copy.deepcopy(suite['runs']); rows = []
    for source in original['runs']:
        run = copy.deepcopy(source)
        run['purpose'] = 'original_coverage:'+','.join(run['purposes'])
        run['origin'] = 'unchanged_1188_draft_assignment'
        rows.append(run)
    rows.extend(diagnostics)
    levels = suite['factors']; names = list(levels)
    existing = {tuple(run['factors'][name] for name in names) for run in rows
                if not run.get('parameter_probe') and not run.get('native_nonfinite_probe') and
                run.get('hidden_pattern', 'none') == 'none'}
    added = 0

    def add(values, purpose, hidden=False):
        nonlocal added
        factors = {name: allowed[0] for name, allowed in levels.items()}; factors.update(values)
        key = tuple(factors[name] for name in names)
        if not hidden and key in existing: return
        if not hidden: existing.add(key)
        options = factors['options']
        run = {'id': f'distance_complete_{added:05}', 'purpose': purpose, 'factors': factors,
               'parameters': {'threshold': suite['distance_values'][factors['distance']],
                              'use_centroid': bool(options & 1), 'use_unselected': bool(options & 2),
                              'use_sharp_edge_from_normals': bool(options & 4)},
               'selection_mask': [name for bit, name in [(1, 'VERT'), (2, 'EDGE'), (4, 'FACE')] if factors['mode'] & bit]}
        if hidden: run['hidden_pattern'] = 'last_vertex'
        added += 1; rows.append(run)

    # Extend the original coverage products to the added geometry/normal levels.
    for left, right in combinations(names, 2):
        for a, b in product(levels[left], levels[right]):
            add({left: a, right: b}, 'expanded_two_factor_assignments')
    for fixture, options, distance in product(levels['fixture'], levels['options'], levels['distance']):
        add(dict(fixture=fixture, options=options, distance=distance), 'expanded_geometry_options_distance')
    for mode, selection, context in product(levels['mode'], levels['selection'], levels['context']):
        add(dict(mode=mode, selection=selection, context=context), 'mode_selection_context')
    for options, normals, frame in product(levels['options'], levels['normals'], levels['frame']):
        add(dict(fixture='quad_strip', options=options, normals=normals, frame=frame), 'expanded_normal_options_frame')
    for i, (mode, selection, context, history) in enumerate(product(
            levels['mode'], levels['selection'], levels['context'], levels['history'])):
        add(dict(fixture='quad_strip', mode=mode, selection=selection, context=context,
                 history=history, options=i % 8, distance='above_pair'), 'hidden_mode_selection_context_history', hidden=True)
    suite['runs'] = rows
    suite.update(scope=SCOPE, state='complete_authored_inputs_before_immutable_code_seal_and_source_execution',
                 native_execution='unrun', product_implementation='unrun', product_acceptance='unrun')
    suite['selection_rule'] = 'Choose the first enabled native domain (VERT, then EDGE, then FACE); author its all/odd/none selection, then close incidence and native flush.'
    suite['initial_binding_requirements'] = ['literal scene adapter, complete initial state, exact declared selection/history, source quantized normals, data providers and outside data']
    suite['remaining_before_freeze'] = ['immutable registry/capture/checker seal before complete native execution', 'separate frozen capacity workload and actual source results before Rust']
    suite['coverage_scope'] = 'all expanded two-factor assignments; named full three-factor products; full hidden mode/selection/context/history product; retained analytic and scalar/native probes; not all Cartesian combinations or all float values'
    suite['comparison'] = {'continuous_absolute_limit': 1e-6, 'discrete': 'exact'}
    suite['source_requirements'] = {'fresh_viewport_processes': 2, 'native_save_reopen': 'every_case',
                                    'failed_or_missing_terminal': 'cannot_pass', 'source_answers_in_inputs': 'forbidden',
                                    'capacity': 'required_before_rust_implementation', 'independent_product_acceptance': 'unrun'}
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); suite = complete()
    with args.output.open('x') as stream: json.dump(suite, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'complete_cases': len(suite['runs']), 'fixtures': len(suite['mesh_fixtures']),
                      'normal_presets': len(suite['factors']['normals']), 'input_seal': 'pending', 'native_execution': 'unrun'}))

"""Check the full authored coverage and purity before source/code freezing."""
import argparse
import builtins
import copy
from itertools import combinations, product
import io
import json
from pathlib import Path
from unittest.mock import patch

from generate_merge_distance_cases import author
from generate_merge_distance_complete import complete, SCOPE


def verify(suite):
    assert suite['scope'] == SCOPE, 'complete scope'
    reads = []
    def deny(*args, **kwargs): reads.append(str(args[0])); raise AssertionError('constructor source read')
    with patch.object(builtins, 'open', deny), patch.object(io, 'open', deny): expected = complete()
    assert not reads and suite == expected, 'independent regeneration'
    rows = suite['runs']; assert len(rows) == len({row['id'] for row in rows}), 'duplicate source identity'
    original = author()
    for old, new in zip(original['runs'], rows):
        assert all(new[key] == value for key, value in old.items()), 'original assignment changed'
    ordinary = [row for row in rows if not row.get('parameter_probe') and not row.get('native_nonfinite_probe')]
    levels = suite['factors']; pair_count = 0
    for left, right in combinations(levels, 2):
        required = set(product(levels[left], levels[right]))
        actual = {(row['factors'][left], row['factors'][right]) for row in ordinary}
        assert actual == required, 'two-factor coverage '+left+'/'+right
        pair_count += len(required)
    for fields in [('fixture', 'options', 'distance'), ('mode', 'selection', 'context'), ('options', 'normals', 'frame')]:
        required = set(product(*(levels[field] for field in fields)))
        actual = {tuple(row['factors'][field] for field in fields) for row in ordinary}
        assert actual == required, 'three-factor coverage '+str(fields)
    hidden = [row for row in ordinary if row.get('hidden_pattern') == 'last_vertex']
    fields = ['mode', 'selection', 'context', 'history']
    assert {tuple(row['factors'][field] for field in fields) for row in hidden} == set(product(*(levels[field] for field in fields))), 'hidden coverage'
    forbidden = {'source_expected', 'reference_answer', 'measured_result', 'captured_result', 'after', 'response'}
    def pure(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value), 'source answer in input'
            for item in value.values(): pure(item)
        elif isinstance(value, list):
            for item in value: pure(item)
    pure(suite)
    sensitive = [row for row in rows if row['purpose'] == 'unique_data_once_repeat_sensitive']
    assert {(row['factors']['options'], row['factors']['context']) for row in sensitive} == set(product([1, 3, 5, 7], levels['context'])), 'unique data repeat-sensitive coverage'
    return {'complete_cases': len(rows), 'original_assignments_unchanged': len(original['runs']),
            'expanded_pair_assignments': pair_count, 'complete_three_factor_products': 3,
            'hidden_cases': len(hidden), 'constructor_file_reads': len(reads), 'input_checks_passed': True,
            'repeat_sensitive_owner_cases': len(sensitive),
            'native_execution': 'unrun', 'input_seal': 'pending', 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = verify(json.loads(args.suite.read_text()))
    controls = []
    for name, mutate in [('source_answer', lambda x: x['mesh_fixtures']['loose_pair'].update(source_expected={})),
                         ('lost_case', lambda x: x['runs'].pop()),
                         ('changed_original_input', lambda x: x['runs'][0]['parameters'].update(threshold=.5))]:
        forged = json.loads(args.suite.read_text()); mutate(forged)
        try: verify(forged)
        except AssertionError as error: controls.append({'name': name, 'rejected': True, 'error': str(error)})
        else: raise AssertionError('forged full registry accepted: '+name)
    result['negative_controls'] = controls
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result))

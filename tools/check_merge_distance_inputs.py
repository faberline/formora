#!/usr/bin/env python3
"""Check authored geometry and draft coverage. Execute no native/product operation."""
from itertools import combinations, product
from pathlib import Path
from unittest.mock import patch
import argparse
import copy
import hashlib
import io
import json
import math
import struct

from generate_merge_distance_cases import author


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check(value):
    require(value['state'] == 'draft_inputs_before_RNA_and_native_validation', 'draft state differs')
    require(value['operator'] == 'mesh.remove_doubles', 'operator differs')
    require(value['native_execution'] == value['product_implementation'] == value['product_acceptance'] == 'unrun',
            'unrun status differs')
    require(bool(value['remaining_before_freeze']), 'missing remaining work')
    forbidden = {'source_expected', 'reference_answer', 'measured_result', 'captured_result', 'after', 'response'}

    def data_tree(node):
        if isinstance(node, dict):
            require(not forbidden.intersection(node), 'source answer field in input')
            for child in node.values():
                data_tree(child)
        elif isinstance(node, list):
            for child in node:
                data_tree(child)
        elif type(node) is float:
            require(math.isfinite(node), 'nonfinite authored number')
    data_tree(value)
    levels = value['factors']; rows = value['runs']
    require(len(rows) == len({r['id'] for r in rows}), 'duplicate case identity')
    require(len(rows) == len({tuple(r['factors'][n] for n in levels) for r in rows}), 'duplicate factor assignment')
    for row in rows:
        factors = row['factors']
        require(set(factors) == set(levels), 'factor fields differ')
        require(all(factors[k] in allowed for k, allowed in levels.items()), 'invalid factor value')
        p = row['parameters']
        require(set(p) == {'threshold', 'use_centroid', 'use_unselected', 'use_sharp_edge_from_normals'},
                'parameter fields differ')
        require(all(type(p[k]) is bool for k in p if k != 'threshold'), 'boolean parameter type differs')
        require(p['threshold'] == value['distance_values'][factors['distance']], 'threshold binding differs')
        require(tuple(p[k] for k in ['use_centroid', 'use_unselected', 'use_sharp_edge_from_normals']) ==
                tuple(bool(factors['options'] & (1 << i)) for i in range(3)), 'options binding differs')
        mask = row['selection_mask']
        require(set(mask).issubset({'VERT', 'EDGE', 'FACE'}) and len(mask) == len(set(mask)), 'invalid mask')
        require(sum({'VERT': 1, 'EDGE': 2, 'FACE': 4}[n] for n in mask) == factors['mode'], 'mask binding differs')
    required_pairs = checked_pairs = 0
    for left, right in combinations(levels, 2):
        expected = set(product(levels[left], levels[right]))
        actual = {(r['factors'][left], r['factors'][right]) for r in rows}
        require(actual == expected, 'pair coverage missing: '+left+'/'+right)
        required_pairs += len(expected); checked_pairs += len(actual)
    for fields in [('fixture', 'options', 'distance'), ('mode', 'selection', 'context'), ('options', 'normals', 'frame')]:
        expected = set(product(*(levels[n] for n in fields)))
        actual = {tuple(r['factors'][n] for n in fields) for r in rows}
        require(actual == expected, 'focused coverage missing: '+str(fields))
    for name, mesh in value['mesh_fixtures'].items():
        vertices, edges, faces = [mesh[n] for n in ['vertices', 'edges', 'polygons']]
        for order, table in [('vertex_order', vertices), ('edge_order', edges), ('face_order', faces)]:
            require(len(mesh[order]) == len(table) and set(mesh[order]) == set(table), 'native order differs')
        require(all(len(p) == 3 and all(type(x) is float and struct.unpack('<f', struct.pack('<f', x))[0] == x for x in p)
                    for p in vertices.values()), 'positions not exact finite f32')
        require(all(len(e) == 2 and len(set(e)) == 2 and set(e).issubset(vertices) for e in edges.values()),
                'invalid edge incidence')
        pairs = {frozenset(e) for e in edges.values()}
        require(len(pairs) == len(edges), 'duplicate edge')
        for face in faces.values():
            loop = face['vertices']
            require(len(loop) >= 3 and len(set(loop)) == len(loop) and set(loop).issubset(vertices), 'invalid face loop')
            require(all(frozenset((loop[i-1], loop[i])) in pairs for i in range(len(loop))), 'missing face edge')
            require(set(face['uv_layers']) == {'Detail', 'Layout'}, 'UV layers differ')
            require(all(len(layer) == len(loop) and all(len(uv) == 2 for uv in layer) for layer in face['uv_layers'].values()),
                    'UV loop coverage differs')
        for domain, table, tag in [('vertices', vertices, 'formora_v_id'), ('edges', edges, 'formora_e_id'),
                                   ('polygons', faces, 'formora_f_id')]:
            attrs = mesh['integer_attributes'][domain]
            require(set(attrs[tag].values()) == set(range(len(table))), 'provenance identity differs')
            for layer in attrs.values():
                require(set(layer) == set(table), 'integer coverage differs')
                require(all(type(n) is int and -(2**31) <= n < 2**31 for n in layer.values()), 'integer type/range differs')
        require(set(mesh['vertex_weights']) == set(vertices), 'weight coverage differs')
        require(any(w.get('pin') == 0. for w in mesh['vertex_weights'].values()), 'explicit zero weight lost')
        require(set(mesh['edge_seams']).issubset(edges) and set(mesh['sharp_edges']).issubset(edges), 'edge flag identity differs')
    distance = value['distance_values']; pair = value['mesh_fixtures']['loose_pair']['vertices']
    literal_distance = math.dist(pair['v000000'], pair['v000001'])
    require(distance['equal_pair'] == literal_distance == .125, 'authored distance is not exact')
    bits = lambda n: struct.unpack('<I', struct.pack('<f', n))[0]
    require(bits(distance['below_pair'])+1 == bits(.125) == bits(distance['above_pair'])-1,
            'f32 boundary adjacency differs')
    return {'draft_cases': len(rows), 'fixtures': len(value['mesh_fixtures']),
            'required_two_factor_assignments': required_pairs, 'checked_two_factor_assignments': checked_pairs,
            'focused_three_factor_products': 3, 'native_execution': 'unrun', 'input_freeze': 'pending'}


def verify(value):
    summary = check(value)
    reads = []
    def deny(*args, **kwargs):
        reads.append(str(args[0])); raise AssertionError('constructor file access')
    with patch('builtins.open', deny), patch.object(io, 'open', deny):
        regenerated = author()
    require(not reads and regenerated == value, 'pure regeneration differs')
    controls = []
    def reject(name, mutation, reason):
        forged = copy.deepcopy(value); mutation(forged)
        try:
            check(forged)
        except (AssertionError, KeyError) as error:
            require(reason in str(error), 'control reached the wrong check: '+name)
            controls.append({'control': name, 'rejected': True, 'error': str(error)})
        else:
            raise AssertionError('forged input accepted: '+name)
    reject('source_answer_in_fixture', lambda x: x['mesh_fixtures']['loose_pair'].update(source_expected={'after': 0}), 'source answer field')
    reject('duplicate_case', lambda x: x['runs'].append(copy.deepcopy(x['runs'][0])), 'duplicate case identity')
    reject('numeric_boolean', lambda x: x['runs'][0]['parameters'].update(use_centroid=1), 'boolean parameter type')
    reject('lost_pair_coverage', lambda x: x.update(runs=[r for r in x['runs'] if not (
        r['factors']['context'] == 'multi_alias_first' and r['factors']['mode'] == 7)]), 'pair coverage missing')
    reject('lost_three_factor_coverage', lambda x: x.update(runs=[r for r in x['runs'] if not (
        r['factors']['fixture'] == 'centroid_tie' and r['factors']['options'] == 7 and r['factors']['distance'] == 'above_pair')]), 'focused coverage missing')
    reject('missing_uv_corner', lambda x: x['mesh_fixtures']['quad_strip']['polygons']['f000000']['uv_layers']['Detail'].pop(), 'UV loop coverage')
    reject('boolean_integer_attribute', lambda x: x['mesh_fixtures']['loose_pair']['integer_attributes']['vertices']['vertices_signed'].update(v000000=True), 'integer type/range')
    reject('threshold_boundary_moved', lambda x: x['distance_values'].update(below_pair=.125), 'threshold binding')
    return {**summary, 'offline_input_checks_passed': True, 'constructor_filesystem_reads': len(reads),
            'negative_controls': controls, 'forged_operations_executed': False,
            'native_capture_ready': False, 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes(); result = verify(json.loads(raw))
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'negative_controls'}))

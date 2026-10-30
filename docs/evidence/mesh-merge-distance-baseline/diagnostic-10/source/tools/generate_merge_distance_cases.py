#!/usr/bin/env python3
"""Author draft distance-merge source inputs without reading measured answers."""
from itertools import combinations, product
from pathlib import Path
import argparse
import json
import struct


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def adjacent(value, direction):
    bits = struct.unpack('<I', struct.pack('<f', value))[0]
    return struct.unpack('<f', struct.pack('<I', bits+direction))[0]


def asset(points, faces, loose_edges=()):
    pairs = {tuple(sorted(pair)) for pair in loose_edges}
    for face in faces:
        pairs.update(tuple(sorted((face[i-1], face[i]))) for i in range(len(face)))
    vertices = {f'v{i:06}': [f32(c) for c in point] for i, point in enumerate(points)}
    edges = {f'e{i:06}': [f'v{v:06}' for v in pair] for i, pair in enumerate(sorted(pairs))}
    polygons = {}
    for i, face in enumerate(faces):
        polygons[f'f{i:06}'] = {
            'vertices': [f'v{v:06}' for v in face], 'material_slot': i % 2,
            'smooth': i % 2 == 0,
            'uv_layers': {
                'Detail': [[f32(points[v][0]*.25+.125), f32(points[v][1]*.5-.25)] for v in face],
                'Layout': [[f32(points[v][0]*.5-points[v][1]*.125), f32(points[v][1]*.25+.375)] for v in face],
            },
        }
    tables = [('vertices', vertices, 'formora_v_id'), ('edges', edges, 'formora_e_id'),
              ('polygons', polygons, 'formora_f_id')]
    return {
        'vertices': vertices, 'edges': edges, 'polygons': polygons,
        'vertex_order': list(vertices), 'edge_order': list(edges), 'face_order': list(polygons),
        'uv_layout': {'layers': ['Detail', 'Layout'], 'active': 'Layout'},
        'material_slots': ['mat0', 'mat1'],
        'edge_seams': list(edges)[::2], 'sharp_edges': list(edges)[1::2],
        'vertex_groups': ['pin', 'soft', 'empty'],
        'vertex_weights': {name: {'pin': 0. if i % 2 == 0 else 1., 'soft': (i % 4)/4.}
                           for i, name in enumerate(vertices)},
        'integer_attributes': {
            domain: {
                tag: {name: i for i, name in enumerate(table)},
                domain+'_signed': {name: 3*i-11 for i, name in enumerate(table)},
                domain+'_duplicate': {name: i % 3-1 for i, name in enumerate(table)},
            } for domain, table, tag in tables
        },
    }


def author():
    geometry = {
        'loose_pair': asset([[0, 0, 0], [.125, 0, 0]], []),
        'unequal_triplet': asset([[0, 0, 0], [.03125, 0, 0], [.125, 0, 0]], []),
        'distance_chain': asset([[0, 0, 0], [.09375, 0, 0], [.1875, 0, 0]], [], [(0, 1), (1, 2)]),
        'centroid_tie': asset([[-.0625, 0, 0], [.0625, 0, 0], [0, -.0625, 0], [0, .0625, 0]], []),
        'quad_strip': asset([[0, 0, 0], [.125, 0, 0], [1, 0, 0], [0, 1, 0], [.125, 1, 0], [1, 1, 0]],
                            [[0, 1, 4, 3], [1, 2, 5, 4]]),
        'concave_face': asset([[0, 0, 0], [2, 0, 0], [.0625, .0625, 0], [2, 2, 0], [0, 2, 0]],
                              [[0, 1, 2, 3, 4]]),
        'nonmanifold_fan': asset([[0, 0, 0], [.125, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1]],
                                 [[0, 1, 2], [1, 0, 3], [0, 1, 4]]),
        'disconnected_coincident_faces': asset([[0, 0, 0], [1, 0, 0], [0, 1, 0],
                                                 [0, 0, 0], [1, 0, 0], [0, 1, 0]],
                                                [[0, 1, 2], [3, 4, 5]]),
    }
    levels = {
        'fixture': list(geometry), 'options': list(range(8)), 'mode': list(range(1, 8)),
        'distance': ['hard_min', 'default', 'below_pair', 'equal_pair', 'above_pair', 'hard_max'],
        'selection': ['all', 'alternating', 'none'],
        'context': ['single_a', 'multi_a_first', 'multi_b_first', 'multi_alias_first'],
        'frame': ['identity', 'noncommuting', 'nonuniform', 'negative', 'zero_axis', 'zero_parent'],
        'units': ['none', 'metric_small', 'metric_large'],
        'history': ['none', 'forward', 'reverse'],
        'normals': ['automatic', 'custom_flat', 'custom_split'],
    }
    names = list(levels)
    rows = {}

    def add(values, purpose):
        row = {name: levels[name][0] for name in names}
        row.update(values)
        key = tuple(row[name] for name in names)
        if key not in rows:
            rows[key] = {'factors': row, 'purposes': []}
        if purpose not in rows[key]['purposes']:
            rows[key]['purposes'].append(purpose)

    for left, right in combinations(names, 2):
        for a, b in product(levels[left], levels[right]):
            add({left: a, right: b}, 'all_two_factor_assignments')
    # These focused products add required interactions beyond pair coverage.
    for fixture, options, distance in product(levels['fixture'], levels['options'], levels['distance']):
        add(dict(fixture=fixture, options=options, distance=distance), 'geometry_options_distance')
    for mode, selection, context in product(levels['mode'], levels['selection'], levels['context']):
        add(dict(mode=mode, selection=selection, context=context), 'mode_selection_context')
    for options, normals, frame in product(levels['options'], levels['normals'], levels['frame']):
        add(dict(options=options, normals=normals, frame=frame, fixture='quad_strip'), 'normal_options_frame')
    distances = {'hard_min': f32(1e-6), 'default': f32(1e-4), 'below_pair': adjacent(.125, -1),
                 'equal_pair': .125, 'above_pair': adjacent(.125, 1), 'hard_max': 50.}
    runs = []
    for i, row in enumerate(rows.values()):
        factors = row['factors']; options = factors['options']
        runs.append({'id': f'distance_{i:05}', **row,
                     'parameters': {'threshold': distances[factors['distance']],
                                    'use_centroid': bool(options & 1),
                                    'use_unselected': bool(options & 2),
                                    'use_sharp_edge_from_normals': bool(options & 4)},
                     'selection_mask': [name for bit, name in [(1, 'VERT'), (2, 'EDGE'), (4, 'FACE')]
                                        if factors['mode'] & bit]})
    return {
        'schema_version': 1, 'operator': 'mesh.remove_doubles',
        'source_commit': 'e13b728c6880d3084d9d57c30031ed5df8b39dee',
        'state': 'draft_inputs_before_RNA_and_native_validation',
        'factors': levels, 'distance_values': distances, 'mesh_fixtures': geometry, 'runs': runs,
        'selection_rule': 'Select all, odd-indexed or no elements in each enabled native domain. '
                          'Then apply the native selection flush and capture the actual initial state.',
        'history_rule': 'Use no history, selected native components in creation order, or that order reversed. '
                        'Do not synthesize an active component when the selected set is empty.',
        'custom_normal_vectors': {'custom_flat': [[0., 0., 1.]],
                                  'custom_split': [[0., 0., 1.], [0., 1., 0.], [1., 0., 0.]]},
        'context_intent': {
            'single_a': {'active': 'a', 'edit_owners': ['a']},
            'multi_a_first': {'active': 'a', 'edit_owners': ['a', 'b']},
            'multi_b_first': {'active': 'b', 'edit_owners': ['b', 'a']},
            'multi_alias_first': {'active': 'alias', 'edit_owners': ['alias', 'b']},
        },
        'data_sharing': {'a': 'mesh_a', 'alias': 'mesh_a', 'b': 'mesh_b', 'outside': 'mesh_outside'},
        'initial_binding_requirements': ['resolve exact frame and unit literals', 'build a distinct second mesh',
                                         'include an outside near-duplicate mesh with empty selection',
                                         'bind actual edit membership, selection flush and typed history',
                                         'capture native component order separately from interpolated tags'],
        'remaining_before_freeze': ['actual RNA defaults and bounds', 'manual content retrieval and review',
                                    'literal frame/unit/second-mesh/native context adapter',
                                    'out-of-range/type/coercion and nonfinite RNA probes',
                                    'capture/checker, independent initial binding and negative controls',
                                    'full immutable input/capture/checker seal', 'capacity workloads and source results'],
        'coverage_scope': 'all two-factor assignments plus named focused three-factor products; '
                          'not the complete Cartesian product or complete numeric/data/capacity domains',
        'native_execution': 'unrun', 'product_implementation': 'unrun', 'product_acceptance': 'unrun',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = author()
    with args.output.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'draft_cases': len(value['runs']), 'fixtures': len(value['mesh_fixtures']),
                      'native_execution': 'unrun', 'source_answers_read': False, 'input_freeze': 'pending'}))

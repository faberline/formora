#!/usr/bin/env python3
"""Author two attributed class-A grids without reading measured answers."""
import argparse
from itertools import product
import json
from pathlib import Path

from generate_multi_mesh_merge_cases import author as context_inputs


def grid(kind):
    side = 100
    points = [[x * .125, y * .125,
               ((x*7+y*11) % 5)*.015625 if kind == 'a' else -((x*3+y*5) % 7)*.0078125]
              for y in range(side+1) for x in range(side+1)]
    faces = [[y*(side+1)+x, y*(side+1)+x+1,
              (y+1)*(side+1)+x+1, (y+1)*(side+1)+x]
             for y in range(side) for x in range(side)]
    pairs = sorted({tuple(sorted((face[i-1], face[i])))
                    for face in faces for i in range(4)})
    vertices = {f'v{i:06}': point for i, point in enumerate(points)}
    edges = {f'e{i:06}': [f'v{a:06}', f'v{b:06}'] for i, (a, b) in enumerate(pairs)}
    polygons = {}
    for i, face in enumerate(faces):
        polygons[f'f{i:06}'] = {
            'vertices': [f'v{v:06}' for v in face],
            'uv_layers': {
                'Detail': [[points[v][0]*.0625+.125, points[v][1]*.03125-.25] for v in face],
                'Layout': [[points[v][0]*.03125-points[v][1]*.015625,
                            points[v][1]*.0625+points[v][0]*.0078125] for v in face],
            },
            'smooth': i % 2 == 0, 'material_slot': i % 2,
            'normal': None, 'corner_normals': None,
        }
    attributes = {
        domain: {
            tag: {id: i for i, id in enumerate(items)},
            domain+'_signed': {id: i % 257 - 128 for i, id in enumerate(items)},
            domain+'_duplicate': {id: i % 3 - 1 for i, id in enumerate(items)},
        }
        for domain, items, tag in [('vertices', vertices, 'formora_v_id'),
                                   ('edges', edges, 'formora_e_id'),
                                   ('polygons', polygons, 'formora_f_id')]
    }
    attributes['triangles'] = {}
    assert len(vertices) == 10201 and len(edges) == 20200 and len(polygons) == 10000
    return {
        'vertices': vertices, 'edges': edges, 'polygons': polygons, 'triangles': {},
        'material_slots': ['mat0', 'mat1'],
        'uv_layout': {'layers': ['Detail', 'Layout'], 'active': 'Layout'},
        'edge_seams': [id for i, id in enumerate(edges) if i % 101 == 0],
        'vertex_groups': ['pin', 'soft'],
        'vertex_weights': {id: {'pin': 0. if i % 2 == 0 else 1., 'soft': (i % 4)/4.}
                           for i, id in enumerate(vertices)},
        'integer_attributes': attributes,
    }


def author():
    suite = context_inputs()
    suite['scope'] = 'authored_two_class_A_multi_data_merge_inputs'
    suite['mesh_assets']['mesh_a'] = grid('a')
    suite['mesh_assets']['mesh_b'] = grid('b')
    suite['runs'] = [
        {'id': f'multi_merge_class_a_{i:03}', 'context': 'active_a',
         'selection': 'both', 'history': 'both_vertex',
         'parameters': {'type': method, 'uvs': uvs}, 'mode': ['VERT'],
         'frame': 'noncommuting', 'expected_enum_unavailable': False, 'sample': sample}
        for i, (method, uvs, sample) in enumerate(product(
            ['CENTER', 'CURSOR', 'COLLAPSE', 'FIRST', 'LAST'], [False, True], range(3)))
    ]
    suite['expected_cases'] = 30
    suite['expected_enum_unavailable'] = 0
    suite['expected_operator_finished'] = 30
    suite['capacity_gate'] = {
        'meshes': 2, 'vertices_each': 10201, 'edges_each': 20200, 'quads_each': 10000,
        'forms': 10, 'samples_each': 3, 'all_samples_required': True,
        'maximum_core_ms': 500., 'maximum_operation_save_reload_ms': 4000.,
        'core_clock': 'full core operation including original validation boundaries',
        'pipeline_clock': 'operation, scene save and independent fresh load, with validation',
        'budget_basis': 'sum of two unchanged existing class-A budgets of 250/2000 ms',
        'existing_workloads_and_limits': 'unchanged and still required',
        'source_capture_is_not_product_timing': True,
    }
    suite.pop('future_product_performance_proposal')
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    suite = author()
    with args.output.open('x') as stream:
        json.dump(suite, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'authored_cases': len(suite['runs']), 'native_execution': 'unrun',
                      'product_timing': 'unrun', 'measured_outputs_read': False}))

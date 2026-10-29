#!/usr/bin/env python3
"""Author the explicit selection input matrix. Does not run or accept a product."""
import itertools
import json
import math
import struct
from pathlib import Path


def build():
    vertices, faces, loose_edges, labels = [], [], [], {}

    def block(name, points, polygons=(), edges=()):
        start = len(vertices)
        labels[name] = {'vertices': list(range(start, start + len(points))),
                        'faces': list(range(len(faces), len(faces) + len(polygons)))}
        vertices.extend(points)
        faces.extend([[start + i for i in face] for face in polygons])
        loose_edges.extend([[start + a, start + b] for a, b in edges])

    block('grid', [[x, y, 0] for y in range(3) for x in range(3)],
          [[y*3+x, y*3+x+1, y*3+x+4, y*3+x+3] for y in range(2) for x in range(2)])
    block('tetrahedron', [[4,0,0], [5,0,0], [4.5,1,0], [4.5,0.5,1]],
          [[0,2,1], [0,1,3], [1,2,3], [2,0,3]])
    block('isolated', [[8,0,0], [0,0,0]])  # Distinct identity at a coincident position.
    block('wire', [[10,0,0], [11,0,0]], edges=[[0,1]])
    block('bow_tie', [[13,0,0], [14,0,0], [13,1,0], [12,0,0], [13,-1,0]],
          [[0,1,2], [0,3,4]])
    block('three_face_edge', [[16,0,0], [17,0,0], [16,1,0], [16,-1,0], [16,0,1]],
          [[0,1,2], [1,0,3], [0,1,4]])
    block('inconsistent_winding', [[19,0,0], [20,0,0], [19,1,0], [19,-1,0]],
          [[0,1,2], [0,1,3]])
    block('interior_face', [[22,0,0], [23,0,0], [22.5,1,0], [22.5,0.5,1], [22.5,0.5,-1]],
          [[0,2,1], [0,1,3], [1,2,3], [2,0,3], [0,4,1], [1,4,2], [2,4,0]])
    ring = [[26+math.cos(math.tau*i/5), math.sin(math.tau*i/5), 0] for i in range(5)]
    block('closed_poles', [*ring, [26,0,1], [26,0,-1]],
          [[5,i,(i+1)%5] for i in range(5)] + [[6,(i+1)%5,i] for i in range(5)])
    block('pentagon', [[30+math.cos(math.tau*i/5), math.sin(math.tau*i/5), 0]
                       for i in range(5)], [[0,1,2,3,4]])
    block('hidden', [[33,0,0], [34,0,0], [34,1,0], [33,1,0]], [[0,1,2,3]])
    pairs = {tuple(sorted(edge)) for edge in loose_edges}
    for face in faces:
        pairs.update(tuple(sorted((a,b))) for a,b in zip(face, face[1:]+face[:1]))
    edges = [list(pair) for pair in sorted(pairs)]
    edge_ids = {tuple(pair): i for i, pair in enumerate(edges)}
    hidden_vertices = labels['hidden']['vertices']
    hidden_edges = [i for i, edge in enumerate(edges) if all(v in hidden_vertices for v in edge)]
    vertices = [[struct.unpack('f', struct.pack('f', value))[0] for value in point]
                for point in vertices]
    mesh = {'vertices': vertices, 'edges': edges, 'faces': faces, 'labels': labels,
            'hidden': {'vertices': hidden_vertices, 'edges': hidden_edges,
                       'faces': labels['hidden']['faces']}}
    mesh['material_slots']=['SelectionMaterialA','SelectionMaterialB']
    mesh['face_materials']=[i%2 for i in range(len(faces))]
    mesh['face_smooth']=[bool(i%2) for i in range(len(faces))]
    mesh['edge_seams']=[i%3==0 for i in range(len(edges))]
    mesh['uv_layers']=[{'name':name,'faces':[[[direction*(i+j*0.125),direction*j*0.25]
                                           for j in range(len(face))]
                                          for i,face in enumerate(faces)]}
                       for name,direction in [('UVMap',1),('DetailUV',-1)]]
    mesh['active_uv_index']=0
    members=[0,1,labels['tetrahedron']['vertices'][0]]
    mesh['group_scenarios']={
        'absent':{'names':[],'weights':{}},
        'empty':{'names':['FixtureGroup'],'weights':{}},
        'positive':{'names':['FixtureGroup'],'weights':{f'v{i:06}':{'FixtureGroup':w}
                                                     for i,w in zip(members,[1.0,0.5,0.25])}},
        'zero':{'names':['FixtureGroup'],'weights':{f'v{i:06}':{'FixtureGroup':0.0}
                                                 for i in members}},
    }
    domains = ['VERT', 'EDGE', 'FACE']
    runs = []

    def seed(mask, source='tetrahedron'):
        data = labels[source]
        face = faces[data['faces'][0]]
        if 'FACE' in mask:
            return {'domain': 'FACE', 'indices': [data['faces'][0]]}
        if 'EDGE' in mask:
            return {'domain': 'EDGE', 'indices': [edge_ids[tuple(sorted(pair))]
                    for pair in [(face[0],face[1]), (face[1],face[2])]]}
        return {'domain': 'VERT', 'indices': face[:2]}

    def add(feature, operator, mode, parameters, initial=None, groups='positive'):
        mask = [mode] if isinstance(mode, str) else mode
        expected_error = None
        if operator == 'select_ungrouped':
            if mask != ['VERT']:
                expected_error = 'Must be in vertex selection mode'
            elif groups in ['absent', 'empty']:
                expected_error = 'No weights/vertex groups on object'
        unchanged = False
        if operator == 'select_mode':
            target = parameters['type']
            if not parameters.get('use_extend', False):
                unchanged = mask == [target]
            else:
                action = parameters.get('action', 'TOGGLE')
                unchanged = ((action == 'ENABLE' and target in mask)
                             or (action == 'DISABLE' and target not in mask)
                             or (len(mask) == 1 and target in mask))
        runs.append({'id': f'selection_{len(runs):04}', 'feature': feature,
                     'operator': operator, 'parameters': parameters, 'initial_mode': mask,
                     'seed': seed(mask) if initial is None else initial, 'groups': groups,
                     'expected_error': expected_error,
                     'expected_status': ['POLL_REJECTED' if expected_error else
                                         'CANCELLED' if unchanged else 'FINISHED']})

    for before, after in itertools.product(domains, repeat=2):
        add('mode', 'select_mode', before, {'type':after}, seed([before], 'grid'))
    for bits in range(1,8):
        mask = [domain for i,domain in enumerate(domains) if bits & (1 << i)]
        for target, action in itertools.product(domains, ['DISABLE','ENABLE','TOGGLE']):
            add('combined_modes', 'select_mode', mask,
                {'type':target, 'action':action, 'use_extend':True}, seed(mask, 'grid'))
    for before, after in [('VERT','EDGE'),('VERT','FACE'),('EDGE','FACE'),
                          ('FACE','VERT'),('FACE','EDGE'),('EDGE','VERT')]:
        feature = 'expand' if domains.index(before) < domains.index(after) else 'contract'
        add(feature, 'select_mode', before, {'type':after,'use_expand':True}, seed([before], 'grid'))
    flags = ['use_wire','use_boundary','use_multi_face','use_non_contiguous','use_verts']
    for values, mode, extend in itertools.product(itertools.product([False,True], repeat=5),
                                                  domains[:2], [False,True]):
        add('non_manifold', 'select_non_manifold', mode, dict(zip(flags, values), extend=extend))
    for mode, extend in itertools.product(domains, [False,True]):
        add('loose', 'select_loose', mode, {'extend':extend})
    for mode, seeded in itertools.product(domains, [False,True]):
        initial = seed([mode]) if seeded else {'domain':mode,'indices':[]}
        add('interior_faces', 'select_interior_faces', mode, {}, initial)
    comparisons = ['LESS','EQUAL','GREATER','NOTEQUAL']
    for mode, comparison, count, extend in itertools.product(domains, comparisons,
                                                             [3,4,5,2147483647], [False,True]):
        add('faces_by_sides', 'select_face_by_sides', mode,
            {'number':count,'type':comparison,'extend':extend})
    for mode, comparison, count, exclude, extend in itertools.product(domains, comparisons,
            [0,3,4,2147483647], [False,True], [False,True]):
        add('poles', 'select_by_pole_count', mode,
            {'pole_count':count,'type':comparison,'exclude_nonmanifold':exclude,'extend':extend})
    for mode, extend, group in itertools.product(domains, [False,True],
                                                 ['absent','empty','positive','zero']):
        add('ungrouped', 'select_ungrouped', mode, {'extend':extend}, groups=group)
    assert len(runs) == 530
    assert sum(r['expected_error'] is not None for r in runs) == 20
    assert sum(r['expected_status'] == ['CANCELLED'] for r in runs) == 30
    return {'schema_version':1, 'reference':{'version':[5,2,3],'build_hash':'e13b728c6880'},
            'mesh':mesh, 'runs':runs,
            'comparison':{'geometry_and_unrelated_state':'exact before/after equality',
                          'selection':'exact logical ID sets, mode, active face and ordered history',
                          'product_acceptance':'unrun'}}


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1]/'baseline/fixtures/mesh-selection.json'
    with path.open('x') as stream:
        json.dump(build(), stream, ensure_ascii=False, indent=2)
        stream.write('\n')

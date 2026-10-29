#!/usr/bin/env python3
"""Author normal fixtures independently of any measured Blender result."""
import copy
import json
from pathlib import Path


def author():
    vertices = [[0,0,0], [0,1,0], [-1,1,0], [-1,0,0], [0,0,1], [0,1,1]]
    floor, wall = [0,1,2,3], [0,4,5,1]
    cases = []

    def add(name, points, faces, smooth, kinds=None):
        edges = sorted({tuple(sorted((face[i-1], face[i]))) for face in faces for i in range(len(face))})
        cases.append({'id':name, 'vertices':copy.deepcopy(points), 'edges':[list(e) for e in edges],
                      'faces':copy.deepcopy(faces), 'smooth':smooth,
                      'kinds':kinds or ['polygon']*len(faces), 'seams':list(range(0,len(edges),3))})

    flat_points = [[10,0,0], [11,0,0], [10,1,0]]
    add('fold-smooth', vertices, [floor,wall], [True,True])
    add('fold-flat', vertices, [floor,wall], [False,False])
    add('fold-mixed', vertices, [floor,wall], [False,True])
    add('fold-mixed-domain', vertices+flat_points, [floor,wall,[6,7,8]], [True,True,False])
    add('winding-mixed-domain', vertices+flat_points, [floor,wall[::-1],[6,7,8]], [True,True,False])
    nonmanifold = vertices+[[0,1,-1], [0,0,-1]]
    add('nonmanifold-smooth', nonmanifold, [floor,wall,[0,1,6,7]], [True]*3)
    add('nonmanifold-mixed-domain', nonmanifold+flat_points, [floor,wall,[0,1,6,7],[8,9,10]], [True,True,True,False])
    bowtie = vertices+[[0,-1,0], [0,-1,1], [0,0,1]]
    add('bowtie-smooth', bowtie, [floor,[0,6,7,8]], [True,True])
    add('bowtie-mixed-domain', bowtie+flat_points, [floor,[0,6,7,8],[9,10,11]], [True,True,False])
    for state in ['flat','smooth','mixed-domain']:
        points = [[0,0,0],[1,0,0],[2,0,0]]
        faces, flags = [[0,1,2]], [state!='flat']
        if state=='mixed-domain':points+=flat_points;faces+=[[3,4,5]];flags+=[False]
        add('collinear-'+state, points, faces, flags)
    add('legacy-triangle-and-polygon', vertices, [[0,1,2],wall], [True,True], ['triangle','polygon'])
    add('coincident-distinct-vertices', vertices+[[0,0,0]], [floor,[6,4,5,1]], [True,True])
    add('nonplanar-quad', [[0,0,0],[2,0,0],[2,1,0.75],[0,1,0]], [[0,1,2,3]], [False])
    add('concave-pentagon', [[0,0,0],[3,0,0],[1,1,0.4],[3,3,0],[0,3,0]], [[0,1,2,3,4]], [False])
    for scale in [1e-12,1e-4,1e6]:
        add('fold-scale-'+str(scale), [[v*scale for v in p] for p in vertices], [floor,wall], [True,True])
    # Authored opposing slivers exercise cancellation without importing an output position.
    add('sliver-quad', [[0,0,0],[1,0,0],[1,1e-7,1e-8],[0,2e-7,0]], [[0,1,2,3]], [False])
    root=Path(__file__).resolve().parents[1]
    mesh=json.loads((root/'baseline/fixtures/mesh-transform.json').read_text())['mesh']
    add('transform-authored-before', mesh['vertices'], mesh['faces'], mesh['face_smooth'])
    return {'schema_version':1, 'reference':{'version':[5,2,3],'build_hash':'e13b728c6880'},
            'normal_absolute_tolerance':1e-6, 'cases':cases,
            'scope':'Automatic normals only. No product transform or full normal editing acceptance.'}


if __name__=='__main__':
    path=Path(__file__).resolve().parents[1]/'baseline/fixtures/mesh-normals.json'
    path.write_text(json.dumps(author(),indent=2,allow_nan=False)+'\n')

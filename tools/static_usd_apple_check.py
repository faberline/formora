#!/usr/bin/env python3
"""Check actual Apple loader buffers against the native mother, without USD parsing."""
import json
import math
from pathlib import Path
import sys

TOLERANCE=1e-6

def near(a,b):
    assert len(a)==len(b),(a,b)
    assert all(math.isfinite(float(x)) and abs(x-y)<=TOLERANCE for x,y in zip(a,b)),(a,b)

def mapped(p): return [p[0],p[2],-p[1]]

def check(report,scene,root):
    assert report['loader']=='RealityKit.Entity.load(contentsOf:)'
    assert report['metal_device']!='unavailable' and report['pid']>0
    def id(v):return 'id_'+v.encode().hex()
    nodes=report['nodes']; by_name={n['name']:n for n in nodes}
    for name in ['Formora',*(id(v) for v in scene['entities'])]:
        assert sum(n['name']==name for n in nodes)==1,('missing or duplicate semantic node',name)
    assert 'Formora' in by_name
    mesh_nodes=[]
    for name,e in scene['entities'].items():
        node=by_name[id(name)]
        # Import root may add an anonymous axis conversion node. Semantic node
        # parentage must still be exact, including the selected root's parent.
        parent='Formora' if e['parent'] is None else id(e['parent'])
        assert node['parent'].split('/')[-1]==parent,(name,node['parent'],parent)
        t=e['transform'];assert t['rotation']==[0,0,0,1] and t['scale']==[1,1,1]
        for row,want in zip(node['local_matrix'],[[1,0,0,t['translation'][0]],[0,1,0,t['translation'][1]],[0,0,1,t['translation'][2]],[0,0,0,1]]): near(row,want)
        if e['content']['kind']=='empty':continue
        a=scene['mesh_assets'][e['content']['geometry']['id']]
        matching=[n for n in nodes if n['parent']==node['path'] and n['name']=='Geometry']
        assert len(matching)==1,('missing or duplicate geometry',name)
        geometry=matching[0]
        mesh_nodes.append(geometry['path'])
        # Expected transforms from independent authoring inputs, no imported
        # matrices used to construct the reference answer.
        offset=[0.,0.,0.]; current=name
        while current is not None:
            tr=scene['entities'][current]['transform'];offset=[x+y for x,y in zip(offset,tr['translation'])];current=scene['entities'][current]['parent']
        expected=[]
        for face in a['triangles'].values():
            expected.append([mapped([x+y for x,y in zip(a['vertices'][v],offset)]) for v in face['vertices']])
        actual=[]
        for part in geometry['parts']:
            mat=geometry['materials'][part['material_index']]
            assert mat.get('numeric_values_available',True),('Apple imported opaque material; numeric material acceptance remains failed',mat)
            material=scene['materials'][e['content']['material']]
            near(mat['base_color'],material['base_color'])
            near([mat['roughness'],mat['metallic']],[material['roughness'],material['metallic']])
            vertices=part['world_positions'];indices=part['indices']
            assert len(indices)%3==0
            for i in range(0,len(indices),3):actual.append([vertices[j] for j in indices[i:i+3]])
        assert len(actual)==len(expected),(name,len(actual),len(expected))
        # Apple may reorder triangles and corners, but may not reverse winding.
        # Match oriented corner triples with cyclic rotations only.
        unmatched=list(actual)
        for triangle in expected:
            match=None
            for i,other in enumerate(unmatched):
                for shift in range(3):
                    if all(abs(triangle[k][axis]-other[(k+shift)%3][axis])<=TOLERANCE for k in range(3) for axis in range(3)):
                        match=i;break
                if match is not None:break
            assert match is not None,('missing oriented triangle',name,triangle)
            unmatched.pop(match)
        assert not unmatched
    assert set(mesh_nodes)=={n['path'] for n in nodes if n.get('parts')},'extra geometry'
    all_points=[p for n in nodes for part in n.get('parts',[]) for p in part['world_positions']]
    low=[min(p[i] for p in all_points) for i in range(3)];high=[max(p[i] for p in all_points) for i in range(3)]
    near([(low[0]+high[0])/2,low[1],(low[2]+high[2])/2],[0,0,0])
    return {'passed':True,'meshes':len(mesh_nodes),'tolerance':TOLERANCE,'geometry':'complete oriented triangle corners','materials':'actual Apple numeric material properties','hierarchy':'exact semantic parents','source_units':'metres','apple_axis':'Y up'}

if __name__=='__main__':
    report,scene=map(lambda p:json.loads(Path(p).read_text()),sys.argv[1:3])
    print(json.dumps(check(report,scene,sys.argv[3]),indent=2))

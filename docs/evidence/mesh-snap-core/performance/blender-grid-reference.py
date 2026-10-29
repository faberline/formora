#!/usr/bin/env python3
"""Capture ten direct snap forms on the unchanged authored 100x100 grid."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

import bmesh
import bpy

ROOT=Path(__file__).resolve().parents[4]
ADAPTER=ROOT/'tools/blender_snap_menu_reference.py'
spec=importlib.util.spec_from_file_location('snap_reference',ADAPTER)
snap=importlib.util.module_from_spec(spec);spec.loader.exec_module(snap)
base=snap.base


def capture(args):
    assert not bpy.app.background and list(bpy.app.version)==[5,2,3]
    assert bpy.app.build_hash.decode()=='e13b728c6880'
    assert base.digest(bpy.app.binary_path)=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert not args.output.exists()
    paths=[args.scene,Path(__file__),ADAPTER,snap.ADAPTER,snap.transform.BASE_PATH,ROOT/'baseline/fixtures/snap-menu.json']
    hashes={str(p.resolve()):base.digest(p) for p in paths}
    scene=json.loads(args.scene.read_text());asset=scene['mesh_assets']['grid']
    vertices=sorted(asset['vertices']);edges=sorted(asset['edges']);faces=sorted(asset['polygons'])
    assert (len(vertices),len(edges),len(faces))==(10201,20200,10000)
    assert vertices==[f'v{i:06}' for i in range(10201)]
    assert edges==[f'e{i:06}' for i in range(20200)] and faces==[f'f{i:06}' for i in range(10000)]
    assert asset['editing']['selected']['vertices']==vertices
    assert asset['editing']['history']==[{'domain':'vertex','id':vertices[-1]}]
    assert scene['authoring_context']['cursor_location']==[.375,-.625,.875]
    assert scene['entities']['target']['parent'] is None
    transform=scene['entities']['target']['transform']
    assert transform['translation']==[0,0,0] and transform['scale']==[1,1,1] and transform['rotation']==[0,0,0,1]
    assert not asset.get('vertex_groups') and not asset.get('vertex_weights')
    assert not asset['material_slots'] and not asset.get('uv_layout') and not asset['triangles']
    assert all(not f['uv_layers'] and not f['smooth'] for f in asset['polygons'].values())
    index={id:i for i,id in enumerate(vertices)}
    suite=json.loads((ROOT/'baseline/fixtures/snap-menu.json').read_text())
    suite['mesh']={'vertices':[asset['vertices'][id] for id in vertices],
        'edges':[[index[v] for v in asset['edges'][id]] for id in edges],
        'faces':[[index[v] for v in asset['polygons'][id]['vertices']] for id in faces],
        'face_smooth':[False]*10000,'face_materials':[0]*10000,
        'edge_seams':[id in asset.get('edge_seams',[]) for id in edges],
        'material_slots':[],'uv_layers':[],'active_uv_index':0,'active_material_index':0,
        'hidden':{'vertices':[],'edges':[],'faces':[]},
        'group_scenarios':{'authored':{'names':[],'weights':{}}}}
    forms=[('selected-grid','snap_selected_to_grid',{}),('selected-active','snap_selected_to_active',{}),
        ('cursor-grid','snap_cursor_to_grid',{}),('cursor-selected','snap_cursor_to_selected',{}),
        ('cursor-active','snap_cursor_to_active',{}),('cursor-origin','snap_cursor_to_center',{})]
    for offset in [False,True]:
        for rotation in [False,True]:forms.append((f'selected-cursor-{str(offset).lower()}-{str(rotation).lower()}',
            'snap_selected_to_cursor',{'use_offset':offset,'use_rotation':rotation}))
    records=[]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='formora-snap-grid-stage-',dir=args.output.parent) as temporary:
        stage=Path(temporary)/'capture';stage.mkdir()
        for name,operator,parameters in forms:
            run=copy.deepcopy(suite['runs'][0]);run.update(id=name,operator=operator,parameters=parameters,
                feature='scene.'+operator,label='authored fixed 100x100 grid')
            run['seed']['indices']=list(range(10201))
            run['context'].update(cursor_location=[.375,-.625,.875],cursor_rotation=[0,0,0],grid_spacing=.75,history='preserve')
            objects,area,region=snap.create(suite,run)
            bm=bmesh.from_edit_mesh(objects['target'].data);layer=bm.verts.layers.int[base.LAYERS[0]]
            bm.select_history.clear();bm.select_history.add(next(v for v in bm.verts if v[layer]==10200))
            bmesh.update_edit_mesh(objects['target'].data,loop_triangles=False,destructive=False)
            before=snap.snapshot(objects,area,run)
            with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):
                op=getattr(bpy.ops.view3d,operator);assert op.poll();status=sorted(op(**parameters))
            assert status==['FINISHED'];bpy.context.view_layer.update();after=snap.snapshot(objects,area,run)
            assert len(after['meshes']['target']['geometry']['vertices'])==10201
            file=name+'.json';base.write(stage/file,{'run':run,'before':before,'after':after,'result':{'status':status,'error':None}})
            records.append({'form':name,'file':file,'sha256':base.digest(stage/file),'status':status})
            print(json.dumps({'captured_form':name,'vertices':10201}),flush=True)
        assert hashes=={str(p.resolve()):base.digest(p) for p in paths},'source grid input changed'
        base.write(stage/'manifest.json',{'schema_version':1,'product':'blender','version':list(bpy.app.version),
            'build_hash':bpy.app.build_hash.decode(),'binary_sha256':base.digest(bpy.app.binary_path),
            'process_id':os.getpid(),'background':False,'input_hashes':hashes,'forms':10,'runs':records,
            'input_rule':'Only the authored fixed grid, identity pose, selected IDs, last active vertex, cursor and grid spacing enter setup. No measured result enters an input.',
            'product_acceptance':'unrun'})
        stage.rename(args.output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    def start():
        try:capture(args)
        except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
        sys.stdout.flush();sys.stderr.flush();os._exit(0)
    bpy.app.timers.register(start,first_interval=.5)

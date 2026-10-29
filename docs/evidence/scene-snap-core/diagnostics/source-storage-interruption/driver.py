#!/usr/bin/env python3
"""Capture the three fixed scene classes using only authored saved inputs."""
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
spec=importlib.util.spec_from_file_location('scene_snap_reference',ADAPTER)
snap=importlib.util.module_from_spec(spec);spec.loader.exec_module(snap)
base=snap.base


def mesh_input(asset):
    vertices=sorted(asset['vertices']);edges=sorted(asset['edges']);faces=sorted(asset['polygons'])
    assert (len(vertices),len(edges),len(faces))==(10201,20200,10000)
    assert vertices==[f'v{i:06}' for i in range(10201)]
    assert edges==[f'e{i:06}' for i in range(20200)] and faces==[f'f{i:06}' for i in range(10000)]
    assert asset['editing']['selected']['vertices']==vertices
    assert asset['editing']['history']==[{'domain':'vertex','id':vertices[-1]}]
    assert not asset.get('vertex_groups') and not asset.get('vertex_weights') and not asset['triangles']
    assert not asset['material_slots'] and not asset.get('uv_layout')
    assert all(not face['uv_layers'] and not face['smooth'] for face in asset['polygons'].values())
    index={id:i for i,id in enumerate(vertices)}
    return {'vertices':[asset['vertices'][id] for id in vertices],
        'edges':[[index[v] for v in asset['edges'][id]] for id in edges],
        'faces':[[index[v] for v in asset['polygons'][id]['vertices']] for id in faces],
        'face_smooth':[False]*10000,'face_materials':[0]*10000,
        'edge_seams':[id in asset.get('edge_seams',[]) for id in edges],
        'material_slots':[],'uv_layers':[],'active_uv_index':0,'active_material_index':0,
        'hidden':{'vertices':[],'edges':[],'faces':[]},'group_scenarios':{'authored':{'names':[],'weights':{}}}}


def create(suite,run,scene):
    target=base.create(suite['mesh'],run);target.name='target'
    bpy.ops.object.mode_set(mode='OBJECT');objects={'target':target};assets={'grid':target.data}
    for name in scene['object_context']['order']:
        data=scene['entities'][name]
        if name!='target':
            if data['content']['kind']=='mesh':
                asset=data['content']['geometry']['id']
                if asset not in assets:assets[asset]=target.data.copy()
                obj=bpy.data.objects.new(name,assets[asset])
            else:obj=bpy.data.objects.new(name,None)
            bpy.context.collection.objects.link(obj);objects[name]=obj
        obj=objects[name];transform=data['transform']
        assert transform['rotation']['kind']=='euler' and transform['rotation']['order']=='xyz'
        obj.rotation_mode='XYZ';obj.location=transform['translation']
        obj.rotation_euler=transform['rotation']['angles'];obj.scale=transform['scale']
        if data['parent'] is not None:obj.parent=objects[data['parent']]
    context=scene['object_context']
    for name,obj in objects.items():
        obj.select_set(name in context['selected'])
        state=context['states'].get(name,{})
        assert state.get('parent_inverse') is None
        obj.lock_location=state.get('lock_location',[False]*3)
        obj.lock_rotation=state.get('lock_rotation',[False]*3)
    bpy.context.view_layer.objects.active=objects[context['active']]
    settings=bpy.context.scene.tool_settings
    settings.mesh_select_mode=(True,False,False)
    if context['edit_objects']:
        bpy.ops.object.mode_set(mode='EDIT');seen=set()
        for obj in objects.values():
            if obj.type=='MESH' and obj.mode=='EDIT' and obj.data.as_pointer() not in seen:
                snap.select_mesh(obj,suite,run);seen.add(obj.data.as_pointer())
                bm=bmesh.from_edit_mesh(obj.data);layer=bm.verts.layers.int[base.LAYERS[0]]
                bm.select_history.clear();bm.select_history.add(next(v for v in bm.verts if v[layer]==10200))
                bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)
        assert {name for name,obj in objects.items() if obj.mode=='EDIT'}==set(context['edit_objects'])
    settings.transform_pivot_point='MEDIAN_POINT'
    settings.use_transform_skip_children=context['skip_children'];settings.use_transform_data_origin=context['origins_only']
    settings.use_keyframe_insert_auto=False;settings.use_mesh_automerge=False;settings.use_mesh_automerge_and_split=False
    settings.use_transform_pivot_point_align=False
    cursor=bpy.context.scene.cursor;cursor.location=scene['authoring_context']['cursor_location']
    cursor.rotation_mode='XYZ';cursor.rotation_euler=scene['authoring_context']['cursor_rotation']
    bpy.context.scene.unit_settings.system='NONE';bpy.context.scene.unit_settings.scale_length=1
    area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');region=next(r for r in area.regions if r.type=='WINDOW')
    area.spaces.active.overlay.grid_scale=.75;area.spaces.active.region_3d.view_perspective='PERSP'
    bpy.context.view_layer.update()
    with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):area.spaces.active.region_3d.update()
    return objects,area,region


def capture(args):
    assert not bpy.app.background and list(bpy.app.version)==[5,2,3] and bpy.app.build_hash.decode()=='e13b728c6880'
    assert base.digest(bpy.app.binary_path)=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert not args.output.exists()
    paths=[args.samples/f'input-{c}.json' for c in ['A','B','C']]+[Path(__file__),ADAPTER,snap.ADAPTER,snap.transform.BASE_PATH,ROOT/'baseline/fixtures/snap-menu.json']
    hashes={str(p.resolve()):base.digest(p) for p in paths};records=[]
    forms=[('selected-grid','snap_selected_to_grid',{}),('selected-active','snap_selected_to_active',{}),
        ('cursor-grid','snap_cursor_to_grid',{}),('cursor-selected','snap_cursor_to_selected',{}),
        ('cursor-active','snap_cursor_to_active',{}),('cursor-origin','snap_cursor_to_center',{})]
    for offset in [False,True]:
        for rotation in [False,True]:forms.append((f'selected-cursor-{str(offset).lower()}-{str(rotation).lower()}',
            'snap_selected_to_cursor',{'use_offset':offset,'use_rotation':rotation}))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='formora-scene-snap-grid-stage-',dir=args.output.parent) as temporary:
        stage=Path(temporary)/'capture';stage.mkdir()
        for case in ['A','B','C']:
            scene=json.loads((args.samples/f'input-{case}.json').read_text())
            assert scene['authoring_context']['cursor_location']==[.375,-.625,.875]
            assert len(scene['mesh_assets'])==(2 if case=='C' else 1)
            suite=json.loads((ROOT/'baseline/fixtures/snap-menu.json').read_text());suite['mesh']=mesh_input(scene['mesh_assets']['grid'])
            if case=='C':assert scene['mesh_assets']['secondary_grid']==scene['mesh_assets']['grid']
            for name,operator,parameters in forms:
                run=copy.deepcopy(suite['runs'][0]);run.update(id=case+'-'+name,operator=operator,parameters=parameters,
                    feature='scene.'+operator,label='fixed class '+case,mode='OBJECT' if case=='A' else 'EDIT_MESH')
                run['seed']['indices']=list(range(10201));run['context'].update(grid_spacing=.75,unit_system='NONE',unit_scale_length=1.)
                objects,area,region=create(suite,run,scene);before=snap.snapshot(objects,area,run)
                with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):
                    op=getattr(bpy.ops.view3d,operator);assert op.poll();status=sorted(op(**parameters))
                assert status==['FINISHED'];bpy.context.view_layer.update();after=snap.snapshot(objects,area,run)
                file=case+'-'+name+'.json';base.write(stage/file,{'class':case,'run':run,'before':before,'after':after,'result':{'status':status,'error':None}})
                records.append({'class':case,'form':name,'file':file,'sha256':base.digest(stage/file),'status':status})
                print(json.dumps({'class':case,'captured_form':name}),flush=True)
        assert hashes=={str(p.resolve()):base.digest(p) for p in paths},'source input changed'
        base.write(stage/'manifest.json',{'schema_version':1,'product':'blender','version':list(bpy.app.version),
            'build_hash':bpy.app.build_hash.decode(),'binary_sha256':base.digest(bpy.app.binary_path),
            'process_id':os.getpid(),'background':False,'input_hashes':hashes,'classes':3,'forms_per_class':10,'runs':records,
            'input_rule':'Only authored scene channels, topology, selection, locks, settings and sharing enter setup. No measured output enters an input.',
            'product_acceptance':'unrun'})
        stage.rename(args.output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--samples',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    def start():
        try:capture(args)
        except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
        sys.stdout.flush();sys.stderr.flush();os._exit(0)
    bpy.app.timers.register(start,first_interval=.5)

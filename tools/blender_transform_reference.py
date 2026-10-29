#!/usr/bin/env python3
"""Capture the fixed transform suite in Blender. Never used by product runtime."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import traceback

import bmesh
import bpy
from mathutils import Euler

BASE_PATH=Path(__file__).with_name('blender_selection_reference.py')
spec=importlib.util.spec_from_file_location('selection_reference',BASE_PATH)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
OPERATORS=['translate','rotate','resize']


def authored_mesh(suite,run):
    mesh=copy.deepcopy(suite['mesh'])
    if run['context'].get('hide_all'):
        mesh['hidden']={key:list(range(len(mesh[key]))) for key in ['vertices','edges','faces']}
    return mesh


def create(suite,run):
    obj=base.create(authored_mesh(suite,run),run)
    obj.active_material_index=suite['mesh']['active_material_index']
    scene=bpy.context.scene;environment=suite['environment'];profile=suite['profiles'][run['context']['profile']]
    obj.location=profile['location'];obj.rotation_euler=profile['rotation'];obj.scale=profile['scale']
    if profile['parent'] is not None:
        parent=bpy.data.objects.new('TransformParent',None);bpy.context.collection.objects.link(parent)
        for prop,key in [('location','location'),('rotation_euler','rotation'),('scale','scale')]:setattr(parent,prop,profile['parent'][key])
        obj.parent=parent
    scene.cursor.location=environment['cursor_location'];scene.cursor.rotation_mode='XYZ';scene.cursor.rotation_euler=environment['cursor_rotation']
    settings=scene.tool_settings;settings.transform_pivot_point=run['context']['pivot']
    settings.use_transform_correct_face_attributes=run['context']['correct_face_attributes']
    settings.use_transform_correct_keep_connected=run['context']['keep_connected']
    settings.use_mesh_automerge=False;settings.use_mesh_automerge_and_split=False
    obj.data.use_mirror_x=run['context']['mirror_x'];obj.data.use_mirror_y=False;obj.data.use_mirror_z=False;obj.data.use_mirror_topology=run['context']['mirror_topology']
    area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');region=next(r for r in area.regions if r.type=='WINDOW')
    view=area.spaces.active.region_3d;view.view_rotation=Euler(environment['view_rotation'],'XYZ').to_quaternion()
    view.view_location=environment['view_location'];view.view_distance=environment['view_distance'];view.view_perspective=environment['view_perspective']
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    bpy.context.view_layer.update()
    with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):
        view.update()
    return obj,area,region


def snapshot(obj,area):
    state=base.snapshot(obj);bm=bmesh.from_edit_mesh(obj.data)
    state['active_material_index']=obj.active_material_index
    vertex_layer=bm.verts.layers.int[base.LAYERS[0]]
    state['world_vertices']={f'v{v[vertex_layer]:06}':list(obj.matrix_world@v.co) for v in bm.verts}
    temporary=bpy.data.meshes.new('TransformNormalSnapshot')
    try:
        bm.to_mesh(temporary);temporary.update();temporary.calc_loop_triangles()
        ids=temporary.attributes[base.LAYERS[2]]
        state['normals']={'faces':{},'corners':{}}
        corners=temporary.corner_normals
        for f in temporary.polygons:
            id=f'f{ids.data[f.index].value:06}'
            state['normals']['faces'][id]=list(f.normal)
            state['normals']['corners'][id]=[list(corners[i].vector) for i in f.loop_indices]
    finally:bpy.data.meshes.remove(temporary)
    def transform(o):
        return {'location':list(o.location),'rotation':list(o.rotation_euler),'scale':list(o.scale),'matrix_world':[list(row) for row in o.matrix_world]}
    state['objects']={'target':transform(obj),'parent':None if obj.parent is None else transform(obj.parent)}
    view=area.spaces.active.region_3d;settings=bpy.context.scene.tool_settings;cursor=bpy.context.scene.cursor
    state['environment']={'cursor_location':list(cursor.location),'cursor_rotation':list(cursor.rotation_euler),'pivot':settings.transform_pivot_point,
        'view_rotation':list(view.view_rotation),'view_location':list(view.view_location),'view_distance':view.view_distance,'view_perspective':view.view_perspective,
        'view_matrix':[list(row) for row in view.view_matrix],'correct_face_attributes':settings.use_transform_correct_face_attributes,'keep_connected':settings.use_transform_correct_keep_connected,
        'mirror_x':obj.data.use_mirror_x,'mirror_topology':obj.data.use_mirror_topology,
        'region_size':[[r.width,r.height] for r in area.regions if r.type=='WINDOW'][0]}
    return state


def properties():
    result={}
    for name in OPERATORS:
        props={}
        for p in getattr(bpy.ops.transform,name).get_rna_type().properties:
            if p.identifier=='rna_type':continue
            item={'type':p.type,'description':p.description}
            for key in ['array_length','hard_min','hard_max','is_enum_flag']:
                if hasattr(p,key):item[key]=getattr(p,key)
            if p.type=='ENUM' and p.is_enum_flag:item['default']=sorted(p.default_flag)
            elif getattr(p,'is_array',False):item['default']=list(p.default_array)
            elif hasattr(p,'default'):item['default']=p.default
            if p.type=='ENUM':item['enum']=[v.identifier for v in p.enum_items]
            props[p.identifier]=item
        result[name]=props
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--suite',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',action='append',default=[],dest='case_ids')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);suite=json.loads(args.suite.read_text());build=bpy.app.build_hash.decode()
    assert not bpy.app.background,'viewport transforms require an actual initialized window/GPU context'
    assert list(bpy.app.version)==suite['reference']['version'] and build==suite['reference']['build_hash']
    assert not args.output.exists(),'never overwrite reference capture';assert len(suite['runs'])==1203
    runs=suite['runs']
    if args.case_ids:
        assert set(args.case_ids)<={r['id'] for r in runs},'unknown run ID'
        runs=[r for r in runs if r['id'] in args.case_ids]
    assert len({r['id'] for r in runs})==len(runs)
    files=[args.suite,Path(__file__),BASE_PATH];inputs={str(p.resolve()):base.digest(p) for p in files}
    args.output.parent.mkdir(parents=True,exist_ok=True);started=datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix='formora-transform-stage-',dir=args.output.parent) as directory:
        stage=Path(directory)/'capture';stage.mkdir();records=[]
        for i,run in enumerate(runs):
            obj,area,region=create(suite,run)
            if i==0:base.write(stage/'operator-properties.json',properties())
            before=snapshot(obj,area);parameters=copy.deepcopy(run['parameters']);clock_before=time.time_ns()
            if 'snap_elements' in parameters:parameters['snap_elements']=set(parameters['snap_elements'])
            try:
                with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):
                    status=sorted(getattr(bpy.ops.transform,run['operator'])(**parameters))
                result={'status':status,'error':None}
            except RuntimeError as error:
                if run['label']!='singular target':raise
                result={'status':['ERROR'],'error':str(error)}
            clock_after=time.time_ns();after=snapshot(obj,area)
            data={'run_id':run['id'],'operator':run['operator'],'parameters':run['parameters'],'context':run['context'],'repeat_policy':run['repeat_policy'],
                  'before':before,'after':after,'result':result,'clock_before_ns':clock_before,'clock_after_ns':clock_after}
            file=run['id']+'.json';base.write(stage/file,data);records.append({'id':run['id'],'file':file,'sha256':base.digest(stage/file),'status':result['status'],'repeat_policy':run['repeat_policy']})
            if (i+1)%100==0:print(json.dumps({'captured':i+1,'total':len(runs)}),flush=True)
        assert inputs=={str(p.resolve()):base.digest(p) for p in files},'capture inputs changed'
        base.write(stage/'manifest.json',{'schema_version':1,'product':'blender','version':list(bpy.app.version),'build_hash':build,'process_id':os.getpid(),
            'scope':'focused' if args.case_ids else 'complete_1203_authored_transform_cases','started_utc':started,'platform':platform.platform(),'binary_sha256':base.digest(bpy.app.binary_path),
            'command_line':sys.argv,'background':bpy.app.background,
            'suite_sha256':base.digest(args.suite),'adapter_sha256':base.digest(__file__),'base_adapter_sha256':base.digest(BASE_PATH),'operator_properties_sha256':base.digest(stage/'operator-properties.json'),
            'runs':records,'product_acceptance':'unrun','random_acceptance':'support_only; RNG sequence and distribution unrun'})
        stage.rename(args.output)
    print(json.dumps({'captured':len(records),'product_acceptance':'unrun'}),flush=True)


if __name__=='__main__':
    try:
        main()
    except BaseException:
        traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
    # This dedicated factory-startup process runs its script before the event
    # loop. A scheduled UI quit can stay pending there. All output is committed
    # before this point; close only this harness process without saving a scene.
    sys.stdout.flush();sys.stderr.flush();os._exit(0)

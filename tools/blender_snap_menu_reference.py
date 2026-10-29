#!/usr/bin/env python3
"""Capture direct snapping in a dedicated frozen native Blender process."""
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
import traceback

import bmesh
import bpy

ADAPTER = Path(__file__).with_name('blender_transform_reference.py')
spec = importlib.util.spec_from_file_location('transform_reference', ADAPTER)
transform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transform)
base = transform.base
OPERATORS = ['snap_selected_to_grid','snap_selected_to_cursor','snap_selected_to_active',
             'snap_cursor_to_grid','snap_cursor_to_selected','snap_cursor_to_active','snap_cursor_to_center']


def physical_factor(context):
    return 1.0 if context['unit_system']=='NONE' else context['unit_scale_length']


def select_mesh(obj, suite, run):
    bm=bmesh.from_edit_mesh(obj.data)
    bm.select_mode=set(run['initial_mode'])
    collections=[bm.verts,bm.edges,bm.faces]
    mesh=transform.authored_mesh(suite,run)
    for elements in collections:
        elements.ensure_lookup_table()
        for item in elements:
            item.hide_set(False)
            item.select=False
    for elements,name in zip(collections,['vertices','edges','faces']):
        layer=elements.layers.int[base.LAYERS[['vertices','edges','faces'].index(name)]]
        by_id={item[layer]:item for item in elements}
        for index in mesh['hidden'][name]:by_id[index].hide_set(True)
    bm.select_history.clear();bm.faces.active=None
    elements=collections[base.DOMAINS.index(run['seed']['domain'])]
    layer=elements.layers.int[base.LAYERS[base.DOMAINS.index(run['seed']['domain'])]]
    by_id={item[layer]:item for item in elements}
    for index in run['seed']['indices']:
        item=by_id[index];item.select_set(True);bm.select_history.add(item)
        if run['seed']['domain']=='FACE':bm.faces.active=item
    bm.select_flush_mode();bm.select_history.validate()
    if run['context']['history']=='clear':bm.select_history.clear()
    active=run['context']['active_face_override']
    if active!='preserve':
        layer=bm.faces.layers.int[base.LAYERS[2]]
        bm.faces.active=None if active is None else next(face for face in bm.faces if face[layer]==active)
    bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)


def create(suite,run):
    obj,area,region=transform.create(suite,run)
    obj.name='target';objects={'target':obj}
    if obj.parent is not None:obj.parent.name='parent';objects['parent']=obj.parent
    context=run['context'];scene=bpy.context.scene;settings=scene.tool_settings
    if context['multi_object'] or run['mode']=='OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
        group_names=[group.name for group in obj.vertex_groups]
        data=obj.data if context['linked_data'] else obj.data.copy()
        other=bpy.data.objects.new('secondary',data);bpy.context.collection.objects.link(other)
        # Mesh copies and linked meshes can already carry the group definitions.
        # Freeze the names before creating groups so a shared list cannot grow
        # while we iterate over it.
        if not other.vertex_groups:
            for name in group_names:other.vertex_groups.new(name=name)
        assert [group.name for group in other.vertex_groups]==group_names
        assert [group.name for group in obj.vertex_groups]==group_names
        other.active_material_index=obj.active_material_index
        for attr,key in [('location','location'),('rotation_euler','rotation'),('scale','scale')]:
            setattr(other,attr,suite['object_inputs']['secondary'][key])
        objects['secondary']=other
        child=bpy.data.objects.new('child',None);bpy.context.collection.objects.link(child);child.parent=obj
        for attr,key in [('location','location'),('rotation_euler','rotation'),('scale','scale')]:
            setattr(child,attr,suite['object_inputs']['child'][key])
        objects['child']=child
        if context['secondary_parent'] is not None:other.parent=objects[context['secondary_parent']]
        for name,item in objects.items():item.select_set(name in context['object_selection'])
        bpy.context.view_layer.objects.active=objects.get(context['active_object'])
        if run['mode']=='EDIT_MESH':
            assert bpy.context.view_layer.objects.active is not None
            bpy.ops.object.mode_set(mode='EDIT')
    else:
        obj.select_set(True);bpy.context.view_layer.objects.active=obj
    assert bpy.context.mode==run['mode'],(run['id'],bpy.context.mode,run['mode'])
    if run['mode']=='EDIT_MESH':
        settings.mesh_select_mode=tuple(domain in run['initial_mode'] for domain in base.DOMAINS)
        seen=set()
        for item in objects.values():
            if item.type=='MESH' and item.mode=='EDIT' and item.data.as_pointer() not in seen:
                select_mesh(item,suite,run);seen.add(item.data.as_pointer())
    obj.lock_location=context['lock_location'];obj.lock_rotation=context['lock_rotation']
    settings.use_transform_skip_children=context['skip_children']
    settings.use_transform_data_origin=context['origins_only']
    settings.use_keyframe_insert_auto=False
    settings.use_transform_pivot_point_align=False
    scene.cursor.location=context['cursor_location'];scene.cursor.rotation_euler=context['cursor_rotation']
    scene.unit_settings.system=context['unit_system'];scene.unit_settings.scale_length=context['unit_scale_length']
    area.spaces.active.overlay.grid_scale=context['grid_spacing']
    bpy.context.view_layer.update()
    with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):
        area.spaces.active.region_3d.update()
    return objects,area,region


def mesh_state(obj,factor):
    edit=obj.mode=='EDIT'
    bm=bmesh.from_edit_mesh(obj.data) if edit else bmesh.new()
    if not edit:bm.from_mesh(obj.data)
    try:
        bm.normal_update();collections=[bm.verts,bm.edges,bm.faces]
        layers=[items.layers.int[name] for items,name in zip(collections,base.LAYERS)]
        key=lambda item:base.logical_id(item,layers)
        geometry={'vertices':{key(v):list(v.co) for v in bm.verts},
            'edges':{key(e):sorted(key(v) for v in e.verts) for e in bm.edges},
            'faces':{key(f):[key(v) for v in f.verts] for f in bm.faces},
            'face_smooth':{key(f):f.smooth for f in bm.faces},
            'face_materials':{key(f):f.material_index for f in bm.faces},
            'edge_seams':{key(e):e.seam for e in bm.edges},
            'material_slots':[m.name for m in obj.data.materials],
            'uv_layers':{name:{key(f):[list(loop[layer].uv) for loop in f.loops] for f in bm.faces}
                         for name in bm.loops.layers.uv.keys() for layer in [bm.loops.layers.uv[name]]},
            'uv_layer_order':[layer.name for layer in obj.data.uv_layers],
            'active_uv_index':obj.data.uv_layers.active_index}
        deform=bm.verts.layers.deform.active
        groups={'names':[group.name for group in obj.vertex_groups],
                'weights':{key(v):{obj.vertex_groups[i].name:weight for i,weight in v[deform].items()} if deform else {} for v in bm.verts}}
        temporary=bpy.data.meshes.new('SnapNormalSnapshot')
        try:
            bm.to_mesh(temporary);temporary.update();temporary.calc_loop_triangles()
            ids=temporary.attributes[base.LAYERS[2]];corners=temporary.corner_normals
            normals={'faces':{},'corners':{}}
            for face in temporary.polygons:
                id=f'f{ids.data[face.index].value:06}'
                normals['faces'][id]=list(face.normal)
                normals['corners'][id]=[list(corners[index].vector) for index in face.loop_indices]
        finally:bpy.data.meshes.remove(temporary)
        world={key(v):list(obj.matrix_world@v.co) for v in bm.verts}
        return {'geometry':geometry,'groups':groups,
                'selected':{domain:sorted(key(item) for item in items if item.select) for domain,items in zip(base.DOMAINS,collections)},
                'hidden':{domain:sorted(key(item) for item in items if item.hide) for domain,items in zip(base.DOMAINS,collections)},
                'mode':[domain for domain,on in zip(base.DOMAINS,bpy.context.tool_settings.mesh_select_mode) if on] if edit else [],
                'history':[{'domain':'VERT' if isinstance(item,bmesh.types.BMVert) else 'EDGE' if isinstance(item,bmesh.types.BMEdge) else 'FACE','id':key(item)} for item in bm.select_history] if edit else [],
                'active_face':key(bm.faces.active) if edit and bm.faces.active is not None else None,
                'flags':{'mirror_x':obj.data.use_mirror_x,'mirror_y':obj.data.use_mirror_y,
                         'mirror_z':obj.data.use_mirror_z,'mirror_topology':obj.data.use_mirror_topology},
                'active_material_index':obj.active_material_index,'normals':normals,'world_vertices':world,
                'vertices_metres':{id:[v*factor for v in p] for id,p in geometry['vertices'].items()},
                'world_vertices_metres':{id:[v*factor for v in p] for id,p in world.items()}}
    finally:
        if not edit:bm.free()


def snapshot(objects,area,run):
    factor=physical_factor(run['context']);scene=bpy.context.scene;settings=scene.tool_settings
    names={item.as_pointer():name for name,item in objects.items()}
    matrix=lambda m:[list(row) for row in m]
    frames={}
    for name,item in sorted(objects.items()):
        frames[name]={'type':item.type,'mode':item.mode,'parent':None if item.parent is None else names[item.parent.as_pointer()],
            'location':list(item.location),'rotation':list(item.rotation_euler),'rotation_mode':item.rotation_mode,
            'scale':list(item.scale),'matrix_world':matrix(item.matrix_world),'matrix_local':matrix(item.matrix_local),
            'matrix_basis':matrix(item.matrix_basis),'matrix_parent_inverse':matrix(item.matrix_parent_inverse),
            'delta_location':list(item.delta_location),'delta_rotation':list(item.delta_rotation_euler),'delta_scale':list(item.delta_scale),
            'lock_location':list(item.lock_location),'lock_rotation':list(item.lock_rotation),'lock_scale':list(item.lock_scale),
            'selected':item.select_get(),'animation_data':item.animation_data is not None,
            'constraints':len(item.constraints),'modifiers':len(item.modifiers)}
    meshes={name:mesh_state(item,factor) for name,item in sorted(objects.items()) if item.type=='MESH'}
    shared={}
    for name,item in objects.items():
        if item.type=='MESH':shared.setdefault(item.data.as_pointer(),[]).append(name)
    view=area.spaces.active.region_3d
    return {'mode':bpy.context.mode,'objects':frames,'meshes':meshes,
        'sharing':sorted(sorted(group) for group in shared.values()),
        'active_object':None if bpy.context.view_layer.objects.active is None else names[bpy.context.view_layer.objects.active.as_pointer()],
        'cursor':{'location':list(scene.cursor.location),'rotation':list(scene.cursor.rotation_euler),
                  'rotation_mode':scene.cursor.rotation_mode,'matrix':matrix(scene.cursor.matrix)},
        'cursor_metres':[v*factor for v in scene.cursor.location],'physical_metres_factor':factor,
        'settings':{'pivot':settings.transform_pivot_point,'skip_children':settings.use_transform_skip_children,
            'correct_face_attributes':settings.use_transform_correct_face_attributes,
            'keep_connected':settings.use_transform_correct_keep_connected,
            'automerge':settings.use_mesh_automerge,'automerge_and_split':settings.use_mesh_automerge_and_split,
            'origins_only':settings.use_transform_data_origin,'autokey':settings.use_keyframe_insert_auto,
            'locations_only':settings.use_transform_pivot_point_align,'unit_system':scene.unit_settings.system,
            'unit_scale_length':scene.unit_settings.scale_length,'grid_spacing':area.spaces.active.overlay.grid_scale,
            'grid_subdivisions':area.spaces.active.overlay.grid_subdivisions,
            'view_perspective':view.view_perspective,'view_rotation':list(view.view_rotation),
            'view_location':list(view.view_location),'view_distance':view.view_distance,
            'view_matrix':matrix(view.view_matrix),'region_size':[[r.width,r.height] for r in area.regions if r.type=='WINDOW'][0]}}


def properties():
    result={}
    for name in OPERATORS:
        props={}
        for p in getattr(bpy.ops.view3d,name).get_rna_type().properties:
            if p.identifier=='rna_type':continue
            value={'type':p.type,'description':p.description}
            for field in ['array_length','hard_min','hard_max','is_enum_flag']:
                if hasattr(p,field):value[field]=getattr(p,field)
            if p.type=='ENUM':value['enum']=[item.identifier for item in p.enum_items]
            if hasattr(p,'default_array') and getattr(p,'array_length',0):value['default']=list(p.default_array)
            elif hasattr(p,'default'):value['default']=p.default
            props[p.identifier]=value
        result[name]=props
    return result


def capture(args):
    suite=json.loads(args.suite.read_text());assert len(suite['runs'])==1672
    assert not bpy.app.background and list(bpy.app.version)==suite['reference']['version']
    assert bpy.app.build_hash.decode()==suite['reference']['build_hash']
    assert not args.output.exists(),'refuse existing output'
    paths=[args.suite,Path(__file__),ADAPTER,transform.BASE_PATH]
    inputs={str(p.resolve()):base.digest(p) for p in paths}
    runs=suite['runs']
    if args.case_ids:
        assert set(args.case_ids)<={r['id'] for r in runs}
        runs=[r for r in runs if r['id'] in args.case_ids]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='formora-snap-stage-',dir=args.output.parent) as temporary:
        stage=Path(temporary)/'capture';stage.mkdir();records=[]
        base.write(stage/'operator-properties.json',properties())
        for index,run in enumerate(runs):
            objects,area,region=create(suite,run);before=snapshot(objects,area,run)
            op=getattr(bpy.ops.view3d,run['operator'])
            with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):
                assert op.poll(),('invalid source setup',run['id'])
                try:result={'status':sorted(op(**copy.deepcopy(run['parameters']))),'error':None}
                except RuntimeError as error:result={'status':['ERROR'],'error':str(error)}
            bpy.context.view_layer.update();after=snapshot(objects,area,run)
            file=run['id']+'.json';base.write(stage/file,{'run':run,'before':before,'after':after,'result':result})
            records.append({'id':run['id'],'file':file,'sha256':base.digest(stage/file),'status':result['status']})
            if (index+1)%100==0:print(json.dumps({'captured':index+1,'total':len(runs)}),flush=True)
        assert inputs=={str(p.resolve()):base.digest(p) for p in paths},'capture input changed'
        base.write(stage/'manifest.json',{'schema_version':1,'product':'blender','version':list(bpy.app.version),
            'build_hash':bpy.app.build_hash.decode(),'process_id':os.getpid(),'binary_sha256':base.digest(bpy.app.binary_path),
            'scope':'focused_diagnostic' if args.case_ids else 'complete_1672_authored_snap_menu_cases',
            'captured_utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),
            'command_line':sys.argv,'background':bpy.app.background,'input_hashes':inputs,
            'operator_properties_sha256':base.digest(stage/'operator-properties.json'),'runs':records,
            'product_acceptance':'unrun'})
        stage.rename(args.output)
    print(json.dumps({'captured':len(records),'product_acceptance':'unrun'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',action='append',default=[],dest='case_ids')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    def start():
        try:capture(args)
        except BaseException:
            traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
        sys.stdout.flush();sys.stderr.flush();os._exit(0)
    bpy.app.timers.register(start,first_interval=0.5)

#!/usr/bin/env python3
"""Bind raw rotation captures to authored inputs and compare native processes."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

from compare_selection_reference import require, validate_state
from compare_snap_menu_reference import f32, floats, tree, selection_input, IDENTITY, snapped
from compare_transform_reference import finite
from generate_snap_rotation_cases import author, channels

ROOT=Path(__file__).resolve().parents[1]
SELECTION=['geometry','groups','selected','hidden','mode','history','active_face']
ORDERS={'XYZ':([0,1,2],False),'XZY':([0,2,1],True),'YXZ':([1,0,2],True),
        'YZX':([1,2,0],False),'ZXY':([2,0,1],False),'ZYX':([2,1,0],True)}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(values):
    d=f32(values[0]*values[0])
    for v in values[1:]:d=f32(d+f32(v*v))
    require(d>0.,'zero authored normalization input')
    factor=f32(1./f32(math.sqrt(d)))
    return [f32(v*factor) for v in values]


def rotation_matrix(data):
    """Evaluate authored channels; never read a captured matrix or result."""
    mode=data['mode'];r=[[0.]*3 for _ in range(3)]
    if mode in ORDERS:
        (i,j,k),parity=ORDERS[mode];e=[f32(v) for v in data['euler']]
        ti,tj,th=[(-e[a] if parity else e[a]) for a in [i,j,k]]
        ci,cj,ch=math.cos(ti),math.cos(tj),math.cos(th)
        si,sj,sh=math.sin(ti),math.sin(tj),math.sin(th)
        cc,cs,sc,ss=ci*ch,ci*sh,si*ch,si*sh
        r[i][i]=f32(cj*ch);r[i][j]=f32(sj*sc-cs);r[i][k]=f32(sj*cc+ss)
        r[j][i]=f32(cj*sh);r[j][j]=f32(sj*ss+cc);r[j][k]=f32(sj*cs-sc)
        r[k][i]=f32(-sj);r[k][j]=f32(cj*si);r[k][k]=f32(cj*ci)
    elif mode=='QUATERNION':
        w,x,y,z=[math.sqrt(2)*v for v in normalized([f32(v) for v in data['quaternion_wxyz']])]
        r=[[f32(1-y*y-z*z),f32(x*y-w*z),f32(x*z+w*y)],
           [f32(x*y+w*z),f32(1-x*x-z*z),f32(y*z-w*x)],
           [f32(x*z-w*y),f32(y*z+w*x),f32(1-x*x-y*y)]]
    else:
        require(mode=='AXIS_ANGLE','unknown rotation mode')
        angle,*axis=[f32(v) for v in data['axis_angle']];x,y,z=normalized(axis)
        s,c=f32(math.sin(angle)),f32(math.cos(angle));t=f32(1-c)
        xx,xy,xz,yy,yz,zz=[f32(f32(a*b)*t) for a,b in [(x,x),(x,y),(x,z),(y,y),(y,z),(z,z)]]
        sx,sy,sz=[f32(a*s) for a in [x,y,z]]
        r=[[f32(xx+c),f32(xy-sz),f32(xz+sy)],
           [f32(xy+sz),f32(yy+c),f32(yz-sx)],
           [f32(xz-sy),f32(yz+sx),f32(zz+c)]]
    return r


def matrix(profile,rotation):
    r=rotation_matrix(rotation)
    return [[f32(r[i][j]*f32(profile['scale'][j])) for j in range(3)]+[f32(profile['location'][i])] for i in range(3)]+[[0.,0.,0.,1.]]


def compose(a,b):
    # The pinned M1 matrix path uses paired f32 SIMD products and sums.
    return [[f32(f32(f32(a[i][0]*b[0][j])+f32(a[i][1]*b[1][j]))+
                 f32(f32(a[i][2]*b[2][j])+f32(a[i][3]*b[3][j]))) for j in range(4)] for i in range(4)]


def world_point(w,p):
    # Pinned mathutils rounds products before its double accumulator.
    return [f32(sum(f32(w[i][j]*p[j]) for j in range(3))+w[i][3]) for i in range(3)]


def bind_initial(suite,run,state):
    c=run['context'];profile=suite['profiles'][c['profile']]
    profiles={'target':profile,**suite['object_inputs']}
    parents={'target':'parent' if profile['parent'] is not None else None,'secondary':None,'child':'target'}
    if parents['target']:profiles['parent']=profile['parent'];parents['parent']=None
    require(set(state['objects'])==set(profiles)==set(state['rotation_channels']),'authored object set differs')
    require(state['active_object']=='target' and state['mode']==run['mode'],'authored mode/active differs')
    require(state['sharing']==[['secondary','target']],'authored shared data differs')
    tree(floats(run['rotations']['cursor']),state['cursor_channels'],'cursor channels',0.)
    tree(floats(c['cursor_location']),state['cursor']['location'],'cursor location',0.)
    cp={'location':c['cursor_location'],'scale':[1.,1.,1.]}
    tree(matrix(cp,run['rotations']['cursor']),state['cursor']['matrix'],'authored cursor matrix')
    authored={};basis={}
    for name,p in profiles.items():
        rot=run['rotations']['objects'] if name in ['target','secondary'] else {'mode':'XYZ','euler':p['rotation'],'quaternion_wxyz':[1.,0.,0.,0.],'axis_angle':[0.,0.,1.,0.]}
        authored[name]=rot;basis[name]=matrix(p,rot)
    def world(name):
        return basis[name] if parents[name] is None else compose(world(parents[name]),basis[name])
    for name,p in profiles.items():
        o=state['objects'][name];rot=authored[name];primary=name in ['target','secondary']
        expected={**floats(rot),'lock_rotation':c['lock_rotation'] if primary else [False]*3,
                  'lock_rotation_w':run['rotations']['lock_rotation_w'] if primary else False,
                  'lock_rotations_4d':run['rotations']['lock_rotations_4d'] if primary else False,
                  'delta_quaternion_wxyz':[1.,0.,0.,0.],'delta_euler':[0.,0.,0.]}
        tree(expected,state['rotation_channels'][name],name+'/channels',0.)
        require(o['rotation_mode']==rot['mode'] and o['parent']==parents[name],'authored mode/parent differs')
        require(o['type']==('MESH' if primary else 'EMPTY'),'authored kind differs')
        require(o['mode']==('EDIT' if name=='target' and run['mode']=='EDIT_MESH' else 'OBJECT'),'authored edit owner differs')
        require(o['selected']==primary,'authored selected object differs')
        for field in ['location','scale']:tree([f32(v) for v in p[field]],o[field],name+'/'+field,0.)
        tree(floats(rot['euler']),o['rotation'],name+'/stored Euler',0.)
        for field in ['matrix_basis','matrix_local']:tree(basis[name],o[field],name+'/'+field)
        tree(IDENTITY,o['matrix_parent_inverse'],name+'/parent inverse',0.)
        tree(world(name),o['matrix_world'],name+'/authored world')
        require(not o['animation_data'] and o['constraints']==o['modifiers']==0,'unexpected animation/constraints/modifiers')
        for field,values in [('delta_location',[0.]*3),('delta_rotation',[0.]*3),('delta_scale',[1.]*3),
                             ('lock_location',[False]*3),('lock_scale',[False]*3)]:tree(values,o[field],name+'/'+field,0.)
    require(set(state['meshes'])=={'target','secondary'},'authored meshes differ')
    edit=run['mode']=='EDIT_MESH';expected=selection_input(suite['mesh'],run,edit)
    for name,m in state['meshes'].items():
        tree(expected,{k:m[k] for k in SELECTION},name+'/authored mesh',0.)
        require(m['data_edit_mode']==edit,'authored shared edit data differs')
        for id,p in expected['geometry']['vertices'].items():
            tree(world_point(world(name),p),m['world_vertices'][id],name+'/authored world vertex/'+id)


def validate_run(suite,run,data):
    require(set(data)=={'run','before','after','result'},'capture fields differ')
    require(data['run']==run,'authored request differs');finite(data)
    bind_initial(suite,run,data['before'])
    before,after=data['before'],data['after']
    require(data['result']=={'status':['FINISHED'],'error':None},'native operator did not finish')
    for state in [before,after]:
        require(set(state)=={'mode','objects','meshes','sharing','active_object','cursor','cursor_metres',
                            'physical_metres_factor','settings','rotation_channels','cursor_channels'},'snapshot fields differ')
        require(state['physical_metres_factor']==1.,'physical units differ')
        require(set(state['rotation_channels'])==set(state['objects']),'rotation identity differs')
        evaluated={}
        for name,o in state['objects'].items():
            require(set(o)=={'type','mode','parent','location','rotation','rotation_mode','scale','matrix_world','matrix_local',
                            'matrix_basis','matrix_parent_inverse','delta_location','delta_rotation','delta_scale','lock_location',
                            'lock_rotation','lock_scale','selected','animation_data','constraints','modifiers'},'object fields differ')
            channels=state['rotation_channels'][name]
            require(set(channels)=={'mode','euler','quaternion_wxyz','axis_angle','lock_rotation','lock_rotation_w',
                                   'lock_rotations_4d','delta_quaternion_wxyz','delta_euler'},'rotation fields differ')
            require(channels['mode']==o['rotation_mode'] and channels['euler']==o['rotation'],'stored rotation disagrees')
            require(channels['lock_rotation']==o['lock_rotation'],'stored rotation locks disagree')
            evaluated[name]=matrix(o,channels)
            for field in ['matrix_basis','matrix_local']:tree(evaluated[name],o[field],'evaluated stored channels/'+name+'/'+field)
            tree(IDENTITY,o['matrix_parent_inverse'],'preserved parent inverse',0.)
        def actual_world(name):
            parent=state['objects'][name]['parent']
            return evaluated[name] if parent is None else compose(actual_world(parent),evaluated[name])
        for name,o in state['objects'].items():tree(actual_world(name),o['matrix_world'],'evaluated world/'+name)
        require(set(state['cursor'])=={'location','rotation','rotation_mode','matrix'},'cursor fields differ')
        require(set(state['cursor_channels'])=={'mode','euler','quaternion_wxyz','axis_angle'},'cursor channel fields differ')
        require(state['cursor']['rotation_mode']==state['cursor_channels']['mode'],'cursor mode disagrees')
        tree(state['cursor_channels']['euler'],state['cursor']['rotation'],'stored cursor Euler',0.)
        tree(matrix({'location':state['cursor']['location'],'scale':[1.]*3},state['cursor_channels']),state['cursor']['matrix'],'evaluated cursor matrix')
        tree(state['cursor']['location'],state['cursor_metres'],'physical cursor',0.)
        for name,m in state['meshes'].items():
            require(set(m)==set(SELECTION)|{'data_edit_mode','active_material_index','flags','normals','world_vertices','vertices_metres','world_vertices_metres'},'mesh fields differ')
            selected={k:m[k] for k in SELECTION}
            if not m['data_edit_mode']:selected={**selected,'mode':run['initial_mode']}
            validate_state(selected)
            for id,p in m['geometry']['vertices'].items():
                tree(p,m['vertices_metres'][id],'local physical',0.)
                actual=world_point(state['objects'][name]['matrix_world'],p)
                tree(actual,m['world_vertices'][id],'world geometry',0.)
                tree(actual,m['world_vertices_metres'][id],'world physical',0.)
            for id,face in m['geometry']['faces'].items():
                require(len(m['normals']['corners'][id])==len(face),'corner normal count differs')
                for n in [m['normals']['faces'][id],*m['normals']['corners'][id]]:
                    require(len(n)==3 and (sum(v*v for v in n)<=1e-12 or abs(math.sqrt(sum(v*v for v in n))-1)<=1e-6),'invalid normal')
        a,b=state['meshes']['target'],state['meshes']['secondary']
        for field in SELECTION+['data_edit_mode','normals','flags']:tree(a[field],b[field],'actual shared data/'+field,0.)
    require(before['sharing']==after['sharing'] and before['settings']==after['settings'],'operation changed sharing/settings')
    require(before['active_object']==after['active_object'] and before['mode']==after['mode'],'operation changed context')
    for name,old in before['rotation_channels'].items():
        new=after['rotation_channels'][name]
        for key in ['mode','lock_rotation','lock_rotation_w','lock_rotations_4d','delta_euler','delta_quaternion_wxyz']:
            require(old[key]==new[key],'operation changed authored mode/lock/delta')
        preserve=run['operator']!='snap_selected_to_cursor' or not run['parameters']['use_rotation'] or run['mode']=='EDIT_MESH' or name not in ['target','secondary']
        if preserve:tree(old,new,'unchanged object channels',0.)
        else:
            mode=old['mode'];active='quaternion_wxyz' if mode=='QUATERNION' else 'axis_angle' if mode=='AXIS_ANGLE' else 'euler'
            for field in ['euler','quaternion_wxyz','axis_angle']:
                if field!=active:tree(old[field],new[field],'inactive channels',0.)
            locks=old['lock_rotation'];locked=[old['lock_rotation_w'],*locks] if active in ['quaternion_wxyz','axis_angle'] else locks
            for index,on in enumerate(locked):
                if on:require(old[active][index]==new[active][index],'locked channel changed')
    if run['operator'].startswith('snap_selected'):
        tree(before['cursor_channels'],after['cursor_channels'],'unchanged cursor channels',0.)
        tree(before['cursor'],after['cursor'],'unchanged cursor',0.)
    elif run['operator']=='snap_cursor_to_center':
        tree(IDENTITY,after['cursor']['matrix'],'world origin matrix')
        tree([0.]*3,after['cursor']['location'],'world origin location',0.)
    else:
        tree(before['cursor_channels'],after['cursor_channels'],'cursor-only unchanged rotation',0.)
        if run['operator']=='snap_cursor_to_grid':tree(snapped(before['cursor']['location'],.75),after['cursor']['location'],'analytic grid',0.)
    for name,m in before['meshes'].items():
        for field in ['groups','selected','hidden','mode','history','active_face','data_edit_mode','flags','active_material_index']:
            tree(m[field],after['meshes'][name][field],'unchanged mesh data/'+field,0.)
        for field in m['geometry']:
            if field!='vertices' or run['mode']=='OBJECT':tree(m['geometry'][field],after['meshes'][name]['geometry'][field],'unchanged geometry/'+field,0.)


def compare_case(suite,run,first,second):
    for data in [first,second]:validate_run(suite,run,data)
    tree(first,second,path=run['id'])


def provenance_inputs(folder,manifest,suite_path):
    source_path=ROOT/'baseline/sources/snap-rotation/manifest.json'
    source=json.loads(source_path.read_text())
    paths=[suite_path.resolve(),ROOT/'tools/blender_snap_rotation_reference.py',ROOT/'tools/blender_snap_menu_reference.py',
           ROOT/'tools/blender_transform_reference.py',ROOT/'tools/blender_selection_reference.py',
           ROOT/'tools/generate_snap_rotation_cases.py',ROOT/'tools/generate_snap_menu_cases.py',
           ROOT/'tools/generate_mesh_transform_cases.py',ROOT/'docs/contracts/snap-rotation-baseline.md',
           ROOT/'baseline/lock.json',source_path]
    for name in source['reused_source_manifests']:
        path=ROOT/name;paths.append(path);value=json.loads(path.read_text())
        for row in value['files'] if 'files' in value else value['source_files']:paths.append(path.parent/row['file'])
    for row in source['files']:paths.append(source_path.parent/row['file'])
    expected={p.relative_to(ROOT).as_posix():p for p in paths}
    captured=manifest['input_hashes'];require(len(captured)==len(expected),'input hash set size differs')
    roots=set()
    for relative,path in expected.items():
        matches=[(name,sha) for name,sha in captured.items() if name.endswith('/'+relative)]
        require(len(matches)==1,'missing or duplicate input hash: '+relative)
        name,sha=matches[0];roots.add(name[:-len(relative)])
        actual=folder/'capture-lock.json' if relative=='baseline/lock.json' else path
        require(digest(actual)==sha,'capture provenance changed: '+relative)
    require(len(roots)==1,'capture input roots differ')
    # Preserve the exact historical lock bytes. Later additions cannot rewrite
    # any old pin or criterion, and do not invalidate this immutable capture.
    historical=json.loads((folder/'capture-lock.json').read_text())
    current=json.loads((ROOT/'baseline/lock.json').read_text())
    require(current['artifacts'][:len(historical['artifacts'])]==historical['artifacts'],'old source pins changed')
    require({k:v for k,v in current.items() if k!='artifacts'}=={k:v for k,v in historical.items() if k!='artifacts'},'baseline criteria changed')
    for row in historical['artifacts']:require(digest(ROOT/row['path'])==row['sha256'],'historical pinned bytes changed: '+row['path'])


def compare(suite_path,first,second):
    suite=json.loads(suite_path.read_text());require(suite==author(),'authored suite differs')
    require(Counter(r['label'] for r in suite['runs'])==suite['groups_expected'],'case family count differs')
    manifests=[json.loads((folder/'manifest.json').read_text()) for folder in [first,second]]
    a,b=manifests;require(a['process_id']!=b['process_id'],'same native process')
    require(a['input_hashes']==b['input_hashes'],'capture inputs differ')
    require(a['operator_properties_sha256']==b['operator_properties_sha256'],'RNA differs')
    receipt_path=ROOT/'docs/evidence/snap-rotation-baseline/native-processes.json'
    receipts=json.loads(receipt_path.read_text())['runs']
    ids=[r['id'] for r in suite['runs']]
    for folder,m in zip([first,second],manifests):
        require(m['schema_version']==1 and m['product']=='blender' and m['product_acceptance']=='unrun','source identity differs')
        require(type(m['process_id']) is int and m['process_id']>0,'native process ID differs')
        require(m['scope']=='complete_2496_authored_snap_rotation_cases' and not m['background'],'incomplete/native mode differs')
        require(m['version']==[5,2,3] and m['build_hash']=='e13b728c6880','fixed build differs')
        require(m['binary_sha256']=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619','fixed binary differs')
        require([r['id'] for r in m['runs']]==ids,'capture cases differ')
        require({p.name for p in folder.glob('*.json.gz')}=={id+'.json.gz' for id in ids},'raw artifact set differs')
        require(digest(folder/'operator-properties.json')==m['operator_properties_sha256'],'RNA hash differs')
        matches=[r for r in receipts if r['process_id']==m['process_id']]
        require(len(matches)==1 and matches[0]['terminal_exit_code']==0,'native terminal exit was not successful')
        require(matches[0]['manifest_sha256']==digest(folder/'manifest.json'),'native terminal manifest differs')
        require(matches[0]['capture_lock_sha256']==digest(folder/'capture-lock.json'),'native terminal lock differs')
        provenance_inputs(folder,m,suite_path)
    for index,run in enumerate(suite['runs']):
        values=[]
        for folder,m in zip([first,second],manifests):
            row=m['runs'][index];path=folder/row['file'];require(path.name==run['id']+'.json.gz','artifact path differs')
            require(digest(path)==row['sha256'],'stored raw hash differs');raw=gzip.decompress(path.read_bytes())
            require(hashlib.sha256(raw).hexdigest()==row['raw_sha256'] and len(raw)==row['raw_bytes'],'exact JSON hash differs')
            value=json.loads(raw);require(value['result']['status']==row['status'],'manifest status differs')
            values.append(value)
        compare_case(suite,run,*values)
        if (index+1)%250==0:print(json.dumps({'compared':index+1}),flush=True)
    return {'passed':True,'cases':2496,'native_processes':[m['process_id'] for m in manifests],
            'binary_sha256':a['binary_sha256'],'suite_sha256':digest(suite_path),
            'comparison_script_sha256':digest(Path(__file__)),
            'native_terminal_receipts_sha256':digest(receipt_path),
            'position_channel_matrix_limit':1e-6,'initial_inputs_independently_bound':True,
            'product_acceptance':'unrun','milestones_accepted':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',type=Path,required=True);parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--repeat',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=compare(args.suite,args.reference,args.repeat)
    with args.output.open('x') as out:json.dump(report,out,indent=2);out.write('\n')

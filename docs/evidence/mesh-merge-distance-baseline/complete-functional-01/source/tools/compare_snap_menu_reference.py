#!/usr/bin/env python3
"""Bind snap captures to authored inputs and compare independent native runs."""
import argparse
from collections import Counter
import hashlib
import math
from pathlib import Path
import struct
import json

from compare_selection_reference import load, digest, require, validate_state, DOMAINS, TABLES
from compare_transform_reference import euler_rotation, finite
from generate_snap_menu_cases import author, OPERATORS

ROOT = Path(__file__).resolve().parents[1]
SELECTION = ['geometry', 'groups', 'selected', 'hidden', 'mode', 'history', 'active_face']
IDENTITY = [[float(i == j) for j in range(4)] for i in range(4)]


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def floats(value):
    if isinstance(value, dict):return {k:floats(v) for k,v in value.items()}
    if isinstance(value, list):return [floats(v) for v in value]
    return f32(value) if type(value) is float else value


def tree(a,b,path='',tolerance=1e-6):
    """Discrete values stay exact; every continuous component has a fixed limit."""
    if isinstance(a,dict):
        require(isinstance(b,dict) and set(a)==set(b),'fields differ: '+path)
        for key in a:tree(a[key],b[key],path+'/'+key,tolerance)
    elif isinstance(a,list):
        require(isinstance(b,list) and len(a)==len(b),'array differs: '+path)
        for i,(x,y) in enumerate(zip(a,b)):tree(x,y,path+'/'+str(i),tolerance)
    elif type(a) in [int,float] and type(b) in [int,float] and (type(a) is float or type(b) is float):
        require(math.isfinite(a) and math.isfinite(b) and abs(a-b)<=tolerance,
                f'component differs: {path}: {a} != {b}')
    else:require(type(a) is type(b) and a==b,'discrete value differs: '+path)


def matmul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def matrix(profile):
    r=euler_rotation([f32(x) for x in profile['rotation']])
    return [[f32(r[i][j]*f32(profile['scale'][j])) for j in range(3)]+[f32(profile['location'][i])] for i in range(3)]+[[0.,0.,0.,1.]]


def selection_input(mesh,run,edit):
    g={'vertices':{f'v{i:06}':[f32(x) for x in p] for i,p in enumerate(mesh['vertices'])},
       'edges':{f'e{i:06}':[f'v{v:06}' for v in pair] for i,pair in enumerate(mesh['edges'])},
       'faces':{f'f{i:06}':[f'v{v:06}' for v in face] for i,face in enumerate(mesh['faces'])}}
    for field,prefix in [('face_smooth','f'),('face_materials','f'),('edge_seams','e')]:
        g[field]={f'{prefix}{i:06}':value for i,value in enumerate(mesh[field])}
    g.update(material_slots=mesh['material_slots'],active_uv_index=mesh['active_uv_index'],
             uv_layer_order=[layer['name'] for layer in mesh['uv_layers']],
             uv_layers={layer['name']:{f'f{i:06}':[[f32(x) for x in p] for p in face] for i,face in enumerate(layer['faces'])} for layer in mesh['uv_layers']})
    hidden={domain:[f'{prefix}{i:06}' for i in (range(len(mesh[table])) if run['context'].get('hide_all') else mesh['hidden'][table])]
            for domain,table,prefix in zip(DOMAINS,TABLES,'vef')}
    domain=run['seed']['domain'];prefix='vef'[DOMAINS.index(domain)]
    seeds=[f'{prefix}{i:06}' for i in run['seed']['indices'] if f'{prefix}{i:06}' not in hidden[domain]]
    v=set();e=set();f=set()
    if domain=='VERT':
        v=set(seeds);e={id for id,pair in g['edges'].items() if set(pair)<=v};f={id for id,face in g['faces'].items() if set(face)<=v}
    elif domain=='EDGE':
        e=set(seeds);v={id for edge in e for id in g['edges'][edge]};pairs={tuple(g['edges'][id]) for id in e}
        f={id for id,face in g['faces'].items() if all(tuple(sorted(pair)) in pairs for pair in zip(face,face[1:]+face[:1]))}
    else:
        f=set(seeds);v={id for face in f for id in g['faces'][face]}
        pairs={tuple(sorted(pair)) for face in f for points in [g['faces'][face]] for pair in zip(points,points[1:]+points[:1])}
        e={id for id,pair in g['edges'].items() if tuple(pair) in pairs}
    groups=mesh['group_scenarios'][run['groups']]
    history=[{'domain':domain,'id':id} for id in seeds] if edit and run['context']['history']!='clear' else []
    active=seeds[-1] if edit and domain=='FACE' and seeds else None
    override=run['context']['active_face_override']
    if edit and override!='preserve':active=None if override is None else f'f{override:06}'
    return {'geometry':g,'groups':{'names':groups['names'],
                'weights':{id:{name:f32(w) for name,w in groups['weights'].get(id,{}).items()} for id in g['vertices']}},
            'selected':{'VERT':sorted(v),'EDGE':sorted(e),'FACE':sorted(f)},'hidden':hidden,
            'mode':run['initial_mode'] if edit else [],'history':history,'active_face':active}


def bind_initial(suite,run,state):
    c=run['context'];multi=c['multi_object'] or run['mode']=='OBJECT'
    profiles={'target':suite['profiles'][c['profile']]}
    parents={'target':'parent' if profiles['target']['parent'] is not None else None}
    if parents['target']:profiles['parent']=profiles['target']['parent'];parents['parent']=None
    if multi:
        profiles.update(suite['object_inputs']);parents.update(secondary=c['secondary_parent'],child='target')
    require(set(state['objects'])==set(profiles),'authored object set differs')
    require(set(state['meshes'])==({'target','secondary'} if multi else {'target'}),'authored mesh set differs')
    require(state['mode']==run['mode'] and state['active_object']==c['active_object'],'authored active context differs')
    expected_share=[['secondary','target']] if multi and c['linked_data'] else [[name] for name in sorted(state['meshes'])]
    require(state['sharing']==expected_share,'authored sharing differs')
    for name,p in profiles.items():
        o=state['objects'][name]
        require(o['parent']==parents[name] and o['type']==('MESH' if name in state['meshes'] else 'EMPTY'),'authored object kind or parent differs')
        expected_edit=run['mode']=='EDIT_MESH' and name in state['meshes'] and name in c['object_selection']
        if multi and c['linked_data'] and expected_edit:expected_edit=name==c['active_object']
        require(o['mode']==('EDIT' if expected_edit else 'OBJECT'),'authored object mode differs')
        require(o['selected']==(name in c['object_selection']),'authored object selection differs')
        for field in ['location','rotation','scale']:tree([f32(x) for x in p[field]],o[field],name+'/'+field,0.)
        tree(matrix(p),o['matrix_basis'],name+'/authored basis')
        # BKE_object_matrix_local_get multiplies by the actual parent inverse.
        # EIG_invert_m4_m4 explicitly returns a zero matrix for a singular
        # parent, so this RNA field is zero even though matrix_basis is valid.
        singular_parent=parents[name] is not None and 0 in profiles[parents[name]]['scale']
        local=[[0.]*4 for _ in range(4)] if singular_parent else matrix(p)
        tree(local,o['matrix_local'],name+'/authored local matrix')
        tree(IDENTITY,o['matrix_parent_inverse'],name+'/authored parent inverse',0.)
        world=matrix(p);parent=parents[name]
        while parent is not None:world=matmul(matrix(profiles[parent]),world);parent=parents[parent]
        tree(world,o['matrix_world'],name+'/authored world')
        require(o['rotation_mode']=='XYZ' and not o['animation_data'] and o['constraints']==o['modifiers']==0,'unexpected object state')
        for field,value in [('delta_location',[0.]*3),('delta_rotation',[0.]*3),('delta_scale',[1.]*3)]:tree(value,o[field],name+'/'+field,0.)
        for field in ['lock_location','lock_rotation','lock_scale']:
            require(o[field]==(c[field] if name=='target' and field in c else [False]*3),'authored locks differ')
    for name,m in state['meshes'].items():
        edit=run['mode']=='EDIT_MESH' and (name in c['object_selection'] or c['linked_data'])
        require(m['data_edit_mode']==edit,'authored mesh edit context differs')
        tree(selection_input(suite['mesh'],run,edit),{k:m[k] for k in SELECTION},name+'/authored mesh',0.)
        require(m['active_material_index']==suite['mesh']['active_material_index'],'authored active material differs')
        require(m['flags']=={'mirror_x':c['mirror_x'],'mirror_y':False,'mirror_z':False,'mirror_topology':c['mirror_topology']},'authored mesh flags differ')
    tree([f32(x) for x in c['cursor_location']],state['cursor']['location'],'authored cursor location',0.)
    tree([f32(x) for x in c['cursor_rotation']],state['cursor']['rotation'],'authored cursor rotation',0.)
    settings=state['settings'];expected={'pivot':c['pivot'],'skip_children':c['skip_children'],'origins_only':c['origins_only'],
        'autokey':False,'locations_only':False,'correct_face_attributes':c['correct_face_attributes'],
        'keep_connected':c['keep_connected'],'automerge':False,'automerge_and_split':False,
        'unit_system':c['unit_system'],'unit_scale_length':f32(c['unit_scale_length']),
        'grid_spacing':f32(c['grid_spacing']),'grid_subdivisions':10,'view_perspective':suite['environment']['view_perspective']}
    for key,value in expected.items():tree(value,settings[key],'authored settings/'+key,0.)
    for field in ['view_location','view_distance']:tree(floats(suite['environment'][field]),settings[field],'authored '+field)
    r=euler_rotation([f32(x) for x in suite['environment']['view_rotation']])
    for i in range(3):tree([r[j][i] for j in range(3)],settings['view_matrix'][i][:3],'authored viewport')


def validate_state_full(state,run):
    require(set(state)=={'active_object','cursor','cursor_metres','meshes','mode','objects','physical_metres_factor','settings','sharing'},'state fields differ')
    finite(state);factor=1. if run['context']['unit_system']=='NONE' else run['context']['unit_scale_length']
    require(state['physical_metres_factor']==factor,'physical conversion differs')
    require(set(state['cursor'])=={'location','rotation','rotation_mode','matrix'},'cursor fields differ')
    require(state['cursor']['rotation_mode']=='XYZ','cursor rotation mode differs')
    tree([x*factor for x in state['cursor']['location']],state['cursor_metres'],'physical cursor',0.)
    cp={'location':state['cursor']['location'],'rotation':state['cursor']['rotation'],'scale':[1.]*3}
    tree(matrix(cp),state['cursor']['matrix'],'cursor matrix')
    object_fields={'type','mode','parent','location','rotation','rotation_mode','scale',
        'matrix_world','matrix_local','matrix_basis','matrix_parent_inverse','delta_location',
        'delta_rotation','delta_scale','lock_location','lock_rotation','lock_scale','selected',
        'animation_data','constraints','modifiers'}
    for name,o in state['objects'].items():
        require(set(o)==object_fields,'object fields differ')
        for field in ['matrix_world','matrix_local','matrix_basis','matrix_parent_inverse']:
            require(len(o[field])==4 and all(len(row)==4 for row in o[field]),'matrix dimensions differ')
    for name,m in state['meshes'].items():
        require(set(m)==set(SELECTION)|{'data_edit_mode','active_material_index','flags','normals','world_vertices','vertices_metres','world_vertices_metres'},'mesh fields differ')
        selected={k:m[k] for k in SELECTION}
        if not m['data_edit_mode']:selected={**selected,'mode':run['initial_mode']}
        validate_state(selected)
        g=m['geometry'];w=state['objects'][name]['matrix_world']
        for field in ['world_vertices','vertices_metres','world_vertices_metres']:require(set(m[field])==set(g['vertices']),'vertex identities differ')
        for id,p in g['vertices'].items():
            # Mathutils rounds each float product before its double accumulator.
            expected=[f32(sum(f32(w[i][j]*p[j]) for j in range(3))+w[i][3]) for i in range(3)]
            tree(expected,m['world_vertices'][id],name+'/world position',0.)
            tree([x*factor for x in p],m['vertices_metres'][id],name+'/local physical position',0.)
            tree([x*factor for x in expected],m['world_vertices_metres'][id],name+'/world physical position',0.)
        n=m['normals'];require(set(n)=={'faces','corners'},'normal fields differ')
        for field in n:require(set(n[field])==set(g['faces']),'normal identities differ')
        for id,face in g['faces'].items():
            require(len(n['corners'][id])==len(face),'corner normals differ')
            for normal in [n['faces'][id],*n['corners'][id]]:
                require(len(normal)==3,'normal dimensions differ');length=math.sqrt(sum(x*x for x in normal))
                require(length<=1e-6 or abs(length-1)<=1e-6,'normal is not zero or unit length')
    require(sorted(name for group in state['sharing'] for name in group)==sorted(state['meshes']),'invalid sharing partition')
    for group in state['sharing']:
        require(group==sorted(set(group)),'invalid sharing group')
        for name in group[1:]:
            a,b=state['meshes'][group[0]],state['meshes'][name]
            for key in SELECTION+['data_edit_mode','normals','flags']:tree(a[key],b[key],'shared mesh/'+key,0.)


def grid_step(context):
    base={'NONE':1.,'METRIC':1.,'IMPERIAL':f32(.3048)}[context['unit_system']]
    scale=1. if context['unit_system']=='NONE' else context['unit_scale_length']
    return f32(f32(context['grid_spacing'])*f32(base/f32(scale)))


def snapped(point,step):
    return [f32(step*math.floor(f32(.5+f32(x/step)))) for x in point]


def analytic(run,data):
    before,after=data['before'],data['after'];op=run['operator'];checks=0
    if data['result']['status']!=['FINISHED']:return 0
    if op=='snap_cursor_to_center':
        tree([0.]*3,after['cursor']['location'],'origin location',0.)
        tree([0.]*3,after['cursor']['rotation'],'origin rotation',0.)
        tree(IDENTITY,after['cursor']['matrix'],'origin matrix',0.);checks+=1
    if op=='snap_cursor_to_grid':
        tree(snapped(before['cursor']['location'],grid_step(run['context'])),after['cursor']['location'],'analytic cursor grid',0.);checks+=1
    if op=='snap_selected_to_grid' and run['mode']=='EDIT_MESH' and run['context']['profile']=='identity' and not run['context']['multi_object']:
        m=before['meshes']['target'];g=m['geometry'];domain=run['initial_mode'][0]
        selected=m['selected']['VERT'] if domain=='VERT' else sorted({v for id in m['selected'][domain] for v in g['edges' if domain=='EDGE' else 'faces'][id]})
        for id,p in g['vertices'].items():
            expected=snapped(p,grid_step(run['context'])) if id in selected else p
            tree(expected,after['meshes']['target']['geometry']['vertices'][id],'analytic identity mesh grid',0.)
        checks+=1
    return checks


def validate(suite,run,data):
    require(set(data)=={'run','before','after','result'},'capture fields differ')
    require(data['run']==run,'authored request differs');finite(data)
    for state in [data['before'],data['after']]:validate_state_full(state,run)
    bind_initial(suite,run,data['before'])
    result=data['result'];require(set(result)=={'status','error'} and result['status'] in [['FINISHED'],['CANCELLED'],['ERROR']],'source outcome differs')
    require((isinstance(result['error'],str) and bool(result['error'])) if result['status']==['ERROR'] else result['error'] is None,'raw source error differs')
    a,b=data['before'],data['after']
    if result['status']!=['FINISHED']:
        tree(a,b,'cancelled or rejected source state',0.)
        if result['status']==['ERROR']:
            require(run['operator']=='snap_selected_to_active' and result['error']=='Error: No active element found!\n','unexpected source error')
        else:require(run['operator'] in ['snap_cursor_to_active','snap_cursor_to_selected'],'unexpected source cancellation')
    require(a['settings']==b['settings'] and a['active_object']==b['active_object'] and a['mode']==b['mode'] and a['sharing']==b['sharing'],'operation changed unrelated context')
    if run['operator'].startswith('snap_cursor_'):
        tree(a['meshes'],b['meshes'],'cursor operation mesh preservation',0.)
        tree(a['objects'],b['objects'],'cursor operation object preservation',0.)
    else:tree(a['cursor'],b['cursor'],'selected operation cursor preservation',0.)
    for name,m in a['meshes'].items():
        n=b['meshes'][name]
        for field in ['groups','selected','hidden','mode','history','active_face','active_material_index','flags','data_edit_mode']:
            require(m[field]==n[field],'preserved mesh state changed: '+field)
        for field in set(m['geometry'])-{'vertices'}:require(m['geometry'][field]==n['geometry'][field],'preserved mesh attribute changed: '+field)
    return analytic(run,data)


def compare_states(a,b):
    # Compare both raw and canonical physical coordinates. Raw position limits
    # are derived from the frozen physical limit, never from measured errors.
    factor=a['physical_metres_factor'];tree(a,b,'state')
    for name,m in a['meshes'].items():
        for field in ['vertices_metres','world_vertices_metres']:
            tree(m[field],b['meshes'][name][field],name+'/'+field)
        for field in ['world_vertices']:
            tree(m[field],b['meshes'][name][field],name+'/'+field,1e-6/factor)
        tree(m['geometry']['vertices'],b['meshes'][name]['geometry']['vertices'],name+'/raw vertices',1e-6/factor)
    tree(a['cursor']['location'],b['cursor']['location'],'raw cursor',1e-6/factor)


def provenance(folder,suite,suite_path):
    manifest=load(folder/'manifest.json');build=load(ROOT/'baseline/reference/builds/blender-5.2.3/report.json')
    require(manifest['schema_version']==1 and manifest['product']=='blender' and manifest['product_acceptance']=='unrun','capture identity differs')
    require(manifest['scope']=='complete_1672_authored_snap_menu_cases','focused capture cannot accept the suite')
    require(manifest['version']==suite['reference']['version'] and manifest['build_hash']==suite['reference']['build_hash'],'frozen build differs')
    require(manifest['binary_sha256']==build['files'][build['entry_executable']]['sha256'],'frozen executable differs')
    require(type(manifest['process_id']) is int and manifest['process_id']>0 and manifest['background'] is False,'native process provenance differs')
    paths=[suite_path,ROOT/'tools/blender_snap_menu_reference.py',ROOT/'tools/blender_transform_reference.py',ROOT/'tools/blender_selection_reference.py']
    # Retain the actual original paths, but bind their repository-relative
    # suffixes so another checkout can verify the same immutable evidence.
    captured=manifest['input_hashes'];require(len(captured)==len(paths),'capture input hash count differs')
    bases=set()
    for path in paths:
        relative=path.resolve().relative_to(ROOT).as_posix()
        matches=[(name,sha) for name,sha in captured.items() if name.endswith('/'+relative)]
        require(len(matches)==1 and matches[0][1]==digest(path),'capture input hashes differ')
        bases.add(matches[0][0][:-len(relative)])
    require(len(bases)==1,'capture input roots differ')
    require(manifest['operator_properties_sha256']==digest(folder/'operator-properties.json'),'operator metadata hash differs')
    require([r['id'] for r in manifest['runs']]==[r['id'] for r in suite['runs']],'complete ordered case set differs')
    properties=load(folder/'operator-properties.json');require(set(properties)==set(OPERATORS),'operator metadata set differs')
    require(set(properties['snap_selected_to_cursor'])=={'use_offset','use_rotation'},'selected-to-cursor parameter set differs')
    for key,default in [('use_offset',True),('use_rotation',False)]:
        p=properties['snap_selected_to_cursor'][key];require(p['type']=='BOOLEAN' and p['default'] is default,'operator default differs')
    for op in OPERATORS:
        if op!='snap_selected_to_cursor':require(properties[op]=={},'unexpected operator properties')
    return manifest,properties


def compare(suite_path,reference,repeat):
    suite=load(suite_path);require(suite==author() and len(suite['runs'])==1672,'authored fixture differs')
    pins={a['path']:a['sha256'] for a in load(ROOT/'baseline/lock.json')['artifacts']}
    for name in ['manifest.json','supporting-manifest.json']:
        path=ROOT/'baseline/sources/snap-menu'/name;source=load(path)
        require(pins.get(path.relative_to(ROOT).as_posix())==digest(path),'source manifest pin differs')
        require(source['blender_commit']=='e13b728c6880d3084d9d57c30031ed5df8b39dee','source commit differs')
        for entry in source['files']:
            file=path.parent/entry['file'];raw=file.read_bytes()
            require(digest(file)==entry['sha256']==pins.get(file.relative_to(ROOT).as_posix()),'source content pin differs')
            require(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==entry['git_blob'],'source Git object differs')
    a,pa=provenance(reference,suite,suite_path);b,pb=provenance(repeat,suite,suite_path)
    require(a['process_id']!=b['process_id'],'native processes are not independent')
    require(pa==pb,'RNA properties differ across processes')
    checks=0;records=[]
    for run,ra,rb in zip(suite['runs'],a['runs'],b['runs']):
        captures=[]
        for folder,entry in [(reference,ra),(repeat,rb)]:
            require(entry['file']==run['id']+'.json','result path differs');path=folder/entry['file']
            require(digest(path)==entry['sha256'],'raw result hash differs');data=load(path)
            require(entry['status']==data['result']['status'],'manifest outcome differs')
            try:checks+=validate(suite,run,data)
            except ValueError as error:raise ValueError(run['id']+': '+str(error)) from error
            captures.append(data)
        first,second=captures
        require(first['result']==second['result'],'source outcomes differ: '+run['id'])
        for field in ['before','after']:
            try:compare_states(first[field],second[field])
            except ValueError as error:raise ValueError(run['id']+'/'+field+': '+str(error)) from error
        records.append({'id':run['id'],'source_result':first['result'],'status':'checked'})
    return {'passed':True,'scope':'finite source reference only; no product acceptance',
            'cases':len(records),'captures':len(records)*2,'analytic_checks':checks,
            'source_outcomes_per_process':dict(Counter(r['source_result']['status'][0] for r in records)),
            'process_ids':[a['process_id'],b['process_id']],'runs':records,'product_acceptance':'unrun'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['suite','reference','repeat','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();report=compare(args.suite,args.reference,args.repeat)
    require(not args.output.exists(),'refuse existing comparison output')
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({key:value for key,value in report.items() if key!='runs'}))


if __name__=='__main__':main()

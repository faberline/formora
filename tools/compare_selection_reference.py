#!/usr/bin/env python3
"""Validate and reproduce fixed upstream selection results. Does not run Formora."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

DOMAINS = ['VERT','EDGE','FACE']
TABLES = ['vertices','edges','faces']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: '+key)
        result[key] = value
    return result


def load(path):
    def nonfinite(value):
        raise ValueError('non-finite JSON value: '+value)
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique_object,
                      parse_constant=nonfinite)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def numbers(value, size):
    return (isinstance(value, list) and len(value)==size
            and all(type(v) in [int,float] and math.isfinite(v) for v in value))


def validate_state(state):
    require(set(state)=={'geometry','groups','selected','hidden','mode','history','active_face'},
            'unexpected selection state fields')
    geometry = state['geometry']
    require(set(geometry)=={'vertices','edges','faces','face_smooth','face_materials',
                            'edge_seams','material_slots','uv_layers','uv_layer_order','active_uv_index'},
            'unexpected geometry fields')
    ids = {}
    for domain, table, prefix in zip(DOMAINS, TABLES, 'vef'):
        ids[domain] = set(geometry[table])
        require(all(re.fullmatch(prefix+r'[0-9]{6}', name) for name in ids[domain]), 'invalid logical ID')
    require(all(numbers(point,3) for point in geometry['vertices'].values()), 'invalid position')
    pairs = []
    for edge in geometry['edges'].values():
        require(isinstance(edge,list) and len(edge)==2 and edge[0]<edge[1]
                and set(edge)<=ids['VERT'], 'invalid edge endpoints')
        pairs.append(tuple(edge))
    require(len(pairs)==len(set(pairs)), 'duplicate edge identity')
    for face in geometry['faces'].values():
        require(len(face)>=3 and len(face)==len(set(face)) and set(face)<=ids['VERT'], 'invalid face')
        require(all(tuple(sorted((a,b))) in pairs for a,b in zip(face,face[1:]+face[:1])),
                'missing polygon boundary edge')
    for name, domain, kind in [('face_smooth','FACE',bool),('face_materials','FACE',int),
                                ('edge_seams','EDGE',bool)]:
        require(set(geometry[name])==ids[domain] and all(type(v) is kind for v in geometry[name].values()),
                'invalid authored component attributes')
    slots = geometry['material_slots']
    require(all(isinstance(v,str) and v for v in slots), 'invalid material slots')
    require(all(0<=i<len(slots) for i in geometry['face_materials'].values()), 'invalid face material')
    for layer in geometry['uv_layers'].values():
        require(set(layer)==ids['FACE'], 'UV faces differ')
        for face, corners in layer.items():
            require(len(corners)==len(geometry['faces'][face])
                    and all(numbers(uv,2) for uv in corners), 'invalid corner UV')
    require(len(geometry['uv_layer_order'])==len(set(geometry['uv_layer_order']))
            and set(geometry['uv_layer_order'])==set(geometry['uv_layers']), 'invalid UV layer order')
    require(type(geometry['active_uv_index']) is int
            and 0<=geometry['active_uv_index']<len(geometry['uv_layers']), 'invalid active UV')
    for field in ['selected','hidden']:
        require(set(state[field])==set(DOMAINS), 'missing component domain')
        for domain in DOMAINS:
            values = state[field][domain]
            require(values==sorted(set(values)) and set(values)<=ids[domain], 'invalid component ID set')
    for domain in DOMAINS:
        require(not set(state['selected'][domain])&set(state['hidden'][domain]), 'hidden component selected')
    require(state['mode'] and state['mode']==[d for d in DOMAINS if d in state['mode']], 'invalid mode mask')
    history = []
    for item in state['history']:
        require(set(item)=={'domain','id'} and item['domain'] in DOMAINS, 'invalid history entry')
        require(item['id'] in state['selected'][item['domain']], 'history component not selected')
        history.append((item['domain'],item['id']))
    require(len(history)==len(set(history)), 'duplicate history entry')
    require(state['active_face'] is None or state['active_face'] in ids['FACE'], 'invalid active face')
    groups = state['groups']
    require(set(groups)=={'names','weights'} and len(groups['names'])==len(set(groups['names'])),
            'invalid group names')
    require(set(groups['weights'])==ids['VERT'], 'missing group membership records')
    for memberships in groups['weights'].values():
        require(set(memberships)<=set(groups['names'])
                and all(type(w) in [int,float] and math.isfinite(w) and 0<=w<=1
                        for w in memberships.values()), 'invalid group weights')


def compare_run(reference, candidate):
    fields = {'run_id','operator','parameters','before','after','result','expected_negative'}
    for value in [reference,candidate]:
        require(set(value)==fields, 'unexpected run fields')
        result=value['result']
        require(set(result)=={'status','error','outcome'}, 'unexpected result fields')
        require(type(value['expected_negative']) is bool, 'invalid negative-case marker')
        outcomes={('FINISHED',):'completed', ('CANCELLED',):'unchanged'}
        if result['status']==['POLL_REJECTED']:
            require(value['expected_negative'] and isinstance(result['error'],str)
                    and result['outcome'] in ['invalid_selection_domain','missing_vertex_weights'],
                    'invalid rejection result')
        else:
            require(not value['expected_negative'] and result['error'] is None
                    and tuple(result['status']) in outcomes
                    and outcomes[tuple(result['status'])]==result['outcome'], 'invalid operation result')
        for side in ['before','after']:
            validate_state(value[side])
        for key in ['geometry','hidden','groups']:
            require(value['before'][key]==value['after'][key], 'selection modified '+key)
        if value['result']['status']!=['FINISHED']:
            require(value['before']==value['after'], 'rejected or unchanged request modified state')
    for field in fields:
        require(reference[field]==candidate[field], field+' differs from reference')


def bind_initial_state(mesh, run, state):
    """Bind the capture to authored data, not just a claimed input digest."""
    g=state['geometry']
    require(g['vertices']=={f'v{i:06}':point for i,point in enumerate(mesh['vertices'])},
            'initial positions or vertex identity differ from authored fixture')
    require(g['edges']=={f'e{i:06}':[f'v{v:06}' for v in pair]
                         for i,pair in enumerate(mesh['edges'])}, 'initial edges differ from fixture')
    require(g['faces']=={f'f{i:06}':[f'v{v:06}' for v in face]
                         for i,face in enumerate(mesh['faces'])}, 'initial face winding differs from fixture')
    for field,prefix in [('face_materials','f'),('face_smooth','f'),('edge_seams','e')]:
        require(g[field]=={f'{prefix}{i:06}':value for i,value in enumerate(mesh[field])},
                'initial authored attributes differ: '+field)
    require(g['material_slots']==mesh['material_slots'] and g['active_uv_index']==mesh['active_uv_index'],
            'initial material or UV layout differs')
    require(g['uv_layer_order']==[layer['name'] for layer in mesh['uv_layers']],
            'initial UV layer order differs')
    require(g['uv_layers']=={layer['name']:{f'f{i:06}':corners for i,corners in enumerate(layer['faces'])}
                             for layer in mesh['uv_layers']}, 'initial UV data differ')
    expected_hidden={domain:[f'{prefix}{i:06}' for i in mesh['hidden'][table]]
                     for domain,table,prefix in zip(DOMAINS,TABLES,'vef')}
    require(state['hidden']==expected_hidden, 'initial hidden state differs')
    groups=mesh['group_scenarios'][run['groups']]
    require(state['groups']=={'names':groups['names'],
                              'weights':{v:groups['weights'].get(v,{}) for v in g['vertices']}},
            'initial group membership differs')
    require(state['mode']==run['initial_mode'], 'initial mode differs')
    domain=run['seed']['domain']
    prefix='vef'[DOMAINS.index(domain)]
    seed=[f'{prefix}{i:06}' for i in run['seed']['indices']]
    require(set(seed)<=set(state['selected'][domain]), 'initial selection omits authored seed')
    require(state['history']==[{'domain':domain,'id':name} for name in seed], 'initial history differs')
    require(state['active_face']==(seed[-1] if seed and domain=='FACE' else None), 'initial active face differs')


def oracle(run, data, mesh):
    """Independent graph predicates for selected, documented subsets of the matrix."""
    p = run['parameters']
    after = data['after']
    domain = run['initial_mode'][0]
    operator = run['operator']
    expected = None
    users = {i:[] for i in range(len(mesh['edges']))}
    edge_index = {tuple(edge):i for i,edge in enumerate(mesh['edges'])}
    degrees = [0]*len(mesh['vertices'])
    for a,b in mesh['edges']:
        degrees[a]+=1
        degrees[b]+=1
    for face_index, face in enumerate(mesh['faces']):
        for a,b in zip(face,face[1:]+face[:1]):
            users[edge_index[tuple(sorted((a,b)))]].append((face_index, 1 if a<b else -1))
    compare = lambda value, count: {'LESS':value<count, 'EQUAL':value==count,
                                   'GREATER':value>count, 'NOTEQUAL':value!=count}[p['type']]
    if operator=='select_mode':
        mask = set(run['initial_mode'])
        target = p['type']
        if not p.get('use_extend',False):
            mask={target}
        elif p['action']=='ENABLE':
            mask.add(target)
        elif p['action']=='DISABLE':
            mask.discard(target)
        else:
            mask.symmetric_difference_update({target})
        if not mask:
            mask=set(run['initial_mode'])
        require(after['mode']==[d for d in DOMAINS if d in mask], 'mode action violates mask rules')
        return True
    if operator=='select_face_by_sides' and domain=='FACE':
        expected={f'f{i:06}' for i,face in enumerate(mesh['faces']) if compare(len(face),p['number'])}
    elif operator=='select_by_pole_count' and domain=='VERT' and not p['exclude_nonmanifold']:
        expected={f'v{i:06}' for i,degree in enumerate(degrees) if compare(degree,p['pole_count'])}
    elif operator=='select_loose':
        if domain=='VERT':
            expected={f'v{i:06}' for i,degree in enumerate(degrees) if degree==0}
        elif domain=='EDGE':
            expected={f'e{i:06}' for i,faces in users.items() if not faces}
        else:
            expected={f'f{i:06}' for i,face in enumerate(mesh['faces'])
                      if all(len(users[edge_index[tuple(sorted((a,b)))]])==1
                             for a,b in zip(face,face[1:]+face[:1]))}
    elif operator=='select_non_manifold' and domain=='EDGE' and not p['extend']:
        enabled=[flag for flag in ['use_wire','use_boundary','use_multi_face','use_non_contiguous','use_verts'] if p[flag]]
        if len(enabled)==1 and enabled[0]!='use_verts':
            flag=enabled[0]
            expected={f'e{i:06}' for i,faces in users.items()
                      if {'use_wire':len(faces)==0, 'use_boundary':len(faces)==1,
                          'use_multi_face':len(faces)>2,
                          'use_non_contiguous':len(faces)==2 and faces[0][1]==faces[1][1]}[flag]}
    if expected is None:
        return False
    expected-=set(data['before']['hidden'][domain])
    if p.get('extend',False):
        expected|=set(data['before']['selected'][domain])
    require(set(after['selected'][domain])==expected, 'result violates independent topology predicate')
    return True


def capture(directory, suite):
    manifest=load(directory/'manifest.json')
    require(type(manifest['process_id']) is int and manifest['process_id']>0
            and isinstance(manifest['capture_started_utc'],str)
            and manifest['capture_started_utc'], 'missing capture process provenance')
    for flag in ['--background','--factory-startup','--disable-autoexec','--python-exit-code']:
        require(flag in manifest['command_line'], 'missing required reference launch flag')
    require(manifest['version']==suite['reference']['version']
            and manifest['build_hash']==suite['reference']['build_hash'], 'reference version differs')
    require(manifest['product_acceptance']=='unrun', 'reference must not accept product')
    require(manifest['suite_sha256']==suite['_input_sha256'], 'suite digest differs')
    require(manifest['expected_negative_cases']==20 and manifest['expected_unchanged_cases']==30,
            'reference outcome counts differ')
    expected=[r['id'] for r in suite['runs']]
    require([r['id'] for r in manifest['runs']]==expected, 'missing, reordered or duplicate runs')
    require(manifest['operator_properties_sha256']==digest(directory/'operator-properties.json'), 'RNA digest differs')
    records={}
    checked=0
    for run,entry in zip(suite['runs'],manifest['runs']):
        require(entry['file']==run['id']+'.json', 'unexpected result path')
        path=directory/entry['file']
        require(digest(path)==entry['sha256'], 'result digest differs')
        value=load(path)
        require(entry['feature']==run['feature'] and entry['result']==value['result']['status'],
                'manifest result metadata differs')
        require(value['run_id']==run['id'] and value['operator']==run['operator']
                and value['parameters']==run['parameters'], 'requested operation differs')
        require(value['result']['status']==run['expected_status']
                and value['expected_negative']==bool(run['expected_error']), 'reference outcome differs')
        if run['expected_error']:
            require(run['expected_error'] in value['result']['error'], 'reference rejection differs')
        else:
            require(value['result']['error'] is None, 'unexpected reference error')
        compare_run(value,value)
        bind_initial_state(suite['mesh'],run,value['before'])
        checked+=oracle(run,value,suite['mesh'])
        records[run['id']]=value
    return manifest,records,checked


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--repeat',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    suite=load(args.suite)
    suite['_input_sha256']=digest(args.suite)
    first, a, count=capture(args.reference,suite)
    second, b, repeat_count=capture(args.repeat,suite)
    require(first['process_id']!=second['process_id']
            and first['capture_started_utc']!=second['capture_started_utc'],
            'captures must come from separate reference processes')
    require(first['binary_sha256']==second['binary_sha256']
            and first['adapter_sha256']==second['adapter_sha256'], 'reference binary or adapter changed')
    root=Path(__file__).resolve().parents[1]
    build=load(root/'baseline/reference/builds/blender-5.2.3/report.json')
    require(first['binary_sha256']==build['files'][build['entry_executable']]['sha256'],
            'binary differs from the frozen reference build')
    require(first['adapter_sha256']==digest(Path(__file__).with_name('blender_selection_reference.py')),
            'capture adapter differs from the current source')
    for name in a:
        compare_run(a[name],b[name])
    report={'reference_reproduction_passed':True,'runs_compared':len(a),
            'expected_completed':480,'expected_unchanged':30,'expected_negative':20,
            'independent_predicates_per_capture':count,'repeat_predicates':repeat_count,
            'authored_initial_states_checked_per_capture':len(a),
            'capture_processes':[{'pid':m['process_id'],'started_utc':m['capture_started_utc']}
                                 for m in [first,second]],
            'source_manifest_sha256':digest(args.reference/'manifest.json'),
            'repeat_manifest_sha256':digest(args.repeat/'manifest.json'),
            'comparer_sha256':digest(__file__), 'suite_sha256':digest(args.suite),
            'formora_execution':'unrun','product_acceptance':'unrun'}
    with args.output.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()

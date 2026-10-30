"""Diagnostic source comparison. Native protocol only; not the CLI/MCP gate."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tools'))
from scene_snap_runtime_smoke import setup as scene_setup
from selection_runtime_smoke import native, snapshot as selection_snapshot
from compare_snap_menu_reference import tree

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())

def setup(suite,case):
    result=scene_setup(suite,case)
    asset=next(command['asset'] for command in result['commands'] if command['operation']=='set_mesh_asset')
    asset['integer_attributes']={domain:{'capture':{id:int(id[1:]) for id in asset[field]}} for domain,field in [('vertices','vertices'),('edges','edges'),('polygons','polygons')]}
    asset['integer_attributes']['triangles']={}
    return result

def near(a,b):
    try:tree(a,b,'candidate');return True
    except AssertionError:return False

def normalize(query,world,reference):
    actual=selection_snapshot(query);asset=query['mesh_asset'];old=reference['geometry'];g=actual['geometry']
    assert len(old['vertices'])==len(g['vertices']),'vertex count differs'
    # Bind topology identity from independent physical and data constraints.
    # Repeated integer values never stand for a component identity.
    candidates={id:[other for other,point in g['vertices'].items() if near(old['vertices'][id],point)
        and near(reference['groups']['weights'][id],actual['groups']['weights'][other])
        and reference['source_component_ids']['VERT'][id]==asset['integer_attributes']['vertices']['capture'][other]] for id in old['vertices']}
    assert all(candidates.values()),'no matching physical vertex and data: '+str({k:v for k,v in candidates.items() if not v})
    edge_pairs={frozenset(pair) for pair in g['edges'].values()}
    adjacency={id:set() for id in old['vertices']}
    for a,b in old['edges'].values():adjacency[a].add(b);adjacency[b].add(a)
    order=sorted(candidates,key=lambda id:(len(candidates[id]),-len(adjacency[id]),id))
    mapping={};used=set()
    def solve(index):
        if index==len(order):return True
        id=order[index]
        for other in candidates[id]:
            if other in used:continue
            if any((neighbor in adjacency[id])!=(frozenset([other,value]) in edge_pairs) for neighbor,value in mapping.items()):continue
            mapping[id]=other;used.add(other)
            if solve(index+1):return True
            used.remove(other);del mapping[id]
        return False
    assert solve(0),'no bijective physical topology match'
    inverse={value:key for key,value in mapping.items()}
    epairs={tuple(sorted(pair)):id for id,pair in g['edges'].items()}
    assert len(epairs)==len(g['edges'])==len(old['edges']),'edge count/uniqueness differs'
    emap={id:epairs[tuple(sorted(mapping[v] for v in pair))] for id,pair in old['edges'].items()}
    einverse={value:key for key,value in emap.items()};fmap={};rotations={}
    for id,vertices in old['faces'].items():
        wanted=[mapping[v] for v in vertices];matches=[]
        for other,points in g['faces'].items():
            if len(points)!=len(wanted):continue
            for offset in range(len(points)):
                if points[offset:]+points[:offset]==wanted:matches.append((other,offset))
        assert len(matches)==1,('oriented face match differs',id,matches)
        fmap[id],rotations[id]=matches[0]
    assert len(fmap)==len(set(fmap.values()))==len(g['faces']),'face count/uniqueness differs'
    finverse={value:key for key,value in fmap.items()}
    remap={'VERT':inverse,'EDGE':einverse,'FACE':finverse}
    result=copy.deepcopy(actual)
    ng=result['geometry']
    ng['vertices']={id:g['vertices'][other] for id,other in mapping.items()}
    ng['edges']={id:sorted(inverse[v] for v in g['edges'][other]) for id,other in emap.items()}
    ng['faces']={id:old['faces'][id] for id in fmap}
    for field in ['face_smooth','face_materials']:ng[field]={id:g[field][other] for id,other in fmap.items()}
    ng['edge_seams']={id:g['edge_seams'][other] for id,other in emap.items()}
    def rotate(values,id):n=rotations[id];return values[n:]+values[:n]
    ng['uv_layers']={name:{id:rotate(values[other],id) for id,other in fmap.items()} for name,values in g['uv_layers'].items()}
    result['groups']['weights']={id:actual['groups']['weights'][other] for id,other in mapping.items()}
    for field in ['selected','hidden']:result[field]={domain:sorted(remap[domain][id] for id in actual[field][domain]) for domain in remap}
    result['history']=[{'domain':entry['domain'],'id':remap[entry['domain']][entry['id']]} for entry in actual['history']]
    result['active_face']=None if actual['active_face'] is None else finverse[actual['active_face']]
    normals={entry['face']['id']:entry for entry in query['normals']['faces']}
    result['normals']={'faces':{id:normals[other]['normal'] for id,other in fmap.items()},
        'corners':{id:rotate(normals[other]['corner_normals'],id) for id,other in fmap.items()}}
    result['world_vertices']={id:world['world_vertices'][other] for id,other in mapping.items()}
    result['source_component_ids']={domain:{id:asset['integer_attributes'][field]['capture'][other] for id,other in pairs.items()} for domain,field,pairs in [('VERT','vertices',mapping),('EDGE','edges',emap),('FACE','polygons',fmap)]}
    return result,{'vertices':mapping,'edges':emap,'faces':fmap}

def compare(reference,query,world):
    result,maps=normalize(query,world,reference)
    tree({key:reference[key] for key in result},result,'saved mesh')
    return maps

def main():
    parser=argparse.ArgumentParser();parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--case',action='append',default=[]);args=parser.parse_args()
    args.output.mkdir(exist_ok=False,parents=True)
    suite=load(ROOT/'baseline/fixtures/mesh-merge.json');records=[]
    cases=[case for case in suite['runs'] if not args.case or case['id'] in args.case]
    binary=args.binary.resolve();binary_hash=sha(binary)
    inputs={p.relative_to(ROOT).as_posix():sha(p) for name in ['src','tests','tools','docs/contracts'] for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    for index,case in enumerate(cases):
        record={'case':case,'interface':'native_protocol_diagnostic','setup':setup(suite,case),'error':None,'passed':False}
        with tempfile.TemporaryDirectory(prefix='formora-merge-pilot-') as folder:
            scene=Path(folder)/'scene.json'
            init=subprocess.run([str(binary),'scene','init','--scene',str(scene)],capture_output=True,text=True);assert init.returncode==0,init.stderr
            with native(binary,scene) as call:
                def inspect():
                    state,error=call('scene_inspect',{});assert not error,state
                    query,error=call('scene_inspect',{'mesh_asset':'mesh','normals':True});assert not error,query
                    world,error=call('scene_inspect',{'entity':'target','world':True});assert not error,world
                    return {'scene':state['scene'],'query':query,'world':world}
                value,error=call('scene_apply',record['setup']);assert not error,value
                record['before']=inspect()
                request={'expected_revision':1,'commands':[{'operation':'merge_mesh','merge':{'entity':'target','method':case['parameters']['type'].lower(),'uvs':case['parameters']['uvs']}}]}
                record['request']=request
                value,error=call('scene_apply',request);record['result']=value;record['operation_error']=error
                record['after']=inspect();record['saved_scene']=json.loads(scene.read_bytes())
                try:
                    for native_name in ['native-01','native-02']:
                        reference=load(ROOT/'docs/evidence/mesh-merge-baseline'/native_name/(case['id']+'.json.gz'))
                        record['before_mapping']=compare(reference['before']['meshes']['target'],record['before']['query'],record['before']['world'])
                        if reference['result']['status']==['ENUM_REJECTED']:
                            assert error and record['before']==record['after'],'missing atomic enum rejection'
                        else:
                            assert not error,value
                            record['after_mapping']=compare(reference['after']['meshes']['target'],record['after']['query'],record['after']['world'])
                            assert len(value['merges'])==1 and value['merges'][0]['shared_instances']==['secondary','target']
                    assert record['saved_scene']==record['after']['scene']
                    record['passed']=True
                except (AssertionError,KeyError,ValueError) as failure:record['error']=str(failure)
        target=args.output/(case['id']+'.json.gz');target.write_bytes(gzip.compress(json.dumps(record,allow_nan=False).encode(),mtime=0))
        records.append({'id':case['id'],'passed':record['passed'],'error':record['error'],'file':target.name,'sha256':sha(target)})
        if (index+1)%50==0:print(json.dumps({'executed':index+1,'failed':sum(not row['passed'] for row in records)}),flush=True)
    assert all(sha(ROOT/name)==value for name,value in inputs.items()) and sha(binary)==binary_hash,'inputs changed during diagnostic'
    report={'passed':all(row['passed'] for row in records),'executed':len(records),'failed':sum(not row['passed'] for row in records),'records':records,'input_hashes':inputs,'binary_sha256':binary_hash,'cli_mcp_gate':'unrun','product_acceptance':'unrun'}
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['records','input_hashes']}),flush=True)
    raise SystemExit(0 if report['passed'] else 1)

if __name__=='__main__':main()

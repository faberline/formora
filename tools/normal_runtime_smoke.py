#!/usr/bin/env python3
"""Compare Rust automatic normal queries with fixed, input-bound source records."""
import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile

from generate_mesh_normal_cases import author


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def f32(value):
    return struct.unpack('<f',struct.pack('<f',value))[0]


def load_reference(root, suite):
    folder=root/'baseline/reference/blender-5.2.3/mesh-normals'
    manifest=json.loads((folder/'manifest.json').read_text())
    assert manifest['complete'] and manifest['cases']==len(suite['cases'])==21
    assert manifest['version']==[5,2,3] and manifest['build_hash']=='e13b728c6880'
    assert manifest['binary_sha256']=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert manifest['suite_sha256']==sha(root/'baseline/fixtures/mesh-normals.json')
    assert manifest['adapter_sha256']==sha(root/'tools/blender_normal_reference.py')
    by_id={case['id']:case for case in suite['cases']};records={}
    assert len(manifest['records'])==len(by_id)
    for record in manifest['records']:
        assert record['id'] in by_id and record['id'] not in records
        assert record['file']==record['id']+'.json'
        path=folder/record['file'];assert sha(path)==record['sha256']
        value=json.loads(path.read_text());case=by_id[record['id']]
        assert value['id']==record['id']
        assert value['vertices']==[[f32(v) for v in p] for p in case['vertices']]
        assert value['faces']==case['faces'] and value['smooth']==case['smooth']
        assert len(value['normals'])==len(case['faces'])
        for face, normal in zip(case['faces'],value['normals']):
            assert len(normal['corner_normals'])==len(face)
            for vector in [normal['normal'],*normal['corner_normals']]:
                assert len(vector)==3 and all(math.isfinite(v) for v in vector)
                assert vector==[0,0,0] or abs(sum(v*v for v in vector)-1)<=1e-6
        records[record['id']]=value
    return records


def asset_from_case(case):
    asset={'vertices':{f'v{i:06}':p for i,p in enumerate(case['vertices'])},
           'edges':{f'e{i:06}':[f'v{v:06}' for v in pair] for i,pair in enumerate(case['edges'])},
           'triangles':{},'polygons':{},'material_slots':[],
           'edge_seams':[f'e{i:06}' for i in case['seams']], 'smooth_triangles':[]}
    for i,(face,smooth,kind) in enumerate(zip(case['faces'],case['smooth'],case['kinds'])):
        id=f'f{i:06}';value={'vertices':[f'v{v:06}' for v in face], 'uv_layers':{},'corner_normals':None,'material_slot':None}
        if kind=='polygon':value.update(normal=None,smooth=smooth)
        elif kind=='triangle':
            assert len(face)==3
            if smooth:asset['smooth_triangles'].append(id)
        else:raise AssertionError('unknown authored face kind')
        asset['polygons' if kind=='polygon' else 'triangles'][id]=value
    return asset


def compare(case, reference, query):
    authored=asset_from_case(case)
    # Match the asset serializer's omitted empty optional collections.
    authored={key:value for key,value in authored.items() if value or key not in {'edges','polygons','edge_seams','smooth_triangles'}}
    assert query['mesh_asset']==authored, 'query changed the authored geometry or attributes'
    faces=query['normals']['faces'];assert len(faces)==len(case['faces'])
    by_key={(f['face']['kind'],f['face']['id']):f for f in faces}
    assert len(by_key)==len(faces);maximum=0.;components=0
    for i,expected in enumerate(reference['normals']):
        actual=by_key[(case['kinds'][i],f'f{i:06}')]
        assert len(actual['corner_normals'])==len(expected['corner_normals'])
        for av,ev in zip([actual['normal'],*actual['corner_normals']], [expected['normal'],*expected['corner_normals']]):
            assert len(av)==len(ev)==3
            for a,e in zip(av,ev):
                assert math.isfinite(a) and abs(a-e)<=1e-6,(case['id'],i,av,ev)
                maximum=max(maximum,abs(a-e));components+=1
    return {'components':components,'maximum_absolute_error':maximum}


async def run(binary, output):
    from jsonschema import Draft202012Validator
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    root=Path(__file__).resolve().parents[1]
    suite=json.loads((root/'baseline/fixtures/mesh-normals.json').read_text())
    assert suite==author() and suite['normal_absolute_tolerance']==1e-6
    references=load_reference(root,suite)
    inputs=[root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()],
            root/'tools/normal_runtime_smoke.py',root/'tools/generate_mesh_normal_cases.py',root/'tools/blender_normal_reference.py',
            root/'baseline/fixtures/mesh-normals.json',*sorted((root/'baseline/reference/blender-5.2.3/mesh-normals').glob('*.json'))]
    snapshot={str(p.relative_to(root)):sha(p) for p in inputs};binary_sha=sha(binary)
    output.mkdir(parents=True,exist_ok=False);records=[]
    def cli(scene,action,*args,request=None,fail=False):
        result=subprocess.run([str(binary),'scene',action,'--scene',str(scene),*args],
                 input=None if request is None else json.dumps(request),capture_output=True,text=True)
        assert bool(result.returncode)==fail,(result.stdout,result.stderr)
        return {'error':result.stderr} if fail else json.loads(result.stdout)
    with tempfile.TemporaryDirectory(prefix='formora-normal-runtime-') as temporary:
        for interface in ['cli','official_mcp_sdk']:
            for case in suite['cases']:
                scene=Path(temporary)/(interface+'-'+case['id']+'.json');cli(scene,'init')
                setup={'expected_revision':0,'commands':[{'operation':'set_mesh_asset','id':'mesh','asset':asset_from_case(case)}]}
                if interface=='cli':
                    applied=cli(scene,'apply','--request','-',request=setup);assert applied['revision']==1
                    saved=scene.read_bytes();query=cli(scene,'inspect','--mesh-asset','mesh','--normals')
                    assert cli(scene,'inspect','--mesh-asset','mesh','--normals')==query
                    assert cli(scene,'inspect','--mesh-asset','mesh')['mesh_asset']==query['mesh_asset']
                    cli(scene,'inspect','--normals',fail=True)
                    cli(scene,'inspect','--mesh-asset','missing','--normals',fail=True)
                    assert scene.read_bytes()==saved
                else:
                    parameters=StdioServerParameters(command=str(binary),args=['mcp','--scene',str(scene)])
                    async with stdio_client(parameters) as (reader,writer):
                        async with ClientSession(reader,writer,read_timeout_seconds=10) as client:
                            await client.initialize();listed=await client.list_tools()
                            schemas={t.name:t.input_schema for t in listed.tools}
                            Draft202012Validator(schemas['scene_apply']).validate(setup)
                            applied=await client.call_tool('scene_apply',setup);assert not applied.is_error
                            assert applied.structured_content['revision']==1;saved=scene.read_bytes()
                            arguments={'mesh_asset':'mesh','normals':True}
                            Draft202012Validator(schemas['scene_inspect']).validate(arguments)
                            response=await client.call_tool('scene_inspect',arguments);assert not response.is_error
                            query=response.structured_content
                            repeat=await client.call_tool('scene_inspect',arguments);assert not repeat.is_error
                            assert repeat.structured_content==query
                            for arguments in [{'normals':True},{'mesh_asset':'missing','normals':True}]:
                                invalid=await client.call_tool('scene_inspect',arguments);assert invalid.is_error
                            assert scene.read_bytes()==saved
                            undone=await client.call_tool('scene_undo',{'expected_revision':1});assert not undone.is_error
                            after=await client.call_tool('scene_inspect',{});assert not after.is_error
                            assert after.structured_content['revision']==2
                            assert after.structured_content['scene'].get('mesh_assets',{})=={}
                assert query['revision']==1
                assert query['mesh_asset']==json.loads(saved)['mesh_assets']['mesh']
                record={'interface':interface,'id':case['id'],'passed':True,**compare(case,references[case['id']],query),
                        'scene_sha256':hashlib.sha256(saved).hexdigest(),'asset':asset_from_case(case),'query':query}
                path=output/(interface+'-'+case['id']+'.json');path.write_text(json.dumps(record,indent=2)+'\n')
                records.append({'id':case['id'],'interface':interface,'file':path.name,'sha256':sha(path),
                                'maximum_absolute_error':record['maximum_absolute_error'],'components':record['components']})
    assert snapshot=={str(p.relative_to(root)):sha(p) for p in inputs} and binary_sha==sha(binary)
    manifest={'passed':True,'cases':len(records),'binary_sha256':binary_sha,'input_hashes':snapshot,'records':records,
              'scope':'Automatic normal queries only; product transforms, full custom normals and integrated acceptance remain unrun.'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(records),'maximum_absolute_error':max(r['maximum_absolute_error'] for r in records)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    binary=args.binary.resolve()
    if not binary.exists() and binary.with_suffix('.exe').exists():
        binary=binary.with_suffix('.exe')
    asyncio.run(run(binary,args.output.resolve()))

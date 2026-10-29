#!/usr/bin/env python3
"""Verify automatic shading, actual edits and fresh reload on native Metal."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from generate_mesh_normal_cases import author
from normal_runtime_smoke import asset_from_case
from png_pixels import read_rgba8


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();binary=args.binary.resolve();output=args.output.resolve();root=Path(__file__).resolve().parents[1]
    output.mkdir(parents=True,exist_ok=False);calls=[]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    inputs=[root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()],
            *[root/name for name in ['tools/normal_gpu_evidence.py','tools/normal_runtime_smoke.py','tools/generate_mesh_normal_cases.py','tools/png_pixels.py','baseline/fixtures/mesh-normals.json','docs/contracts/mesh-transform-core.md']]]
    snapshot={str(p.relative_to(root)):sha(p) for p in inputs};binary_sha=sha(binary)
    scene=output/'scene.json'
    def call(*arguments,request=None):
        result=subprocess.run([str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),capture_output=True,text=True)
        calls.append({'arguments':list(map(str,arguments)),'request':request,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        assert result.returncode==0,result.stderr
        return json.loads(result.stdout)
    identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
    def entity(id,content,transform):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':None,'transform':transform,'content':content}}
    asset=asset_from_case(author()['cases'][0]);call('scene','init','--scene',scene)
    call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':0,'commands':[
        {'operation':'set_mesh_asset','id':'mesh','asset':asset},
        entity('surface',{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None},identity),
        entity('camera',{'kind':'camera','vertical_fov_degrees':45,'near':0.1,'far':100},{**identity,'translation':[-0.5,0.5,4]}),
        {'operation':'set_active_camera','id':'camera'},
        entity('light',{'kind':'light','color':[1,1,1],'intensity':2},{**identity,'translation':[2,1,5]})]})
    queries={};gpus=[]
    def capture(name):
        queries[name]=call('scene','inspect','--scene',scene,'--mesh-asset','mesh','--normals')
        (output/(name+'-scene.json')).write_bytes(scene.read_bytes())
        (output/(name+'-normals.json')).write_text(json.dumps(queries[name],indent=2)+'\n')
        gpus.append(call('render','--scene',scene,'--output',output/(name+'.png'),'--width',640,'--height',480)['gpu'])
        assert '(Metal,' in gpus[-1],gpus[-1]
    capture('smooth')
    flat=copy.deepcopy(asset)
    for polygon in flat['polygons'].values():polygon['smooth']=False
    call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':1,'commands':[{'operation':'set_mesh_asset','id':'mesh','asset':flat}]})
    capture('flat');assert queries['smooth']['normals']!=queries['flat']['normals']
    assert queries['smooth']['mesh_asset']['vertices']==queries['flat']['mesh_asset']['vertices']
    assert all(p['normal'] is None and p['corner_normals'] is None for p in queries['flat']['mesh_asset']['polygons'].values())
    call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':2,'commands':[{'operation':'set_mesh_vertices','id':'mesh','positions':{'v000002':[-1,1,0.5],'v000004':[0.4,0,1],'v000005':[0.4,1,1]}}]})
    capture('edited');assert queries['edited']['normals']!=queries['flat']['normals']
    capture('reloaded');assert queries['edited']==queries['reloaded']
    assert (output/'edited.png').read_bytes()==(output/'reloaded.png').read_bytes()
    def changed(a,b):
        w,h,first=read_rgba8(output/(a+'.png'));w2,h2,second=read_rgba8(output/(b+'.png'));assert (w,h)==(w2,h2)==(640,480)
        return sum(first(x,y)!=second(x,y) for y in range(h) for x in range(w))
    shading_pixels=changed('smooth','flat');edit_pixels=changed('flat','edited')
    assert shading_pixels>500 and edit_pixels>500,(shading_pixels,edit_pixels)
    assert snapshot=={str(p.relative_to(root)):sha(p) for p in inputs} and binary_sha==sha(binary)
    manifest={'passed':True,'gpu':gpus,'platform':platform.platform(),'binary_sha256':binary_sha,'input_hashes':snapshot,
              'normal_only_changed_pixels':shading_pixels,'geometry_edit_changed_pixels':edit_pixels,'fresh_reload_identical':True,
              'commands':calls,'artifacts':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and not p.name.endswith('.formora.lock')},
              'scope':'Automatic normal shading only. Native window input, product transforms, other GPU platforms and full product acceptance remain unrun.'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'passed':True,'normal_only_changed_pixels':shading_pixels,'geometry_edit_changed_pixels':edit_pixels,'gpu':gpus[0]}))


if __name__=='__main__':main()

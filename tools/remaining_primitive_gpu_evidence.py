#!/usr/bin/env python3
"""Capture two isolated Rust-generated models on the native GPU."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
from png_pixels import read_rgba8


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();binary=args.binary.resolve();output=args.output.resolve()
    root=Path(__file__).resolve().parents[1];output.mkdir(parents=True,exist_ok=False)
    records=[];calls=[]
    def call(*arguments,request=None):
        result=subprocess.run([str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),
                              capture_output=True,text=True,check=True)
        calls.append({'arguments':list(map(str,arguments)),'request':request,'exit_code':result.returncode,'stdout':result.stdout})
        return json.loads(result.stdout)
    identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
    for kind,before,after,camera_transform in [
        ('ico_sphere',{'radius':0.65},{'radius':1.1},{**identity,'translation':[0,0,5]}),
        ('monkey',{'size':1.3},{'size':2.2},{**identity,'translation':[0,-5,0],'rotation':[math.sqrt(0.5),0,0,math.sqrt(0.5)]})]:
        folder=output/kind;folder.mkdir();scene=folder/'scene.json';call('scene','init','--scene',scene)
        def entity(name,content,transform=identity):
            return {'operation':'create_entity','id':name,'entity':{'name':name,'parent':None,'transform':transform,'content':content}}
        creation={'expected_revision':0,'commands':[
            {'operation':'create_mesh_primitive','id':'shape','primitive':{'kind':kind,**before}},
            {'operation':'set_material','id':'surface','material':{'base_color':[0.2,0.7,0.9,1],'roughness':0.6,'metallic':0}},
            entity('shape',{'kind':'mesh','geometry':{'kind':'asset','id':'shape'},'material':'surface'}),
            entity('camera',{'kind':'camera','vertical_fov_degrees':45,'near':0.1,'far':100},camera_transform),
            {'operation':'set_active_camera','id':'camera'},
            entity('light',{'kind':'light','color':[1,1,1],'intensity':2},{**identity,'translation':[1,-4,5]})]}
        change={'expected_revision':1,'commands':[{'operation':'regenerate_mesh_primitive','id':'shape','primitive':{'kind':kind,**after}}]}
        (folder/'creation-request.json').write_text(json.dumps(creation,indent=2)+'\n')
        (folder/'regenerate-request.json').write_text(json.dumps(change,indent=2)+'\n')
        call('scene','apply','--scene',scene,'--request','-',request=creation)
        first_query=call('scene','inspect','--scene',scene);(folder/'before-scene.json').write_bytes(scene.read_bytes())
        gpu=call('render','--scene',scene,'--output',folder/'before.png','--width',640,'--height',480)['gpu']
        assert '(Metal,' in gpu,gpu
        call('scene','apply','--scene',scene,'--request','-',request=change)
        for name in ['after','reloaded']:call('render','--scene',scene,'--output',folder/(name+'.png'),'--width',640,'--height',480)
        changed=call('scene','inspect','--scene',scene)
        assert changed['scene']['entities']==first_query['scene']['entities']
        assert changed['scene']['mesh_assets']['shape']['recipe']['primitive']['kind']==kind
        assert not changed['scene']['mesh_assets']['shape']['recipe']['edited']
        assert (folder/'after.png').read_bytes()==(folder/'reloaded.png').read_bytes()
        width,height,initial=read_rgba8(folder/'before.png');w,h,final=read_rgba8(folder/'after.png');assert (w,h)==(width,height)
        initial_background=initial(0,0);final_background=final(0,0);initial_count=final_count=different=0
        for y in range(height):
            for x in range(width):
                initial_count+=initial(x,y)!=initial_background
                final_count+=final(x,y)!=final_background
                different+=initial(x,y)!=final(x,y)
        assert initial_count>1000 and different>500,(kind,initial_count,different)
        assert final_count>initial_count+200,(kind,initial_count,final_count)
        records.append({'kind':kind,'gpu':gpu,'initial_visible_pixels':initial_count,'changed_visible_pixels':final_count,
                        'different_pixels':different,'reopened_png_identical':True,'asset_identity_preserved':True})
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest={'passed':True,'platform':platform.platform(),'runs':records,'binary_sha256':sha(binary),
              'source_files_sha256':{str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},
              'capture_inputs_sha256':{name:sha(root/name) for name in ['tools/remaining_primitive_gpu_evidence.py','tools/png_pixels.py','docs/contracts/remaining-primitives.md']},
              'artifacts':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and not p.name.endswith('.formora.lock')},
              'commands':calls,'full_feature_acceptance':'unrun','unrun':['native window input','Windows GPU','Linux GPU','full modeling parity']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'passed':True,'runs':records}))


if __name__=='__main__':main()

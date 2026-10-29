#!/usr/bin/env python3
"""Render actual cursor/view placement and insertion, modification and fresh reload."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from png_pixels import read_rgba8


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();binary=args.binary.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1];calls=[];records=[]
    def call(*arguments,request=None):
        result=subprocess.run([str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),capture_output=True,text=True,check=True)
        calls.append({'arguments':list(map(str,arguments)),'request':request,'exit_code':result.returncode,'stdout':result.stdout})
        return json.loads(result.stdout)
    identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
    def entity(id,content,transform):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':None,'transform':transform,'content':content}}
    for sample in ['cursor','view','append']:
        folder=output/sample;folder.mkdir();scene=folder/'scene.json';call('scene','init','--scene',scene)
        context={'cursor_location':[-0.75,0,0],'cursor_rotation':[0.2,-0.4,0.6],'view_rotation':[0.35,-0.25,0.6]}
        setup=[{'operation':'set_authoring_context','context':context},
               {'operation':'create_mesh_object','creation':{'id':'shape','asset':'mesh','name':sample,'primitive':{'kind':'cube','size':1.3},'placement':{'align':'cursor' if sample=='append' else sample}}},
               entity('camera',{'kind':'camera','vertical_fov_degrees':45,'near':0.1,'far':100},{**identity,'translation':[0,0,8]}),
               {'operation':'set_active_camera','id':'camera'},
               entity('light',{'kind':'light','color':[1,1,1],'intensity':2},{**identity,'translation':[1,-4,5]})]
        result=call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':0,'commands':setup})
        revision=1
        if sample=='append':
            result=call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':1,'commands':[{'operation':'append_mesh_primitive','creation':{'entity':'shape','prefix':'inserted','primitive':{'kind':'torus','major_segments':31,'minor_segments':11},'placement':{'location':[1,0,0],'rotation':[0.4,0.2,0.1]}}}]});revision=2
        receipt=result['creation'][0];assert receipt['edit_ready'];before=call('scene','inspect','--scene',scene)['scene']
        (folder/'before-scene.json').write_bytes(scene.read_bytes());gpu=call('render','--scene',scene,'--output',folder/'before.png','--width',640,'--height',480)['gpu'];assert '(Metal,' in gpu,gpu
        if sample=='append':
            vertices=before['mesh_assets']['mesh']['vertices'];ids=receipt['created']['vertices'];center=[sum(vertices[id][j] for id in ids)/len(ids) for j in range(3)]
            positions={id:[center[j]+(vertices[id][j]-center[j])*1.35 for j in range(3)] for id in ids}
            operation={'operation':'set_mesh_vertices','id':'mesh','positions':positions}
        else:operation={'operation':'regenerate_mesh_primitive','id':'mesh','primitive':{'kind':'cube','size':2.3}}
        call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':revision,'commands':[operation]})
        changed=call('scene','inspect','--scene',scene)['scene'];assert changed['entities']==before['entities']
        if sample=='append':
            for id,point in before['mesh_assets']['mesh']['vertices'].items():
                if id not in receipt['created']['vertices']:assert changed['mesh_assets']['mesh']['vertices'][id]==point
        for name in ['after','reloaded']:call('render','--scene',scene,'--output',folder/(name+'.png'),'--width',640,'--height',480)
        assert (folder/'after.png').read_bytes()==(folder/'reloaded.png').read_bytes()
        width,height,initial=read_rgba8(folder/'before.png');w,h,final=read_rgba8(folder/'after.png');assert (w,h)==(width,height)
        visible=sum(initial(x,y)!=initial(0,0) for y in range(height) for x in range(width));different=sum(initial(x,y)!=final(x,y) for y in range(height) for x in range(width))
        assert visible>1000 and different>500,(sample,visible,different)
        records.append({'sample':sample,'gpu':gpu,'visible_pixels':visible,'different_pixels':different,'fresh_reload_png_identical':True,'entities_preserved':True,'receipt':receipt})
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest={'passed':True,'platform':platform.platform(),'runs':records,'binary_sha256':sha(binary),
              'source_files_sha256':{str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},
              'capture_inputs_sha256':{name:sha(root/name) for name in ['tools/creation_context_gpu_evidence.py','tools/png_pixels.py','docs/contracts/primitive-creation-contexts.md']},
              'artifacts':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and not p.name.endswith('.formora.lock')},'commands':calls,
              'full_feature_acceptance':'unrun','unrun':['native window input','Windows GPU','Linux GPU','full modeling parity']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'passed':True,'samples':len(records)}))


if __name__=='__main__':main()

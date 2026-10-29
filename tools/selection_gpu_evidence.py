#!/usr/bin/env python3
"""Capture actual selection markers, hidden faces and reload on the native GPU."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from png_pixels import read_rgba8


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();binary=args.binary.resolve();output=args.output.resolve()
    root=Path(__file__).resolve().parents[1];output.mkdir(parents=True,exist_ok=False)
    calls=[];records=[]
    def call(*arguments,request=None):
        result=subprocess.run([str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),
                              text=True,capture_output=True,check=True)
        calls.append({'arguments':list(map(str,arguments)),'request':request,'exit_code':result.returncode,'stdout':result.stdout})
        return json.loads(result.stdout)
    identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
    asset={'vertices':{'a':[-1,-1,0],'b':[1,-1,0],'c':[1,1,0],'d':[-1,1,0]},
           'edges':{'ab':['a','b'],'bc':['b','c'],'cd':['c','d'],'da':['d','a']},'triangles':{},
           'polygons':{'square':{'vertices':['a','b','c','d'],'uv_layers':{},'corner_normals':None,
                                  'normal':None,'smooth':False,'material_slot':None}},'material_slots':[]}
    face={'kind':'polygon','id':'square'}
    def entity(name,content,transform=identity):
        return {'operation':'create_entity','id':name,'entity':{'name':name,'parent':None,'transform':transform,'content':content}}
    for domain in ['vertex','edge','face']:
        folder=output/domain;folder.mkdir();scene=folder/'scene.json'
        call('scene','init','--scene',scene)
        request={'expected_revision':0,'commands':[
            {'operation':'set_mesh_asset','id':'mesh','asset':asset},
            entity('surface',{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}),
            entity('camera',{'kind':'camera','vertical_fov_degrees':45,'near':0.1,'far':100},{**identity,'translation':[0,0,5]}),
            {'operation':'set_active_camera','id':'camera'},
            entity('light',{'kind':'light','color':[1,1,1],'intensity':2},{**identity,'translation':[1,-2,5]})]}
        call('scene','apply','--scene',scene,'--request','-',request=request)
        baseline=call('render','--scene',scene,'--output',folder/'before.png','--width',640,'--height',480)
        gpu=baseline['gpu'];assert '(Metal,' in gpu,gpu
        selected={'vertices':['a'] if domain=='vertex' else [],'edges':['ab'] if domain=='edge' else [],'faces':[face] if domain=='face' else []}
        editing={'mode':[domain],'selected':selected,'hidden':{},'history':[],'active_face':face if domain=='face' else None}
        select={'expected_revision':1,'commands':[{'operation':'set_mesh_editing','id':'mesh','editing':editing}]}
        call('scene','apply','--scene',scene,'--request','-',request=select)
        observed=call('scene','inspect','--scene',scene,'--mesh-asset','mesh','--selection-topology')
        preserved={key:value for key,value in observed['mesh_asset'].items() if key!='editing'}
        assert preserved==asset
        (folder/'selected-scene.json').write_bytes(scene.read_bytes())
        for name in ['selected','reloaded']:
            call('render','--scene',scene,'--output',folder/(name+'.png'),'--width',640,'--height',480)
        assert (folder/'selected.png').read_bytes()==(folder/'reloaded.png').read_bytes()
        hidden={'mode':[domain],'selected':{},'hidden':{'vertices':[],'edges':[],'faces':[face]},'history':[],'active_face':None}
        hide={'expected_revision':2,'commands':[{'operation':'set_mesh_editing','id':'mesh','editing':hidden}]}
        call('scene','apply','--scene',scene,'--request','-',request=hide)
        call('render','--scene',scene,'--output',folder/'hidden.png','--width',640,'--height',480)
        images=[read_rgba8(folder/(name+'.png')) for name in ['before','selected','hidden']]
        width,height,_=images[0];assert all(image[:2]==(width,height) for image in images)
        initial,selected_pixel,hidden_pixel=[image[2] for image in images]
        background=hidden_pixel(0,0);selected_background=selected_pixel(0,0)
        different=visible=hidden_visible=0
        for y in range(height):
            for x in range(width):
                different+=initial(x,y)!=selected_pixel(x,y)
                visible+=selected_pixel(x,y)!=selected_background
                hidden_visible+=hidden_pixel(x,y)!=background
        minimum={'vertex':20,'edge':100,'face':1000}[domain]
        assert different>minimum,(domain,different)
        assert visible>1000 and hidden_visible==0,(domain,visible,hidden_visible)
        records.append({'domain':domain,'gpu':gpu,'different_pixels':different,'visible_pixels':visible,
                        'hidden_visible_pixels':hidden_visible,'reloaded_identical':True,'asset_attributes_unchanged':True})
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report={'passed':True,'runs':records,'platform':platform.platform(),'binary_sha256':sha(binary),
            'source_files_sha256':{str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},
            'capture_inputs_sha256':{name:sha(root/name) for name in ['tools/selection_gpu_evidence.py','tools/png_pixels.py','docs/contracts/mesh-selection-core.md']},
            'artifacts':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and not p.name.endswith('.formora.lock')},
            'commands':calls,'full_feature_acceptance':'unrun',
            'unrun':['native window input','Windows GPU','Linux GPU','full modeling parity']}
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'runs':records}))


if __name__=='__main__':main()

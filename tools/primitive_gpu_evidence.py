#!/usr/bin/env python3
"""Render Rust-generated primitives and regenerate their saved parameters on the native GPU."""
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
    args=parser.parse_args();binary=args.binary.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1];scene=output/'scene.json';calls=[]
    def run(*arguments,request=None):
        p=subprocess.run([str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),capture_output=True,text=True,check=True)
        calls.append({'arguments':list(map(str,arguments)),'exit_code':p.returncode,'stdout':p.stdout})
        return json.loads(p.stdout)
    run('scene','init','--scene',scene)
    identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
    shapes=[('plane',-3,{'kind':'plane','size':1.5},[0.1,0.5,0.9,1]),
            ('cube',-1,{'kind':'cube','size':1.5},[0.9,0.3,0.1,1]),
            ('grid',1,{'kind':'grid','size':1.5,'x_subdivisions':4,'y_subdivisions':4},[0.2,0.8,0.3,1]),
            ('circle',3,{'kind':'circle','vertices':16,'radius':0.75,'fill_type':'ngon'},[0.8,0.3,0.8,1])]
    commands=[]
    for name,x,primitive,color in shapes:
        commands.extend([
            {'operation':'set_material','id':name+'_material','material':{'base_color':color,'roughness':0.6,'metallic':0}},
            {'operation':'create_mesh_primitive','id':name,'primitive':primitive},
            {'operation':'create_entity','id':name+'_entity','entity':{'name':name,'parent':None,'transform':{**identity,'translation':[x,0,0.75 if name=='cube' else 0]},'content':{'kind':'mesh','geometry':{'kind':'asset','id':name},'material':name+'_material'}}},
        ])
    angle=math.atan2(8,5.5)
    commands.extend([
        {'operation':'create_entity','id':'camera','entity':{'name':'Camera','parent':None,'transform':{**identity,'translation':[0,-8,6],'rotation':[math.sin(angle/2),0,0,math.cos(angle/2)]},'content':{'kind':'camera','vertical_fov_degrees':55,'near':0.1,'far':100}}},
        {'operation':'set_active_camera','id':'camera'},
        {'operation':'create_entity','id':'light','entity':{'name':'Light','parent':None,'transform':{**identity,'translation':[-2,-3,6]},'content':{'kind':'light','color':[1,1,1],'intensity':120}}},
    ])
    creation={'expected_revision':0,'commands':commands};(output/'creation-request.json').write_text(json.dumps(creation,indent=2)+'\n')
    run('scene','apply','--scene',scene,'--request','-',request=creation)
    gpu=run('render','--scene',scene,'--output',output/'before.png','--width',1200,'--height',700)['gpu']
    w,h,pixel=read_rgba8(output/'before.png');assert (w,h)==(1200,700);background=pixel(0,0)
    probes=[]
    for name,x,primitive,color in shapes:
        point=[x,-0.75,0.75] if name=='cube' else [x,0,0]
        dy,dz=point[1]+8,point[2]-6
        cy=math.cos(angle)*dy+math.sin(angle)*dz;depth=math.sin(angle)*dy-math.cos(angle)*dz
        factor=350/(depth*math.tan(math.radians(55/2)))
        xy=(round(600+point[0]*factor),round(350-cy*factor));value=pixel(*xy)
        assert value!=background,(name,xy,value)
        probes.append({'primitive':name,'world':point,'pixel':xy,'rgba':value})
    def screen(point):
        dy,dz=point[1]+8,point[2]-6
        cy=math.cos(angle)*dy+math.sin(angle)*dz;depth=math.sin(angle)*dy-math.cos(angle)*dz
        factor=350/(depth*math.tan(math.radians(55/2)))
        return round(600+point[0]*factor),round(350-cy*factor)
    growth_probes=[]
    for name,point in [('plane',[-3.9,0,0]),('cube',[-2,-0.9,1.5]),('grid',[1.9,0,0]),('circle',[3.85,0,0])]:
        xy=screen(point);value=pixel(*xy)
        assert value==background,(name,'growth point not initially empty',xy,value)
        growth_probes.append({'primitive':name,'world':point,'pixel':xy,'before_rgba':value})
    changed=[{'kind':'plane','size':2},{'kind':'cube','size':2.25},{'kind':'grid','size':2,'x_subdivisions':6,'y_subdivisions':3},{'kind':'circle','vertices':7,'radius':1,'fill_type':'ngon'}]
    rebuild={'expected_revision':1,'commands':[{'operation':'regenerate_mesh_primitive','id':name,'primitive':p} for (name,*rest),p in zip(shapes,changed)]}
    (output/'regenerate-request.json').write_text(json.dumps(rebuild,indent=2)+'\n')
    run('scene','apply','--scene',scene,'--request','-',request=rebuild)
    run('render','--scene',scene,'--output',output/'after-regenerate.png','--width',1200,'--height',700)
    run('render','--scene',scene,'--output',output/'reopened.png','--width',1200,'--height',700)
    _,_,after_pixel=read_rgba8(output/'after-regenerate.png')
    for probe in growth_probes:
        value=after_pixel(*probe['pixel']);assert value!=background,(probe['primitive'],'no visible growth')
        probe['after_rgba']=value
    assert (output/'before.png').read_bytes()!=(output/'after-regenerate.png').read_bytes()
    assert (output/'after-regenerate.png').read_bytes()==(output/'reopened.png').read_bytes()
    query=run('scene','inspect','--scene',scene)
    for name,*rest in shapes:
        asset=query['scene']['mesh_assets'][name];assert not asset['recipe']['edited']
        assert query['scene']['entities'][name+'_entity']['content']['geometry']['id']==name
    artifacts=['before.png','after-regenerate.png','reopened.png','scene.json','creation-request.json','regenerate-request.json']
    manifest={'scope':'Rust procedural generation and regeneration; finite native Metal evidence','full_feature_acceptance':'unrun','platform':platform.platform(),'gpu':gpu,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
              'source_files_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},
              'capture_inputs_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['tools/primitive_gpu_evidence.py','tools/png_pixels.py','docs/contracts/primitive-generation.md']},
              'artifacts':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in artifacts},'pixel_probes':probes,'per_primitive_growth_probes':growth_probes,'background_rgba':background,'parameter_change_visible':True,'reopened_png_identical':True,'asset_identity_preserved':True,'commands':calls,
              'unrun':['native window input','Windows GPU','Linux GPU','loose-edge drawing','full primitive parameter domains','full modeling parity']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'gpu':gpu,'generated_primitives_visible':4,'parameter_change_visible':True,'reload_identical':True}))


if __name__=='__main__':main()

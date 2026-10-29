"""Render actual snap geometry with native Metal and verify fresh reload."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools'))
from png_pixels import read_rgba8
from compare_snap_menu_reference import f32, snapped


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();binary=args.binary.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(binary)
    paths=sorted([ROOT/'Cargo.toml',ROOT/'Cargo.lock',*[p for p in (ROOT/'src').rglob('*') if p.is_file()]])
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths};calls=[];scene=out/'scene.json'
    def call(*arguments,request=None):
        p=subprocess.run([str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),capture_output=True,text=True)
        calls.append({'arguments':list(map(str,arguments)),'request':request,'stdout':p.stdout,'stderr':p.stderr,'exit_code':p.returncode})
        assert p.returncode==0,p.stdout+p.stderr;return json.loads(p.stdout)
    vertices={f'v{5*y+x:04}':[(x-2)*.5,(y-2)*.5,(y-2)*.225] for y in range(5) for x in range(5)}
    faces={};pairs=set()
    for y in range(4):
        for x in range(4):
            ids=[f'v{5*y+x:04}',f'v{5*y+x+1:04}',f'v{5*(y+1)+x+1:04}',f'v{5*(y+1)+x:04}']
            faces[f'f{4*y+x:04}']={'vertices':ids,'uv_layers':{'UV':[[vertices[id][0],vertices[id][1]] for id in ids]},
                'normal':None,'corner_normals':None,'smooth':True,'material_slot':None}
            for i in range(4):pairs.add(tuple(sorted([ids[i-1],ids[i]])))
    asset={'vertices':vertices,'edges':{f'e{i:04}':list(pair) for i,pair in enumerate(sorted(pairs))},
        'polygons':faces,'triangles':{},'material_slots':[],'uv_layout':{'layers':['UV'],'active':'UV'}}
    identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
    def entity(id,content,transform):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':None,'transform':transform,'content':content}}
    call('scene','init','--scene',scene)
    call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':0,'commands':[
        {'operation':'set_mesh_asset','id':'mesh','asset':asset},
        {'operation':'set_mesh_editing','id':'mesh','editing':{'selected':{'vertices':sorted(vertices)},'preview':False}},
        entity('surface',{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None},{**identity,'precision':'f32'}),
        entity('camera',{'kind':'camera','vertical_fov_degrees':45,'near':.1,'far':100},
            {**identity,'translation':[0,-4,4],'rotation':[math.sin(math.pi/8),0,0,math.cos(math.pi/8)]}),
        {'operation':'set_active_camera','id':'camera'},
        entity('light',{'kind':'light','color':[1,1,1],'intensity':2},{**identity,'translation':[1,-3,5]})]})
    before=call('scene','inspect','--scene',scene)['scene'];(out/'before-scene.json').write_bytes(scene.read_bytes())
    gpu=call('render','--scene',scene,'--output',out/'before.png','--width',640,'--height',480)['gpu'];assert '(Metal,' in gpu,gpu
    receipt=call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':1,'commands':[
        {'operation':'snap_mesh','snap':{'entity':'surface','action':{'kind':'selected_to_grid','spacing':.6},'pivot':'median'}}]})
    after=call('scene','inspect','--scene',scene)['scene'];q=call('scene','inspect','--scene',scene,'--mesh-asset','mesh','--normals')
    mesh=q['mesh_asset'];old=before['mesh_assets']['mesh'];expected={id:snapped([f32(x) for x in p],f32(.6)) for id,p in vertices.items()}
    assert mesh['vertices']==expected;assert mesh['edges']==old['edges'] and mesh['editing']==old['editing']
    assert after['entities']==before['entities'] and mesh['uv_layout']==old['uv_layout']
    for id,p in old['polygons'].items():
        assert {k:v for k,v in mesh['polygons'][id].items() if k not in ['normal','corner_normals']}=={k:v for k,v in p.items() if k not in ['normal','corner_normals']}
    changed={id for id,p in old['vertices'].items() if p!=mesh['vertices'][id]};assert len(changed)==24
    assert set(receipt['snaps'][0]['changed']['vertices'])==changed and receipt['snaps'][0]['shared_instances']==['surface']
    for name in ['after','reloaded']:call('render','--scene',scene,'--output',out/(name+'.png'),'--width',640,'--height',480)
    assert (out/'after.png').read_bytes()==(out/'reloaded.png').read_bytes()
    w,h,a=read_rgba8(out/'before.png');wb,hb,b=read_rgba8(out/'after.png');assert (w,h)==(wb,hb)
    pixels=sum(a(x,y)!=b(x,y) for y in range(h) for x in range(w));assert pixels>100
    for name,value in [('receipt',receipt),('normals-query',q)]: (out/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
    assert binary_sha==sha(binary) and hashes=={p.relative_to(ROOT).as_posix():sha(p) for p in paths}
    report={'passed':True,'binary_sha256':binary_sha,'driver_sha256':sha(Path(__file__)),'source_hashes':hashes,'gpu':gpu,
        'changed_vertices':24,'changed_pixels':pixels,'analytic_grid_geometry_matches':True,'preserved_attributes':True,
        'fresh_reload_images_identical':True,'calls':calls,'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file() and not p.name.endswith('.formora.lock')},
        'scope':'Actual native Metal snapped surface and saved fresh reload; full feature and milestone acceptance remain unrun.'}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','gpu','changed_vertices','changed_pixels','fresh_reload_images_identical']}))


if __name__=='__main__':main()

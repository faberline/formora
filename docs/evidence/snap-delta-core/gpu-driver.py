"""Show actual nonunit delta geometry and child compensation with native Metal."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools'))
from png_pixels import read_rgba8
from compare_snap_menu_reference import f32, tree


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();binary=args.binary.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(binary)
    paths=sorted([ROOT/'Cargo.toml',ROOT/'Cargo.lock',*[p for p in (ROOT/'src').rglob('*') if p.is_file()]])
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths};calls=[];scene=out/'scene.json'
    def call(*arguments,request=None):
        p=subprocess.run([str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),capture_output=True,text=True)
        record={'arguments':list(map(str,arguments)),'request':request,'stdout':p.stdout,'stderr':p.stderr,'exit_code':p.returncode};calls.append(record)
        with (out/'calls.jsonl').open('a') as stream:stream.write(json.dumps(record,allow_nan=False)+'\n')
        assert p.returncode==0,p.stdout+p.stderr;return json.loads(p.stdout)
    vertices={f'v{5*y+x:04}':[(x-2)*.5,(y-2)*.5,(y-2)*.225] for y in range(5) for x in range(5)}
    faces={};pairs=set()
    for y in range(4):
        for x in range(4):
            ids=[f'v{5*y+x:04}',f'v{5*y+x+1:04}',f'v{5*(y+1)+x+1:04}',f'v{5*(y+1)+x:04}']
            faces[f'f{4*y+x:04}']={'vertices':ids,'uv_layers':{'UV':[[vertices[id][0],vertices[id][1]] for id in ids]},
                'normal':None,'corner_normals':None,'smooth':True,'material_slot':None}
            for i in range(4):pairs.add(tuple(sorted([ids[i-1],ids[i]])))
    asset={'vertices':vertices,'edges':{f'e{i:04}':list(pair) for i,pair in enumerate(sorted(pairs))},'polygons':faces,
        'triangles':{},'material_slots':[],'uv_layout':{'layers':['UV'],'active':'UV'}}
    raw={'mode':'quaternion','euler':[.12345678901234567,-.27,.43],'quaternion_wxyz':[1.,0.,0.,0.],'axis_angle':[.71,-3.,2.,4.]}
    cursor={**raw,'quaternion_wxyz':[.8,.1,.1,math.sqrt(.34)]}
    identity={'translation':[0,0,0],'rotation':{'kind':'euler','angles':[0,0,0],'order':'xyz'},'scale':[1,1,1],'precision':'f32'}
    def entity(id,content,transform,parent=None):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':parent,'transform':transform,'content':content}}
    mesh={'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}
    call('scene','init','--scene',scene)
    setup={'expected_revision':0,'commands':[
        {'operation':'set_mesh_asset','id':'mesh','asset':asset},
        {'operation':'set_mesh_editing','id':'mesh','editing':{'selected':{'vertices':sorted(vertices)},'preview':False}},
        {'operation':'set_material','id':'marker','material':{'base_color':[.9,.15,.1,1],'roughness':.6,'metallic':0}},
        entity('surface',mesh,{**identity,'translation':[.25,-.5,.75],'rotation':{'kind':'channels','channels':raw}}),
        entity('shared',mesh,{**identity,'translation':[1.75,.25,.25]}),
        entity('child',{'kind':'mesh','geometry':{'kind':'cube','size':[.3,.3,.3]},'material':'marker'},{**identity,'translation':[0,0,1]},'surface'),
        entity('camera',{'kind':'camera','vertical_fov_degrees':55,'near':.1,'far':100},
            {**identity,'translation':[1,-4,4],'rotation':[math.sin(math.pi/8),0,0,math.cos(math.pi/8)],'precision':'f64'}),
        {'operation':'set_active_camera','id':'camera'},
        entity('light',{'kind':'light','color':[1,1,1],'intensity':2},{**identity,'translation':[1,-3,5]}),
        {'operation':'set_authoring_context','context':{'cursor_location':[.375,-.625,.875],'cursor_rotation':cursor['euler'],'cursor_orientation':cursor}},
        {'operation':'set_object_context','context':{'order':['surface','shared','child','camera','light'],'selected':['surface'],
            'active':'surface','edit_objects':[],'skip_children':True,'origins_only':True,'states':{'surface':{'lock_rotation':[True,False,False],'lock_rotation_w':False,'lock_rotations_4d':True}}}}]}
    delta={'translation':[.125,-.25,.375], 'euler':[.21345678901234567,-.31789,.4789],
           'quaternion_wxyz':[-2.,0.,0.,-2.], 'scale':[1.,1.,1.]}
    setup['commands'][3]['entity']['transform']['delta']=delta
    call('scene','apply','--scene',scene,'--request','-',request=setup)
    before=call('scene','inspect','--scene',scene)['scene'];(out/'before-scene.json').write_bytes(scene.read_bytes())
    old_world={id:call('scene','inspect','--scene',scene,'--entity',id,'--world') for id in ['surface','shared','child']}
    gpu=call('render','--scene',scene,'--output',out/'before.png','--width',640,'--height',480)['gpu'];assert '(Metal,' in gpu,gpu
    receipt=call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':1,'commands':[
        {'operation':'snap_scene','snap':{'action':{'kind':'selected_to_cursor','use_offset':False,'use_rotation':True},'pivot':'median'}}]})
    after=call('scene','inspect','--scene',scene)['scene'];q=call('scene','inspect','--scene',scene,'--mesh-asset','mesh','--normals')
    world={id:call('scene','inspect','--scene',scene,'--entity',id,'--world') for id in ['surface','shared','child']}
    stored=after['entities']['surface']['transform']['rotation']['channels']
    raw_q=[f32(.8),0.,f32(.1),f32(math.sqrt(.34))]
    assert stored=={**raw,'quaternion_wxyz':raw_q}
    assert abs(sum(v*v for v in raw_q)-1.)>.005
    length=math.sqrt(sum(v*v for v in raw_q));w,x,y,z=[v/length for v in raw_q]
    rotation=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
              [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
              [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
    expected={id:[sum(rotation[j][i]*(p[j]+[-.125,0.,.25][j]) for j in range(3)) for i in range(3)] for id,p in vertices.items()}
    updated=q['mesh_asset'];old=before['mesh_assets']['mesh'];tree(expected,updated['vertices'],'analytic raw rotation local geometry')
    assert updated['editing']==old['editing'] and updated['edges']==old['edges'] and updated['uv_layout']==old['uv_layout']
    for id,p in old['polygons'].items():
        assert {k:v for k,v in updated['polygons'][id].items() if k not in ['normal','corner_normals']}=={k:v for k,v in p.items() if k not in ['normal','corner_normals']}
    assert after['entities']['surface']['transform']['translation']==[.25,-.375,.5]
    assert after['entities']['surface']['transform']['delta']==before['entities']['surface']['transform']['delta']==delta
    tree(old_world['surface']['world_vertices'],world['surface']['world_vertices'],'preserved surface world')
    tree(old_world['child']['world_matrix'],world['child']['world_matrix'],'preserved child world')
    assert after['entities']['child']==before['entities']['child']
    assert world['child']['object_frames']['matrix_parent_inverse']!=old_world['child']['object_frames']['matrix_parent_inverse']
    tree({id:[p[j]+[1.75,.25,.25][j] for j in range(3)] for id,p in expected.items()},world['shared']['world_vertices'],'analytic shared world geometry')
    assert after['entities']['shared']==before['entities']['shared'] and len(after['mesh_assets'])==1
    result=receipt['scene_snaps'][0];assert len(result['meshes'])==1 and result['meshes'][0]['shared_instances']==['shared','surface']
    assert result['meshes'][0]['changed']['vertices']==sorted(vertices)
    assert {item['entity'] for item in result['objects']}=={'surface','child'}
    for name in ['after','reloaded']:call('render','--scene',scene,'--output',out/(name+'.png'),'--width',640,'--height',480)
    assert (out/'after.png').read_bytes()==(out/'reloaded.png').read_bytes()
    w,h,a=read_rgba8(out/'before.png');wb,hb,b=read_rgba8(out/'after.png');assert (w,h)==(wb,hb)
    pixels=sum(a(x,y)!=b(x,y) for y in range(h) for x in range(w));assert pixels>100
    for name,value in [('receipt',receipt),('normals-query',q),('world-before',old_world),('world-after',world)]:
        (out/(name+'.json')).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    assert binary_sha==sha(binary) and hashes=={p.relative_to(ROOT).as_posix():sha(p) for p in paths}
    report={'passed':True,'binary_sha256':binary_sha,'driver_sha256':sha(Path(__file__)),'source_hashes':hashes,'gpu':gpu,
        'raw_nonunit_delta_and_inactive_values_preserved':True,'analytic_delta_compensation_checked':True,'source_driver_reused':'docs/evidence/snap-rotation-core/gpu-driver.py','raw_nonunit_quaternion_preserved':True,'wxyz_mapping_and_inactive_channels_checked':True,'changed_vertices':25,'changed_pixels':pixels,'analytic_shared_geometry_matches':True,'surface_world_unchanged':True,
        'child_world_unchanged':True,'child_parent_inverse_changed':True,'preserved_attributes':True,'fresh_reload_images_identical':True,
        'setup':setup,'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file() and not p.name.endswith('.formora.lock')},
        'product_acceptance':'unrun','milestone_acceptance':'unrun'}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','gpu','changed_vertices','changed_pixels','fresh_reload_images_identical']}))


if __name__=='__main__':main()

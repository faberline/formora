#!/usr/bin/env python3
"""Actual export rejections preserve the mother and do not publish output. CI only."""
import copy
import json
from pathlib import Path
import sys
from static_usd_runtime import Runner, native_expected, sha

binary=Path(sys.argv[1]).resolve()
if not binary.exists() and binary.with_suffix('.exe').exists():binary=binary.with_suffix('.exe')
output=Path(sys.argv[2]).resolve();output.mkdir(parents=True,exist_ok=False)
runner=Runner(output);original=native_expected('crate');cases=[]
def case(name,edit,message):
    scene=copy.deepcopy(original);edit(scene);cases.append((name,json.dumps(scene),message))
mesh_id='crate_body'
case('unknown_field',lambda s:s.update(unknown_field=True),'unknown field')
case('missing_asset',lambda s:s['entities']['crate_body']['content']['geometry'].update(id='absent'),'missing mesh asset')
case('missing_material',lambda s:s['materials'].pop('wood'),'material')
case('precision_limit',lambda s:s['mesh_assets'][mesh_id]['vertices']['v0'].__setitem__(0,1000.0000015),'1e-6')
case('isolated_vertex',lambda s:s['mesh_assets'][mesh_id]['vertices'].update(loose=[0,0,0]),'isolated')
case('loose_edge',lambda s:s['mesh_assets'][mesh_id].update(edges={'wire':['v0','v6']}),'loose')
case('partial_uv',lambda s:s['mesh_assets'][mesh_id]['triangles']['f000']['uv_layers'].update(UV=[[0,0],[1,0],[0,1]]),'UV')
case('recipe',lambda s:s['mesh_assets'][mesh_id].update(recipe={'primitive':{'kind':'cube','size':2},'max_components':1000,'edited':False}),'unsupported')
case('skin_groups',lambda s:s['mesh_assets'][mesh_id].update(vertex_groups=['skin']),'unsupported')
case('nonstatic_time',lambda s:s.update(time_seconds=1),'nonstatic')
case('annotation',lambda s:s['annotations'].append({'entity':'crate','position':[0,0,0],'text':'keep annotation in mother'}),'unsupported')
case('builtin_geometry',lambda s:s['entities']['crate_body']['content'].update(geometry={'kind':'cube','size':[.8,.6,.6]}),'unsupported entity')
case('camera',lambda s:s['entities'].update(camera={'name':'camera','parent':'crate','transform':{'translation':[0,0,1],'rotation':[0,0,0,1],'scale':[1,1,1]},'content':{'kind':'camera','vertical_fov_degrees':45,'near':.01,'far':100}}),'unsupported entity')
cases.append(('invalid_json','{',''))
# Parse-time duplicate maps must not be silently collapsed before export.
text=json.dumps(original);cases.append(('duplicate_map',text.replace('"materials": {','"materials": {"dup":{"base_color":[1,1,1,1],"roughness":0.5,"metallic":0},"dup":{"base_color":[1,1,1,1],"roughness":0.5,"metallic":0},',1),'duplicate ID'))
# A valid scene can still exceed the frozen export entity/depth limit.
def too_deep(s):
    parent='crate'
    for i in range(129):
        id='depth_'+str(i);s['entities'][id]={'name':id,'parent':parent,'transform':{'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]},'content':{'kind':'empty'}};parent=id
case('depth_limit',too_deep,'depth limit')
records=[]
for name,text,message in cases:
    folder=output/name;folder.mkdir();scene=folder/'mother.json';target=folder/'no.usda';scene.write_text(text)
    before=scene.read_bytes()
    result=runner.run([binary,'scene','export','--scene',scene,'--root','crate','--format','usda','--output',target],fail=True)
    error=result['error'];assert message.lower() in error.lower(),(name,message,error)
    assert before==scene.read_bytes() and not target.exists()
    assert not list(folder.glob('.formora-usd-*.tmp')),'failed export left staging file'
    records.append({'case':name,'error':error,'mother_sha256':sha(scene),'output_absent':True,'source_unchanged':True})
# A real existing target is preserved, including contents, and a path through a
# regular file is unwritable on every OS without relying on root/chmod policy.
folder=output/'targets';folder.mkdir();scene=folder/'mother.json';scene.write_text(json.dumps(original));target=folder/'existing.usda';target.write_bytes(b'USER FILE\n')
result=runner.run([binary,'scene','export','--scene',scene,'--root','crate','--format','usda','--output',target],fail=True);assert target.read_bytes()==b'USER FILE\n'
blocked=folder/'parent-file';blocked.write_bytes(b'parent marker');no=blocked/'no.usda'
runner.run([binary,'scene','export','--scene',scene,'--root','crate','--format','usda','--output',no],fail=True);assert blocked.read_bytes()==b'parent marker' and not no.exists()
assert not list(folder.glob('.formora-usd-*.tmp'))
report={'passed':True,'cases':records,'existing_target_preserved':True,'unwritable_parent_rejected':True,'binary_sha256':sha(binary)}
(output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)

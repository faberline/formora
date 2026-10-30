"""Render actual persistent merge topology before/after/fresh reload on Metal."""
import copy
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'tools'))
from png_pixels import read_rgba8

OUTPUT=Path('/private/tmp/formora-merge-gpu-01')
BINARY=Path('/private/tmp/formora-merge-allfeatures-actual185/debug/formora')
AUTHORED=Path('/private/tmp/formora-merge-authored-input-01.json')
OUTPUT.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_hash=sha(BINARY)
scene=OUTPUT/'scene.json';initial=json.loads(AUTHORED.read_bytes())
initial['materials']['paint']={'base_color':[0.95,0.25,0.08,1.],'roughness':0.55,'metallic':0.}
for entity in initial['entities'].values():
    if entity['content']['kind']=='mesh':entity['content']['material']='paint'
scene.write_text(json.dumps(initial)+'\n');calls=[]
def call(*arguments,request=None):
    command=[str(BINARY),*map(str,arguments)]
    process=subprocess.run(command,input=None if request is None else json.dumps(request),capture_output=True,text=True)
    calls.append({'command':command,'request':request,'exit':process.returncode,'stdout':process.stdout,'stderr':process.stderr})
    (OUTPUT/'calls.json').write_text(json.dumps(calls,indent=2)+'\n');assert process.returncode==0,(process.stdout,process.stderr)
    return json.loads(process.stdout)
def entity(id,content,translation,rotation):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':None,'transform':{'translation':translation,'rotation':rotation,'scale':[1.,1.,1.]},'content':content}}
call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':0,'commands':[
    entity('camera',{'kind':'camera','vertical_fov_degrees':45.,'near':0.1,'far':100.},[20.,3.5,5.5],[0.,math.sqrt(.5),0.,math.sqrt(.5)]),
    {'operation':'set_active_camera','id':'camera'},
    entity('light',{'kind':'light','color':[1.,1.,1.],'intensity':3.},[12.,6.,10.],[0.,0.,0.,1.])
]})
queries={};gpus=[]
def capture(name):
    value=call('scene','inspect','--scene',scene);queries[name]=value
    (OUTPUT/(name+'-scene.json')).write_bytes(scene.read_bytes())
    queries[name+'-mesh']=call('scene','inspect','--scene',scene,'--mesh-asset','mesh','--normals')
    result=call('render','--scene',scene,'--output',OUTPUT/(name+'.png'),'--width',640,'--height',480)
    assert '(Metal,' in result['gpu'],result
    gpus.append(result['gpu'])
capture('before')
result=call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':1,'commands':[{'operation':'merge_mesh','merge':{'entity':'owner','method':'center','uvs':True}}]})
assert result['revision']==2 and result['merges'][0]['shared_instances']==['owner','shared']
capture('after');capture('reloaded')
assert queries['after']==queries['reloaded'] and queries['after-mesh']==queries['reloaded-mesh']
assert (OUTPUT/'after.png').read_bytes()==(OUTPUT/'reloaded.png').read_bytes()
old=queries['before']['scene'];new=queries['after']['scene']
assert old['entities']==new['entities'] and old['materials']==new['materials'] and len(new['mesh_assets'])==1
assert len(old['mesh_assets']['mesh']['vertices'])==9 and len(new['mesh_assets']['mesh']['vertices'])==8
assert old['mesh_assets']['mesh']['polygons']['p']['vertices']==['a','b','c','d','e','f']
assert new['mesh_assets']['mesh']['polygons']['p']['vertices']==['a','d','e','f']
assert old['mesh_assets']['mesh']['triangles']['t']==new['mesh_assets']['mesh']['triangles']['t']
w,h,before=read_rgba8(OUTPUT/'before.png');w2,h2,after=read_rgba8(OUTPUT/'after.png');assert (w,h)==(w2,h2)==(640,480)
changed=sum(before(x,y)!=after(x,y) for y in range(h) for x in range(w));assert changed>500,changed
assert sha(BINARY)==binary_hash
(OUTPUT/'queries.json').write_text(json.dumps(queries,indent=2)+'\n')
report={'passed':True,'changed_pixels':changed,'gpu':gpus,'platform':platform.platform(),'binary_sha256':binary_hash,
    'product_implementation':'224a4360276511f48d023a2f6f39190010dae731','authored_input_sha256':sha(AUTHORED),
    'actual_shared_asset_and_topology_checked':True,'unselected_triangle_preserved':True,'fresh_process_reload_and_render_identical':True,
    'render_processes':[row for row in calls if row['command'][1]=='render'],'native_cli_exits':[row['exit'] for row in calls],
    'artifacts':{p.name:sha(p) for p in OUTPUT.iterdir() if p.is_file()},'product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUTPUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({key:report[key] for key in ['passed','changed_pixels','gpu','fresh_process_reload_and_render_identical']}),flush=True)

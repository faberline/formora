"""Check real generator recipes through snap, rollback, undo and regeneration."""
from pathlib import Path
import hashlib,json,subprocess,sys

root=Path(__file__).resolve().parents[3];binary=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(exist_ok=False)
path=out/'scene.json';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(binary);calls=[]
subprocess.run([str(binary),'scene','init','--scene',str(path)],check=True,capture_output=True)
with subprocess.Popen([str(binary),'scene','serve','--scene',str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as process:
    sequence=0
    def call(name,args,error=False):
        global sequence
        sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':args})+'\n');process.stdin.flush()
        response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok'] is (not error),response
        calls.append({'name':name,'arguments':args,'response':response})
        with (out/'calls.jsonl').open('a') as stream:stream.write(json.dumps(calls[-1],allow_nan=False)+'\n')
        return response['error'] if error else response['result']
    def inspect():return call('scene_inspect',{})['scene']
    created=call('scene_apply',{'expected_revision':0,'commands':[
        {'operation':'create_mesh_object','creation':{'id':'cube','asset':'mesh','name':'Recipe cube','primitive':{'kind':'cube','size':1.3}}},
        {'operation':'set_authoring_context','context':{'cursor_location':[2.1,-1.3,.7],'cursor_rotation':[.17,.23,.41]}},
        {'operation':'set_transform','id':'cube','transform':{'translation':[.25,-.5,.75],'rotation':{'kind':'euler','angles':[0,0,0],'order':'xyz'},'scale':[1,1,1],'precision':'f32'}},
        {'operation':'set_object_context','context':{'order':['cube'],'selected':['cube'],'active':'cube','edit_objects':[],'origins_only':True}}]})
    original=inspect()['mesh_assets']['mesh'];assert original['recipe']['edited'] is False
    call('scene_apply',{'expected_revision':1,'commands':[{'operation':'set_mesh_editing','id':'mesh','editing':{
        'mode':['vertex'],'selected':{'vertices':sorted(original['vertices'])},'preview':False}}]})
    call('scene_apply',{'expected_revision':2,'commands':[{'operation':'snap_scene','snap':{'action':{'kind':'cursor_to_center'}}}]})
    before=inspect();assert before['mesh_assets']['mesh']['recipe']['edited'] is False
    snap={'operation':'snap_scene','snap':{'action':{'kind':'selected_to_grid','spacing':.75}}}
    saved=path.read_bytes();call('scene_apply',{'expected_revision':3,'commands':[snap,{'operation':'delete_entity','id':'missing'}]},error=True)
    assert inspect()==before and path.read_bytes()==saved
    result=call('scene_apply',{'expected_revision':3,'commands':[snap]});after=inspect();asset=after['mesh_assets']['mesh']
    assert asset['recipe']=={**before['mesh_assets']['mesh']['recipe'],'edited':True}
    assert set(result['scene_snaps'][0]['meshes'][0]['changed']['vertices'])==set(original['vertices']) and len(original['vertices'])==8
    call('scene_undo',{'expected_revision':4});restored=inspect();assert {k:v for k,v in restored.items() if k!='revision'}=={k:v for k,v in before.items() if k!='revision'}
    replay=call('scene_apply',{'expected_revision':5,'commands':[snap]});assert replay['scene_snaps']==result['scene_snaps']
    call('scene_apply',{'expected_revision':6,'commands':[{'operation':'regenerate_mesh_primitive','id':'mesh'}]})
    regenerated=inspect();asset=regenerated['mesh_assets']['mesh'];assert asset['recipe']['edited'] is False
    for key in ['vertices','edges','polygons','triangles','uv_layout']:assert asset.get(key)==original.get(key),key
    assert regenerated['entities']==after['entities']
    process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();assert process.returncode==0,stderr
fresh=subprocess.run([str(binary),'scene','inspect','--scene',str(path)],capture_output=True,text=True,check=True)
assert json.loads(fresh.stdout)['scene']==regenerated and binary_sha==sha(binary)
for name,value in [('before',before),('after',after),('regenerated',regenerated),('receipt',result)]: (out/(name+'.json')).write_text(json.dumps(value,allow_nan=False)+'\n')
report={'passed':True,'binary_sha256':binary_sha,'driver_sha256':sha(Path(__file__)),'native_terminal_exit':process.returncode,'fresh_process_exit':fresh.returncode,
    'cursor_only_preserves_recipe':True,'geometry_edit_marks_recipe':True,'failed_batch_preserves_recipe_and_disk':True,
    'undo_replay_checked':True,'regeneration_restores_original_authored_geometry_and_attributes':True,'fresh_reload_equal':True,
    'calls':calls,'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file() and not p.name.endswith('.formora.lock')},'product_acceptance':'unrun'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'recipe_rollback_undo_replay_regeneration':True}))

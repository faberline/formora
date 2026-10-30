"""Actual native merge save failure, rollback, undo, replay and fresh reload."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')
OUTPUT=Path('/private/tmp/formora-multi-merge-retained-failed-save-01')
BINARY=Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
AUTHORED=Path('/private/tmp/formora-merge-authored-input-01.json')
OUTPUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
binary_hash=sha(BINARY);scene=OUTPUT/'scene.json';shutil.copyfile(AUTHORED,scene)
profile=Path('/private/tmp/formora-multi-merge-retained-native-drivers-01/profile.sb').read_text()
denial=subprocess.run(['/usr/bin/sandbox-exec','-p',profile,'/bin/cat',str(ROOT/'Cargo.toml')],capture_output=True,text=True,cwd=OUTPUT)
assert denial.returncode==1 and not denial.stdout and 'Cargo.toml' in denial.stderr and 'Operation not permitted' in denial.stderr
calls=[];command=['/usr/bin/sandbox-exec','-p',profile,str(BINARY),'scene','serve','--scene',str(scene)]
process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=OUTPUT)
def call(name,arguments):
    request={'id':len(calls)+1,'name':name,'arguments':arguments}
    process.stdin.write(json.dumps(request)+'\n');process.stdin.flush()
    line=process.stdout.readline();assert line,'native server ended without a result'
    response=json.loads(line);assert response['id']==request['id']
    calls.append({'request':request,'raw_response':line,'response':response})
    (OUTPUT/'calls.json').write_text(json.dumps(calls,indent=2)+'\n')
    return (response['result'],None) if response['ok'] else (None,response['error'])
def inspect():
    value,error=call('scene_inspect',{});assert error is None,error
    return value['scene']
merge={'operation':'merge_mesh','merge':{'entity':'owner','method':'center','uvs':True}}
try:
    initial=inspect();saved=scene.read_bytes();assert initial['revision']==0
    for request in [
        {'expected_revision':9,'commands':[merge]},
        {'expected_revision':0,'commands':[{'operation':'merge_mesh','merge':{'entity':'owner','method':'center','max_components':1}}]},
        {'expected_revision':0,'commands':[{'operation':'merge_mesh','merge':{'entity':'owner','method':'center','reference_path':'forbidden-answer.json'}}]},
        {'expected_revision':0,'commands':[merge,{'operation':'set_mesh_vertices','id':'missing','positions':{'a':[0.,0.,0.]}}]},
    ]:
        result,error=call('scene_apply',request);assert result is None and error
        assert inspect()==initial and scene.read_bytes()==saved,'rejected request changed memory, revision or disk'
    backup=OUTPUT/'original-backup.json';scene.rename(backup);scene.mkdir()
    result,error=call('scene_apply',{'expected_revision':0,'commands':[merge]})
    save_error=error;assert result is None and error and 'Is a directory' in error and '21' in error,error
    assert inspect()==initial and backup.read_bytes()==saved and list(scene.iterdir())==[]
    result,error=call('scene_undo',{'expected_revision':0});assert result is None and error and 'nothing to undo' in error,error
    assert inspect()==initial
    scene.rename(OUTPUT/'failed-save-directory');backup.rename(scene)
    result,error=call('scene_apply',{'expected_revision':0,'commands':[merge]});assert error is None,error
    after=inspect();assert after['revision']==result['revision']==1
    assert len(result['merges'])==1 and result['merges'][0]['shared_instances']==['owner','shared']
    mesh=after['mesh_assets']['mesh'];assert mesh['polygons']['p']['vertices']==['a','d','e','f'] and len(mesh['vertices'])==8
    assert mesh['polygons']['p']['uv_layers']['Layout'][1]==initial['mesh_assets']['mesh']['polygons']['p']['uv_layers']['Layout'][3]
    assert mesh['triangles']['t']==initial['mesh_assets']['mesh']['triangles']['t']
    assert mesh['integer_attributes']['vertices']['signed']['a']==-1
    assert mesh['integer_attributes']['vertices']['tag']['a']==mesh['integer_attributes']['vertices']['tag']['b']==7
    assert after['entities']==initial['entities'] and len(after['mesh_assets'])==1
    result,error=call('scene_undo',{'expected_revision':1});assert error is None and result['revision']==2
    undone=inspect();expected=copy.deepcopy(initial);expected['revision']=2;assert undone==expected
    result,error=call('scene_apply',{'expected_revision':2,'commands':[merge]});assert error is None and result['revision']==3
    replayed=inspect();expected=copy.deepcopy(after);expected['revision']=3;assert replayed==expected
finally:
    process.stdin.close();terminal=process.wait(timeout=20);stderr=process.stderr.read();process.stdout.close();process.stderr.close()
    (OUTPUT/'native-stderr').write_text(stderr)
    (OUTPUT/'terminal.json').write_text(json.dumps({'native_process_id':process.pid,'terminal_exit':terminal,'command':command},indent=2)+'\n')
assert terminal==0,stderr
fresh_command=['/usr/bin/sandbox-exec','-p',profile,str(BINARY),'scene','inspect','--scene',str(scene)]
fresh=subprocess.run(fresh_command,capture_output=True,text=True,cwd=OUTPUT);assert fresh.returncode==0,fresh.stderr
assert json.loads(fresh.stdout)['scene']==replayed
assert binary_hash==sha(BINARY)
report={'passed':True,'native_calls':len(calls),'native_process_id':process.pid,'native_terminal_exit':terminal,
    'actual_failed_save_error':save_error,'memory_disk_revision_and_undo_preserved':True,'actual_undo_and_replay':True,'fresh_process_reload_equal':True,
    'repository_and_prior_results_reads_denied':True,'denial_control':{'exit':denial.returncode,'stderr':denial.stderr},
    'fresh_process':{'command':fresh_command,'exit':fresh.returncode,'stdout':fresh.stdout,'stderr':fresh.stderr},
    'binary_sha256':binary_hash,'authored_input_sha256':sha(AUTHORED),'scene_sha256':sha(scene),
    'product_implementation':'bd13f3d424f2649b4b25c16305c4e5b0eb7f8542','product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUTPUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({key:report[key] for key in ['passed','native_calls','native_terminal_exit','actual_failed_save_error','fresh_process_reload_equal']}),flush=True)

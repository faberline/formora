#!/usr/bin/env python3
"""Run unseen create/append inputs with every source repository read denied."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    calls=[]
    with tempfile.TemporaryDirectory(prefix='formora-independent-context-') as directory:
        runtime=Path(directory);binary=runtime/'formora';shutil.copyfile(args.binary.resolve(),binary);binary.chmod(0o755)
        policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))'
        prefix=['/usr/bin/sandbox-exec','-p',policy]
        control=subprocess.run([*prefix,'/bin/cat',str(root/'Cargo.toml')],cwd=runtime,capture_output=True,text=True)
        assert control.returncode!=0 and not control.stdout and ('Operation not permitted' in control.stderr or 'Permission denied' in control.stderr)
        def run(*arguments,request=None):
            result=subprocess.run([*prefix,str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),cwd=runtime,capture_output=True,text=True,check=True)
            calls.append({'arguments':list(map(str,arguments)),'request':request,'stdout':result.stdout,'exit_code':result.returncode})
            return json.loads(result.stdout)
        scene=runtime/'scene.json';run('scene','init','--scene',scene)
        setup={'expected_revision':0,'commands':[
            {'operation':'set_authoring_context','context':{'cursor_location':[1.3,-2.4,0.7],'cursor_rotation':[0.31,-0.17,0.83],'view_rotation':[0.41,-0.37,0.19]}},
            {'operation':'create_mesh_object','creation':{'id':'unseen','asset':'unseen-mesh','name':'Unseen view cube','primitive':{'kind':'cube','size':1.375},'placement':{'align':'view'}}}]}
        process=subprocess.Popen([*prefix,str(binary),'scene','serve','--scene',str(scene)],cwd=runtime,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        sequence=0
        def call(name,arguments):
            nonlocal sequence
            sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':arguments})+'\n');process.stdin.flush()
            response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok'],response
            calls.append({'name':name,'arguments':arguments,'response':response})
            return response['result']
        created=call('scene_apply',setup)
        before=call('scene_inspect',{})['scene'];receipt=created['creation'][0]
        assert len(receipt['created']['vertices'])==8 and len(receipt['created']['edges'])==12 and len(receipt['created']['faces'])==6
        request={'expected_revision':1,'commands':[{'operation':'append_mesh_primitive','creation':{'entity':'unseen','prefix':'new','primitive':{'kind':'cone','radius1':0.915,'radius2':0.275,'depth':2.175,'vertices':37},'placement':{'location':[-0.875,0.625,1.125],'rotation':[0.23,-0.51,0.37]}}}]}
        appended=call('scene_apply',request);after=call('scene_inspect',{})['scene'];new=appended['creation'][0]['created']
        old_mesh=before['mesh_assets']['unseen-mesh'];new_mesh=after['mesh_assets']['unseen-mesh']
        assert after['entities']==before['entities'];assert len(new_mesh['vertices'])==82 and len(new_mesh['edges'])==123 and len(new_mesh['polygons'])==45
        assert set(new['vertices'])==set(new_mesh['vertices'])-set(old_mesh['vertices'])
        for id,point in old_mesh['vertices'].items():assert new_mesh['vertices'][id]==point
        assert new_mesh['recipe']['edited'] and new_mesh['editing']['selected']==new
        call('scene_undo',{'expected_revision':2})
        restored=call('scene_inspect',{})['scene'];assert {k:v for k,v in restored.items() if k!='revision'}=={k:v for k,v in before.items() if k!='revision'}
        call('scene_apply',{**request,'expected_revision':3})
        process.stdin.close();process.wait(timeout=10);error=process.stderr.read();process.stdout.close();process.stderr.close();assert process.returncode==0,error
        reloaded=run('scene','inspect','--scene',scene)['scene']
        assert {k:v for k,v in reloaded.items() if k!='revision'}=={k:v for k,v in after.items() if k!='revision'}
        for name,value in [('before',before),('after',after),('reloaded',reloaded),('create-receipt',created),('append-receipt',appended)]:
            (output/(name+'.json')).write_text(json.dumps(value,allow_nan=False)+'\n')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        report={'passed':True,'source_repository_reads':'denied by macOS sandbox','policy':policy,'denial_control_exit_code':control.returncode,'denial_control_stderr':control.stderr,
                'binary_sha256':sha(binary),'tool_sha256':sha(Path(__file__)),'requests':[setup,request],'commands':calls,'undo_checked':True,'fresh_reload_equal':True,
                'artifacts':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'full_feature_acceptance':'unrun'}
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'unseen_create_and_append':True}))


if __name__=='__main__':main()

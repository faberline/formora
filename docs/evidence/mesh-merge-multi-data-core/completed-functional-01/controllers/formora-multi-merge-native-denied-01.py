from pathlib import Path
import hashlib,json,os,re,subprocess
root=Path('/private/tmp/formora-mesh-merge-multi-data-core');out=Path('/private/tmp/formora-multi-merge-native-controls-01');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
denied=[root,Path('/Users/chrischeng/faberlines/formora'),Path('/private/tmp/formora-mesh-merge-multi-data'),Path('/private/tmp/formora-mesh-merge-sparse'),Path('/private/tmp/formora-multi-merge-api-full-01'),Path('/private/tmp/formora-multi-merge-api-pilot-03'),Path('/private/tmp/formora-object-state-runtime-01')]
policy='(version 1)(allow default)(deny file-read* '+''.join('(subpath '+json.dumps(str(p))+')' for p in denied)+')';prefix=['/usr/bin/sandbox-exec','-p',policy];controls=[];records=[]
inputs=[root/'tests/mesh_merge_multi_data.rs',root/'tests/mesh_merge_history.rs',root/'docs/evidence/mesh-merge-core/continuation/proposed-unseen-core.rs',root/'docs/evidence/mesh-merge-core/continuation/proposed-mesh-merge-uv-preservation.rs',Path('/private/tmp/formora-multi-merge-target-actual185/release/libformora.rlib')];hashes={str(p):sha(p) for p in inputs};assert hashes[str(inputs[-1])]=='9b6e850f4cbe2e348d9aea69c48ed0f6e5ba8b0a94f6325eed67f2844e568d40'
for p in [root/'Cargo.toml',denied[1]/'Cargo.toml',denied[2]/'baseline/fixtures/mesh-merge-multi-data.json',denied[4]/'cli/multi_merge_00000/record.json.gz']:
 command=[*prefix,'/bin/cat',str(p)];result=subprocess.run(command,capture_output=True,text=True,cwd=out);controls.append({'command':command,'terminal_exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr});assert result.returncode==1 and not result.stdout and 'not permitted' in result.stderr
for name,count in [('multi',8),('single',9)]:
 binary=out/(name+'-controls');command=[*prefix,str(binary),'--test-threads=1','--nocapture'];environment=os.environ.copy();environment['TMPDIR']=str(out/'temp')
 with (out/(name+'-denied.stdout')).open('x') as so,(out/(name+'-denied.stderr')).open('x') as se:
  process=subprocess.Popen(command,cwd=out,stdout=so,stderr=se,env=environment);code=process.wait()
 text=(out/(name+'-denied.stdout')).read_text();passed=code==0 and f'test result: ok. {count} passed; 0 failed; 0 ignored;' in text
 records.append({'name':name,'command':command,'process_id':process.pid,'terminal_exit_code':code,'required_tests':count,'passed':passed,'binary_sha256':sha(binary),'stdout_sha256':sha(out/(name+'-denied.stdout')),'stderr_sha256':sha(out/(name+'-denied.stderr'))})
report={'passed':all(r['passed'] for r in records),'source_and_prior_answers_read_denied':True,'policy':policy,'denial_controls':controls,'records':records,'inputs_unchanged':hashes=={p:sha(p) for p in hashes},'input_hashes':hashes,'product_acceptance':'unrun','independent_acceptance':'unrun'}
with (out/'denied-report.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'passed':report['passed'],'frozen_controls':17,'repository_and_prior_answer_reads':'denied'}));raise SystemExit(0 if report['passed'] and report['inputs_unchanged'] else 1)

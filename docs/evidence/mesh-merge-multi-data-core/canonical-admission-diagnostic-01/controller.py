from pathlib import Path
from datetime import datetime,timezone
import gzip,hashlib,json,subprocess,traceback,sys
sys.path.insert(0,str(Path.cwd()/'tools'))
from multi_mesh_merge_product_inputs import scene
from compare_snap_menu_reference import tree
root=Path.cwd();out=Path('/private/tmp/formora-multi-data-canonical-admission-01');out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
helper=root/'docs/evidence/mesh-merge-multi-data-core/canonical-scene-validator.rs';constructor=root/'tools/multi_mesh_merge_product_inputs.py';fixture=root/'baseline/fixtures/mesh-merge-multi-data.json';lib=Path('/private/tmp/formora-merge-regen-target-actual185/release/libformora.rlib');serde=Path('/private/tmp/formora-merge-regen-target-actual185/release/deps/libserde_json-7ab9b385339e8dcd.rlib');binary=out/'canonical-scene-validator';inputs={str(p):sha(p) for p in [helper,constructor,fixture,lib,serde]};suite=json.loads(fixture.read_text());report={'scope':'before_code_native_Rust_scene_admission_and_world_queries','started_utc':datetime.now(timezone.utc).isoformat(),'inputs':inputs,'required_cases':13440,'passed_cases':0,'product_operation_acceptance':'unrun','cli_mcp_feature_acceptance':'unrun','product_implementation_changed':False,'complete':False}
command=['/private/tmp/formora-rustup-cache/toolchains/1.85.0-aarch64-apple-darwin/bin/rustc','--edition','2024','-C','opt-level=3',str(helper),'--extern','formora='+str(lib),'--extern','serde_json='+str(serde),'-L','dependency='+str(serde.parent),'-o',str(binary)]
with (out/'compile.stdout').open('x') as so,(out/'compile.stderr').open('x') as se:code=subprocess.call(command,stdout=so,stderr=se)
report.update(compile_command=command,compile_exit=code)
process=None
try:
 assert code==0,('compile',code)
 with (out/'process.stderr').open('xb') as stderr,(out/'requests.jsonl.gz').open('xb') as requests_file,(out/'responses.jsonl.gz').open('xb') as responses_file:
  with gzip.GzipFile(filename='',fileobj=requests_file,mode='wb',mtime=0,compresslevel=6) as requests,gzip.GzipFile(filename='',fileobj=responses_file,mode='wb',mtime=0,compresslevel=6) as responses:
   process=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr)
   report.update(process_id=process.pid,binary_sha256=sha(binary))
   for i,run in enumerate(suite['runs']):
    # Setup is built and sent before any native expected record is opened.
    payload={'id':run['id'],'scene':scene(suite,run)};raw=(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n').encode();requests.write(raw);process.stdin.write(raw);process.stdin.flush();raw_response=process.stdout.readline();assert raw_response,'missing real native response';responses.write(raw_response);value=json.loads(raw_response);assert value['id']==run['id'] and value['accepted'] is True,value
    reference_path=root/'docs/evidence/mesh-merge-multi-data-baseline/native-01'/(run['id']+'.json.gz');reference=json.loads(gzip.decompress(reference_path.read_bytes()))['before'];assert set(value['worlds'])==set(reference['objects'])
    for name,world in value['worlds'].items():
     expected=reference['objects'][name];tree(expected['matrix_world'],world['world_matrix'],name+'/native world')
     frames=world['object_frames']
     for key in ['matrix_basis','matrix_local','matrix_parent_inverse','lock_location','lock_rotation','lock_scale']:tree(expected[key],frames[key],name+'/native '+key)
     assert frames['selected']==expected['selected'] and frames['edit_mode']==(expected['mode']=='EDIT')
     if name in reference['meshes']:tree(reference['meshes'][name]['world_vertices'],world['world_vertices'],name+'/native world vertices')
    report['passed_cases']+=1
    if (i+1)%250==0:print(json.dumps({'admitted_and_world_bound':i+1,'required':13440}),flush=True)
   process.stdin.close();report['terminal_exit_code']=process.wait(timeout=30);assert report['terminal_exit_code']==0
 assert report['passed_cases']==13440 and inputs=={p:sha(p) for p in inputs},'coverage/input drift';report['complete']=True
except BaseException as error:
 report.update(error=str(error),traceback=traceback.format_exc())
 if process is not None:
  try:process.stdin.close()
  except Exception:pass
  report['terminal_exit_code']=process.wait(timeout=30)
finally:
 report['ended_utc']=datetime.now(timezone.utc).isoformat();report['files']={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.iterdir() if p.is_file() and p.name!='report.json'}
 with (out/'report.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'complete':report['complete'],'passed_cases':report['passed_cases'],'error':report.get('error'),'product_operation_acceptance':'unrun'}),flush=True)
raise SystemExit(0 if report['complete'] else 1)

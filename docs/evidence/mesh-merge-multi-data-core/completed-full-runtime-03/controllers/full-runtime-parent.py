from pathlib import Path
import hashlib,json,subprocess,sys,time
root=Path.cwd();out=Path('/private/tmp/formora-multi-merge-full-process-01');out.mkdir(exist_ok=False)
command=[sys.executable,str(root/'tools/multi_mesh_merge_runtime.py'),'--binary','/private/tmp/formora-multi-merge-target-actual185/debug/formora','--output','/private/tmp/formora-multi-merge-api-full-01']
started=time.monotonic()
with (out/'stdout').open('x') as stdout,(out/'stderr').open('x') as stderr:
 process=subprocess.Popen(command,stdout=stdout,stderr=stderr);(out/'started.json').write_text(json.dumps({'process_id':process.pid,'command':command,'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()},indent=2)+'\n');print(json.dumps({'process_id':process.pid,'started':True}),flush=True);code=process.wait()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'terminal.json').write_text(json.dumps({'process_id':process.pid,'terminal_exit_code':code,'elapsed_seconds':time.monotonic()-started,'stdout_sha256':sha(out/'stdout'),'stderr_sha256':sha(out/'stderr')},indent=2)+'\n');print(json.dumps({'process_id':process.pid,'terminal_exit_code':code}),flush=True);raise SystemExit(code)

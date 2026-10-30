"""Repeat four unchanged native Metal proofs on the current preview executable."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=Path('/private/tmp/formora-merge-retained-gpu-01');OUT.mkdir(exist_ok=False)
BINARY=Path('/private/tmp/formora-merge-allfeatures-actual185/debug/formora');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(BINARY)
assert binary_sha=='5fe37fe3ce8c556e4cd5c01fe27f086fd422e5de8ad3a765de4c428b0ee15f7f'
rows=[]
for name,script,extra,file in [('delta',ROOT/'docs/evidence/snap-delta-core/gpu-driver.py',[str(BINARY),str(OUT/'delta')],'manifest.json'),('raw',ROOT/'docs/evidence/snap-rotation-core/gpu-driver.py',[str(BINARY),str(OUT/'raw')],'manifest.json'),('rng',HERE/'retained-gpu-rng-01.py',[],'manifest.json'),('mirror',HERE/'retained-gpu-mirror-01.py',[],'manifest.json')]:
 command=[sys.executable,str(script),*extra]
 with (OUT/(name+'.stdout')).open('xb') as stdout,(OUT/(name+'.stderr')).open('xb') as stderr:
  child=subprocess.Popen(command,cwd=ROOT,env=os.environ,stdout=stdout,stderr=stderr);code=child.wait()
 path=OUT/name/file;report=json.loads(path.read_bytes()) if path.exists() else None
 row={'name':name,'command':command,'process_id':child.pid,'terminal_exit_code':code,'passed':code==0 and report is not None and report['passed'],'driver_sha256':sha(script),'report_sha256':sha(path) if path.exists() else None}
 rows.append(row);(OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
report={'passed':all(r['passed'] for r in rows) and sha(BINARY)==binary_sha,'records':rows,'binary_sha256':binary_sha,'implementation_commit':'224a4360276511f48d023a2f6f39190010dae731','product_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)

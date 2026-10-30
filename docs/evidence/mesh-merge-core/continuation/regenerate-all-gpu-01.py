"""Run new merge and four retained native Metal proofs on the repaired build."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];OUT=Path('/private/tmp/formora-merge-regen-all-gpu-01');OUT.mkdir(exist_ok=False)
rows=[];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,script,path in [('merge','regenerate-gpu-proof-01.py','/private/tmp/formora-merge-regen-gpu-01/report.json'),('retained4','regenerate-retained-gpu-01.py','/private/tmp/formora-merge-regen-retained-gpu-01/report.json')]:
 command=[sys.executable,str(HERE/script)]
 with (OUT/(name+'.stdout')).open('xb') as stdout,(OUT/(name+'.stderr')).open('xb') as stderr:
  p=subprocess.Popen(command,cwd=ROOT,env=os.environ,stdout=stdout,stderr=stderr);code=p.wait()
 reportpath=Path(path);report=json.loads(reportpath.read_bytes()) if reportpath.exists() else None
 row={'name':name,'command':command,'process_id':p.pid,'terminal_exit_code':code,'passed':code==0 and report is not None and report['passed'],'report_sha256':sha(reportpath) if reportpath.exists() else None}
 rows.append(row);(OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
result={'passed':all(r['passed'] for r in rows),'records':rows,'implementation_commit':'5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d','product_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(0 if result['passed'] else 1)

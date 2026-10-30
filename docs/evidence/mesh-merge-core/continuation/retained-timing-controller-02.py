"""Run all 177 retained timing samples once with their unchanged native drivers."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=Path('/private/tmp/formora-merge-retained-timing-controller-02');OUT.mkdir(exist_ok=False)
compile_report=json.loads(Path('/private/tmp/formora-merge-retained-compile-01/report.json').read_text());assert compile_report['passed']
rows=[]
for name,count in [('90',90),('rotation',24),('delta',24)]:
 command=[sys.executable,str(HERE/f'retained-run-{name}-02.py')]
 with (OUT/(name+'.stdout')).open('xb') as stdout,(OUT/(name+'.stderr')).open('xb') as stderr:
  child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr);code=child.wait()
 path=Path(f'/private/tmp/formora-merge-retained-{name}-02/controller-report.json')
 report=json.loads(path.read_text()) if path.exists() else None
 row={'name':name,'expected_samples':count,'command':command,'process_id':child.pid,'terminal_exit_code':code,'passed':code==0 and report is not None and report['passed'],'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None}
 rows.append(row);print(json.dumps(row),flush=True)
 (OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
result={'passed':all(r['passed'] for r in rows),'samples':138,'records':rows,'implementation_commit':'224a4360276511f48d023a2f6f39190010dae731','source_comparison':'unrun','product_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(0 if result['passed'] else 1)

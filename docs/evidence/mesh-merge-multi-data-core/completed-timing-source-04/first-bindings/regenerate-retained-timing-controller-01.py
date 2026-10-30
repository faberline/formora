"""Run all 177 retained timing samples once with their unchanged native drivers."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core');HERE=Path(__file__).resolve().parent
OUT=Path('/private/tmp/formora-multi-merge-retained-timing-controller-01');OUT.mkdir(exist_ok=False)
compile_report=json.loads(Path('/private/tmp/formora-multi-merge-retained-compile-01/report.json').read_text());assert compile_report['passed']
rows=[]
for name,count in [('90',90),('39',39),('rotation',24),('delta',24)]:
 command=[sys.executable,str(HERE/f'regenerate-retained-run-{name}-01.py')]
 with (OUT/(name+'.stdout')).open('xb') as stdout,(OUT/(name+'.stderr')).open('xb') as stderr:
  child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr);code=child.wait()
 path=Path(f'/private/tmp/formora-multi-merge-retained-{name}-01/controller-report.json')
 report=json.loads(path.read_text()) if path.exists() else None
 row={'name':name,'expected_samples':count,'command':command,'process_id':child.pid,'terminal_exit_code':code,'passed':code==0 and report is not None and report['passed'],'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None}
 rows.append(row);print(json.dumps(row),flush=True)
 (OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
result={'passed':all(r['passed'] for r in rows),'samples':177,'records':rows,'implementation_commit':'bd13f3d424f2649b4b25c16305c4e5b0eb7f8542','source_comparison':'unrun','product_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(0 if result['passed'] else 1)

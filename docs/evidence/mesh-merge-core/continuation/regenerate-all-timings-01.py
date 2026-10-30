"""Run all 207 fixed timings once on the repaired library; keep every result."""
from pathlib import Path
import hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
OUT=Path('/private/tmp/formora-merge-regen-all-timings-01');OUT.mkdir(exist_ok=False)
compile_report=json.loads(Path('/private/tmp/formora-merge-regen-retained-compile-01/report.json').read_bytes());assert compile_report['passed'] and compile_report['library_sha256']=='a06c8aa897ce51992ca08779627eb4041ef0db51d4ccca9dab08ce3fdbc1a0f6'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(ROOT/'docs/evidence/mesh-merge-core/performance/capture-driver.rs')=='247a0988c964d1e6b5e289dab3c8148ca8db72feea20a4240bc8f7a238a9ac91'
rows=[]
for name,count,script,reportpath in [('new30',30,'regenerate-run-performance-01.py','/private/tmp/formora-merge-regen-performance-01/report.json'),('retained177',177,'regenerate-retained-timing-controller-01.py','/private/tmp/formora-merge-regen-retained-timing-controller-01/report.json')]:
 command=[sys.executable,str(HERE/script)]
 with (OUT/(name+'.stdout')).open('xb') as stdout,(OUT/(name+'.stderr')).open('xb') as stderr:
  process=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr);code=process.wait()
 path=Path(reportpath);report=json.loads(path.read_bytes()) if path.exists() else None
 row={'name':name,'samples':count,'command':command,'process_id':process.pid,'terminal_exit_code':code,'passed':code==0 and report is not None and report['passed'],'report_sha256':sha(path) if path.exists() else None}
 rows.append(row);(OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
result={'passed':all(r['passed'] for r in rows),'samples':207,'records':rows,'implementation_commit':'5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d','physical_source_comparisons':'unrun on this build','product_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(0 if result['passed'] else 1)

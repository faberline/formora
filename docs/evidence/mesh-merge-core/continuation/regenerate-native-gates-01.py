"""Repeat real source-denied, save-failure and retained lifecycle proofs."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
OUT=Path('/private/tmp/formora-merge-regen-native-gates-01');OUT.mkdir(exist_ok=False)
checks=[('unseen9','regenerate-run-unseen-denial-after-01.py','/private/tmp/formora-merge-regen-unseen-after-01/report.json','all_functional_controls_passed'),('failed-save19','regenerate-failed-save-proof-01.py','/private/tmp/formora-merge-regen-failed-save-01/report.json','passed'),('retained12','regenerate-retained-small-gates-01.py','/private/tmp/formora-merge-regen-retained-small-gates-01/report.json','passed'),('rng48','regenerate-retained-rng-one-shot-01.py','/private/tmp/formora-merge-regen-rng-one-shot-01/report.json','passed'),('euler6','regenerate-retained-source-oracle-01.py','/private/tmp/formora-merge-regen-source-oracle-01/report.json','passed')]
rows=[];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,script,report,key in checks:
 command=[sys.executable,str(HERE/script)]
 with (OUT/(name+'.stdout')).open('xb') as stdout,(OUT/(name+'.stderr')).open('xb') as stderr:
  p=subprocess.Popen(command,cwd=ROOT,env=os.environ,stdout=stdout,stderr=stderr);code=p.wait()
 path=Path(report);data=json.loads(path.read_bytes()) if path.exists() else None
 row={'name':name,'command':command,'process_id':p.pid,'terminal_exit_code':code,'passed':code==0 and data is not None and data[key] is True,'report_sha256':sha(path) if path.exists() else None}
 rows.append(row);(OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
result={'passed':all(r['passed'] for r in rows),'records':rows,'implementation_commit':'5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d','product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(0 if result['passed'] else 1)

"""Repeat the seven source-denied suites and five local lifecycle suites."""
from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=Path('/private/tmp/formora-merge-retained-small-gates-01');OUT.mkdir(exist_ok=False)
BINARY=Path('/private/tmp/formora-merge-target-actual185/debug/formora');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
binary_sha=sha(BINARY);assert binary_sha=='5bf40a3c99843bd7b9395d3d712f605756284cd44aa07c2925661b7c7bd5c3c2'
records=[]
for row in json.loads((HERE/'retained-small-gates-config-01.json').read_text()):
 name=row['kind']+'-'+row['name'];command=row['command']
 with (OUT/(name+'.stdout')).open('xb') as stdout,(OUT/(name+'.stderr')).open('xb') as stderr:
  child=subprocess.Popen(command,cwd=ROOT,env=os.environ,stdout=stdout,stderr=stderr);code=child.wait()
 path=Path(row['report']);report=json.loads(path.read_bytes()) if path.exists() else None
 record={**row,'process_id':child.pid,'terminal_exit_code':code,'passed':code==0 and report is not None and report['passed'],'report_sha256':sha(path) if path.exists() else None,'driver_sha256':sha(Path(command[1]))}
 records.append(record);(OUT/'progress.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['kind','name','terminal_exit_code','passed']}),flush=True)
unchanged=sha(BINARY)==binary_sha
report={'passed':unchanged and all(r['passed'] for r in records),'suites':len(records),'records':records,'binary_sha256':binary_sha,'binary_unchanged':unchanged,'implementation_commit':'224a4360276511f48d023a2f6f39190010dae731','product_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)

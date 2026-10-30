"""Audit one completed retained corpus after its native terminal record exists."""
from pathlib import Path
import hashlib,importlib.util,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('retained_audit',HERE/'regenerate-retained-audit-module-01.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
kind=sys.argv[1];out=Path(sys.argv[2]);assert not out.exists();out.parent.mkdir(exist_ok=True,parents=True)
name,count={'full':('delta',3584),'rotation':('raw-rotation',4992),'scene':('scene-snap',1100),'single':('single-snap',2244),'transform':('mesh-transform',2406)}[kind]
folder=Path('/private/tmp/formora-merge-regen-retained-api-01')
progress=json.loads((folder/'progress.json').read_bytes());row=next(r for r in progress if r['name']==name)
assert row['passed'] and row['terminal_exit_code']==0 and row['actual_checks']==row['expected_checks']==count
assert row['report_sha256']==audit.sha(folder/name/'report.json')
for rootname in ['src','tests','tools','docs/contracts']:
 for path in sorted((ROOT/rootname).rglob('*')):
  if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
  assert subprocess.check_output(['git','show',audit.IMPLEMENTATION+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)==path.read_bytes(),path
binary=Path('/private/tmp/formora-merge-regen-target-actual185/debug/formora');assert audit.sha(binary)==audit.BINARY
result=audit.audit(kind,count)
if kind in ['full','rotation']:assert result['outcomes']=={'defined_numeric_source_comparison':count}
if kind=='scene':assert result['outcomes']=={'defined_numeric_source_comparison':1094,'explicit_cancellation':4,'explicit_atomic_rejection':2}
if kind=='single':assert result['outcomes']=={'defined_numeric_source_comparison':2072,'explicit_cancellation':136,'explicit_atomic_rejection':36}
assert audit.sha(binary)==audit.BINARY
report={'passed':True,'kind':kind,**result,'binary_sha256':audit.BINARY,'implementation_commit':audit.IMPLEMENTATION,'actual_terminal_record':row,'driver_sha256':audit.sha(Path(__file__)),'audit_module_sha256':audit.sha(HERE/'regenerate-retained-audit-module-01.py'),'product_acceptance':'unrun','independent_acceptance':'unrun'}
out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)

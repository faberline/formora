"""Run only pending timings with real host probes, then compare all 207 sources."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback

ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')
OUT=Path('/private/tmp/formora-multi-merge-timing-recovery-02');OUT.mkdir(exist_ok=False)
DRIVERS=Path('/private/tmp/formora-multi-merge-timing-recovery-drivers-02')
BINARY=Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
first=load('/private/tmp/formora-multi-merge-post-full-01/report.json')
assert not first['passed'] and first['input_hashes_unchanged']
assert all(r['passed'] and r['terminal_exit_code']==0 for r in first['records'][:2])
retained39=load('/private/tmp/formora-multi-merge-retained-39-01/controller-report.json')
assert retained39['passed'] and retained39['verification_inputs_unchanged']
assert sum(r['expected_samples'] for r in retained39['checks'])==39
assert all(r['terminal_exit_code']==0 and r['passed'] for r in retained39['checks'])
assert load('/private/tmp/formora-multi-merge-api-full-audit-01.json')['raw_calls_bound']==860160
assert load('/private/tmp/formora-multi-merge-api-full-controls-01.json')['negative_controls_passed']
hashes={str(ROOT/name):digest for name,digest in load('/private/tmp/formora-multi-merge-api-full-01/report.json')['input_hashes'].items()}
hashes[str(BINARY)]=sha(BINARY)
for folder in [DRIVERS,Path('/private/tmp/formora-multi-merge-source-runners-01')]:
    for path in folder.iterdir():
        if path.is_file():hashes[str(path)]=sha(path)
rows=[]
env=dict(os.environ,PYTHONPYCACHEPREFIX='/private/tmp/formora-multi-data-pycache',PYTHONPATH=str(ROOT/'tools')+':/private/tmp/formora-mcp-sdk-2')
(OUT/'started.json').write_text(json.dumps({'pid':os.getpid(),'frozen_input_hashes':hashes,
    'prior_diagnostic_preserved':True,'retained_39_not_repeated':True},indent=2)+'\n')
def run(name,command,path,count,kind='samples'):
    assert all(sha(p)==d for p,d in hashes.items())
    started=time.monotonic()
    with (OUT/(name+'.stdout')).open('x') as stdout,(OUT/(name+'.stderr')).open('x') as stderr:
        child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
        (OUT/(name+'-started.json')).write_text(json.dumps({'pid':child.pid,'command':command},indent=2)+'\n')
        code=child.wait()
    report=load(path) if path.exists() else None
    row={'name':name,'process_id':child.pid,'command':command,'terminal_exit_code':code,
         'elapsed_seconds':time.monotonic()-started,'report_path':str(path),
         'report_sha256':sha(path) if path.exists() else None,'passed':False}
    rows.append(row)
    (OUT/(name+'-terminal.json')).write_text(json.dumps(row,indent=2)+'\n')
    assert code==0 and report is not None and report['passed'] and report[kind]==count,row
    assert all(sha(p)==d for p,d in hashes.items())
    row['passed']=True
    (OUT/(name+'-terminal.json')).write_text(json.dumps(row,indent=2)+'\n')
    (OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps({k:row[k] for k in ['name','process_id','terminal_exit_code','passed']}),flush=True)
result={'passed':False,'records':rows,'prior_attempt':'preserved sandbox host-probe failures; not a timing pass',
        'product_acceptance':'unrun','independent_acceptance':'unrun'}
try:
    for name,count in [('90',90),('rotation',24),('delta',24)]:
        run('retained-'+name,[sys.executable,str(DRIVERS/f'regenerate-retained-run-{name}-01.py')],
            Path(f'/private/tmp/formora-multi-merge-retained-{name}-02/controller-report.json'),count)
    run('single-merge-30',[sys.executable,'/private/tmp/formora-multi-merge-timing-runners-01/regenerate-run-performance-01.py'],
        Path('/private/tmp/formora-multi-merge-performance-01/report.json'),30,'actual_samples')
    run('physical-source-177',[sys.executable,str(DRIVERS/'regenerate-retained-compare-all-sources-01.py'),
        str(BINARY),'/private/tmp/formora-multi-merge-retained-source-02'],
        Path('/private/tmp/formora-multi-merge-retained-source-02/report.json'),177)
    run('physical-source-30',[sys.executable,'/private/tmp/formora-multi-merge-source-runners-01/regenerate-compare-performance-01.py'],
        Path('/private/tmp/formora-multi-merge-performance-source-01/report.json'),30)
    result.update(passed=True,retained_timing_samples=207,retained_physical_source_samples=207,
                  new_timing_samples=168,prior_passed_samples_reused=39)
except BaseException as error:result.update(error=str(error),traceback=traceback.format_exc())
finally:
    result['frozen_inputs_unchanged']=all(sha(p)==d for p,d in hashes.items())
    (OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'completed_stages':len(rows),'error':result.get('error')}),flush=True)
raise SystemExit(0 if result['passed'] else 1)

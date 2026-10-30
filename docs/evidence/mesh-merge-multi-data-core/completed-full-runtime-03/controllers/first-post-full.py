"""Wait for the actual full run, audit it, then run the frozen retained timings."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
OUT = Path('/private/tmp/formora-multi-merge-post-full-01')
CAPTURE = Path('/private/tmp/formora-multi-merge-api-full-01')
TERMINAL = Path('/private/tmp/formora-multi-merge-full-process-01/terminal.json')
BINARY = Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
TIMING = Path('/private/tmp/formora-multi-merge-timing-runners-01')
SOURCE = Path('/private/tmp/formora-multi-merge-source-runners-01')
OUT.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
load = lambda p: json.loads(Path(p).read_text())
rows = []
env = dict(os.environ, PYTHONPYCACHEPREFIX='/private/tmp/formora-multi-data-pycache',
           PYTHONPATH=str(ROOT/'tools')+':/private/tmp/formora-mcp-sdk-2')
inputs = [p for folder in ['src','tests','tools','docs/contracts'] for p in (ROOT/folder).rglob('*')
          if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
inputs += [ROOT/'Cargo.toml',ROOT/'Cargo.lock',BINARY,
           ROOT/'docs/evidence/mesh-merge-core/continuation/pilot-native.py',
           ROOT/'docs/evidence/mesh-merge-core/continuation/runtime-cli-mcp.py']
bindings = {str(p):sha(p) for p in inputs}
for folder in [TIMING,SOURCE]:
    for p in folder.iterdir():
        if p.is_file():
            bindings[str(p)] = sha(p)
(OUT/'started.json').write_text(json.dumps({'pid':os.getpid(),'head':subprocess.check_output(
    ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'input_hashes':bindings,
    'waiting_for_actual_full_terminal':str(TERMINAL),'no_timing_under_live_functional_load':True},indent=2)+'\n')

def unchanged():
    assert all(sha(p)==digest for p,digest in bindings.items()), 'frozen input or executable changed'

def run(name, command, report_path, validator):
    unchanged()
    started = time.monotonic()
    with (OUT/(name+'.stdout')).open('x') as stdout,(OUT/(name+'.stderr')).open('x') as stderr:
        child = subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
        (OUT/(name+'-started.json')).write_text(json.dumps({'pid':child.pid,'command':command},indent=2)+'\n')
        code = child.wait()
    row = {'name':name,'process_id':child.pid,'command':command,'terminal_exit_code':code,
           'elapsed_seconds':time.monotonic()-started,'stdout_sha256':sha(OUT/(name+'.stdout')),
           'stderr_sha256':sha(OUT/(name+'.stderr')),'report_path':str(report_path),
           'report_sha256':sha(report_path) if report_path.exists() else None,'passed':False}
    rows.append(row)
    (OUT/(name+'-terminal.json')).write_text(json.dumps(row,indent=2)+'\n')
    assert code==0, row
    report=load(report_path)
    validator(report)
    unchanged()
    row['passed']=True
    (OUT/(name+'-terminal.json')).write_text(json.dumps(row,indent=2)+'\n')
    (OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps({k:row[k] for k in ['name','process_id','terminal_exit_code','passed']}),flush=True)

def require(condition):
    assert condition

result={'passed':False,'records':rows,'product_acceptance':'unrun','independent_acceptance':'unrun'}
try:
    print(json.dumps({'waiting_for_full_terminal':True,'timing_samples_started':0}),flush=True)
    while not TERMINAL.exists():
        time.sleep(5)
    terminal=load(TERMINAL)
    assert terminal['process_id']==5100 and terminal['terminal_exit_code']==0
    full=load(CAPTURE/'report.json')
    assert full['complete'] and full['executed_records']==full['required_records']==26880 and full['failed_records']==0
    assert full['outcomes']=={'finished_source_comparison':18176,'explicit_enum_rejection':8704}
    assert full['binary_sha256']==sha(BINARY)
    result['full_terminal_sha256']=sha(TERMINAL)
    run('full-raw-audit',[sys.executable,str(ROOT/'tools/audit_multi_mesh_merge_runtime.py'),
        '--capture',str(CAPTURE),'--output','/private/tmp/formora-multi-merge-api-full-audit-01.json'],
        Path('/private/tmp/formora-multi-merge-api-full-audit-01.json'),
        lambda r:require(r['raw_evidence_passed'] and r['full_interface_matrix_passed'] and r['records']==26880
                         and r['raw_calls_bound']==860160 and r['source_cases_each']==13440))
    run('full-raw-controls',[sys.executable,str(ROOT/'tools/check_multi_mesh_merge_runtime_controls.py'),
        '--capture',str(CAPTURE),'--output','/private/tmp/formora-multi-merge-api-full-controls-01.json'],
        Path('/private/tmp/formora-multi-merge-api-full-controls-01.json'),
        lambda r:require(r['negative_controls_passed'] and r['controls']==30 and not r['forged_operations_executed']
                         and r['constructor_filesystem_reads']==0 and r['pure_constructor_cases']==13440))
    run('retained-timing-177',[sys.executable,str(TIMING/'regenerate-retained-timing-controller-01.py')],
        Path('/private/tmp/formora-multi-merge-retained-timing-controller-01/report.json'),
        lambda r:require(r['passed'] and r['samples']==177 and len(r['records'])==4))
    run('retained-timing-30',[sys.executable,str(TIMING/'regenerate-run-performance-01.py')],
        Path('/private/tmp/formora-multi-merge-performance-01/report.json'),
        lambda r:require(r['passed'] and r['actual_samples']==30 and r['terminal_exit_code']==0))
    run('retained-source-177',[sys.executable,str(SOURCE/'regenerate-retained-compare-all-sources-01.py'),
        str(BINARY),'/private/tmp/formora-multi-merge-retained-source-01'],
        Path('/private/tmp/formora-multi-merge-retained-source-01/report.json'),
        lambda r:require(r['passed'] and r['samples']==177 and len(r['records'])==5))
    run('retained-source-30',[sys.executable,str(SOURCE/'regenerate-compare-performance-01.py')],
        Path('/private/tmp/formora-multi-merge-performance-source-01/report.json'),
        lambda r:require(r['passed'] and r['samples']==30 and r['all_30_timing_and_physical_source_results_passed']))
    result.update(passed=True,full_raw_records=26880,full_raw_calls=860160,retained_timing_and_source_samples=207,
                  required_platform_ci='unpassed',dependency_integration='unrun')
except BaseException as error:
    result.update(error=str(error),traceback=traceback.format_exc())
finally:
    result['input_hashes_unchanged']=all(sha(p)==digest for p,digest in bindings.items())
    (OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'completed_stages':len(rows),'error':result.get('error')}),flush=True)
raise SystemExit(0 if result['passed'] else 1)

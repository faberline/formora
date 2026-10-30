"""Run every sealed merge timing sample and preserve its actual terminal result."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[4]
AUTHORED=ROOT/'docs/evidence/mesh-merge-core/performance'
OUTPUT=Path('/private/tmp/formora-merge-regen-performance-01')
DRIVER=Path('/private/tmp/formora-merge-regen-performance-driver-01')
LIBRARY=Path('/private/tmp/formora-merge-regen-target-actual185/release/libformora.rlib')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
OUTPUT.mkdir(exist_ok=False)
sealed=json.loads((AUTHORED/'before-product-code-final.json').read_bytes())
for relative,digest in sealed['files'].items():assert sha(ROOT/relative)==digest,relative
assert sealed['source_terminal_exit']==sealed['source_checker_terminal_exit']==0
assert sealed['source_forms_checked']==10 and sealed['source_process_id']==76326
bindings={'implementation':'5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d','head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'driver':str(DRIVER),'driver_sha256':sha(DRIVER),'library':str(LIBRARY),'library_sha256':sha(LIBRARY),
    'sealed_inputs':sealed['files'],'rustc':subprocess.check_output(['/private/tmp/formora-rustup-cache/toolchains/1.85.0-aarch64-apple-darwin/bin/rustc','-vV'],text=True),
    'all_samples_required':30,'discarded_warmup_samples':0,'maximum_core_ms':250,'maximum_pipeline_ms':2000}
host={}
for name,command in [('uptime',['uptime']),('model',['sysctl','-n','hw.model']),('memory',['sysctl','-n','hw.memsize']),('cpu_activity',['ps','-A','-o','pcpu='])]:
    try:
        process=subprocess.run(command,capture_output=True,text=True);host[name]={'command':command,'exit':process.returncode,'stdout':process.stdout,'stderr':process.stderr}
    except OSError as error:
        host[name]={'command':command,'exit':None,'unavailable':str(error)}
bindings['host_before']=host
command=[str(DRIVER),str(AUTHORED),str(OUTPUT/'samples')];started=time.monotonic_ns()
with (OUTPUT/'stdout').open('x') as stdout,(OUTPUT/'stderr').open('x') as stderr:
    process=subprocess.Popen(command,stdout=stdout,stderr=stderr,cwd=ROOT)
    (OUTPUT/'started.json').write_text(json.dumps({'command':command,'native_process_id':process.pid,'bindings':bindings,'started_ns':started},indent=2)+'\n')
    terminal=process.wait()
summary_path=OUTPUT/'samples/timing-summary.json'
summary=json.loads(summary_path.read_bytes()) if summary_path.exists() else None
unchanged=sha(DRIVER)==bindings['driver_sha256'] and sha(LIBRARY)==bindings['library_sha256'] and all(sha(ROOT/path)==digest for path,digest in sealed['files'].items())
complete=summary is not None and summary['samples']==len(summary['runs'])==30 and len(summary['groups'])==10
if complete:
    assert len({(row['form'],row['sample']) for row in summary['runs']})==30
    assert all(row['maximum_core_ms']==250 and row['maximum_pipeline_ms']==2000 and row['full_input_and_result_validation_inside_clocks'] for row in summary['runs'])
report={'passed':terminal==0 and unchanged and complete and summary['passed'], 'terminal_exit_code':terminal,'native_process_id':process.pid,
    'command':command,'start_ns':started,'end_ns':time.monotonic_ns(),'bindings':bindings,'inputs_unchanged':unchanged,'all_30_samples_complete':complete,
    'summary_sha256':sha(summary_path) if summary_path.exists() else None,'actual_samples':len(summary['runs']) if summary else 0,
    'all_source_comparisons':'unrun','retained_177_samples':'unrun','product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUTPUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:report[key] for key in ['passed','terminal_exit_code','native_process_id','actual_samples','inputs_unchanged']}),flush=True)
raise SystemExit(0 if report['passed'] else 1)

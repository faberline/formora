"""Run every frozen added release sample outside the watched checkout."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')
HERE=ROOT/'docs/evidence/snap-delta-core/performance'
RUN=Path('/private/tmp/formora-multi-merge-retained-delta-01')
DRIVER=Path('/private/tmp/formora-multi-merge-retained-delta-driver-01')
BINARY=Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
IMPLEMENTATION='bd13f3d424f2649b4b25c16305c4e5b0eb7f8542'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
RUN.mkdir(exist_ok=False);assert RUN.stat().st_dev==ROOT.stat().st_dev
source=[ROOT/'Cargo.toml',ROOT/'Cargo.lock',*[p for p in sorted((ROOT/'src').rglob('*')) if p.is_file()]]
for path in source:assert subprocess.check_output(['git','show',IMPLEMENTATION+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)==path.read_bytes()
paths=[*source,Path(__file__),HERE/'capture-driver.rs',HERE/'authored-grid.json',HERE/'authored-modes.json',
       DRIVER,BINARY,Path('/private/tmp/formora-multi-merge-target-actual185/release/libformora.rlib')]
hashes={str(p):sha(p) for p in paths}
hardware=subprocess.run(['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'],capture_output=True,text=True)
assert hardware.returncode==0 and hardware.stdout.strip()=='Apple M1 Max'
def host(name):
    value={'captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hardware':hardware.stdout.strip()}
    for key,command in [('top',['/usr/bin/top','-l','1','-n','0']),('swap',['/usr/sbin/sysctl','vm.swapusage'])]:
        p=subprocess.run(command,capture_output=True,text=True);value[key]={'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    with (RUN/name).open('x') as out:json.dump(value,out,indent=2);out.write('\n')
host('host-before.json');command=[str(DRIVER),str(HERE),str(RUN/'samples')]
with (RUN/'native.stdout').open('x') as stdout,(RUN/'native.stderr').open('x') as stderr:
    process=subprocess.Popen(command,stdout=stdout,stderr=stderr);exit_code=process.wait()
host('host-after.json');summary_path=RUN/'samples/timing-summary.json'
summary=json.loads(summary_path.read_text()) if summary_path.exists() else None
if summary is not None:
    assert summary['samples']==24 and len(summary['runs'])==24
    assert {(r['mode'],r['sample']) for r in summary['runs']}=={(m['object']['mode'],s) for m in json.loads((HERE/'authored-modes.json').read_text())['modes'] for s in [1,2,3]}
    for r in summary['runs']:assert r['maximum_core_ms']==250. and r['maximum_pipeline_ms']==2000.
unchanged=hashes=={str(p):sha(p) for p in paths}
passed=exit_code==0 and summary is not None and summary['passed'] and unchanged
report={'passed':passed,'terminal_exit_code':exit_code,'native_process_id':process.pid,'command':command,
        'implementation_commit':IMPLEMENTATION,'binary_sha256':sha(BINARY),'input_hashes':hashes,
        'verification_inputs_unchanged':unchanged,'same_filesystem_as_checkout':True,'samples':24 if summary else 0,
        'timing_summary_sha256':sha(summary_path) if summary_path.exists() else None,
        'method':'all fixed modes in one native process; original clocks, counts and limits; output outside checkout on same filesystem',
        'source_comparisons':'unrun','product_acceptance':'unrun'}
with (RUN/'controller-report.json').open('x') as out:json.dump(report,out,indent=2);out.write('\n')
print(json.dumps({'passed':passed,'samples':report['samples'],'terminal_exit_code':exit_code}),flush=True)
if not passed:raise SystemExit(1)

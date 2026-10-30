#!/usr/bin/env python3
"""Repeat all fixed samples in one process outside the watched Git checkout."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
HERE=ROOT/'docs/evidence/snap-delta-core/performance'
RUN=Path('/private/tmp/formora-merge-retained-90-01')
SAMPLES=RUN/'samples'
DRIVER=Path('/private/tmp/formora-merge-retained-90-driver-01')
IMPLEMENTATION='224a4360276511f48d023a2f6f39190010dae731'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
RUN.mkdir(exist_ok=False)
assert ROOT.stat().st_dev==RUN.stat().st_dev,'same filesystem required'
source_paths=[ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'src').rglob('*'))]
source_paths=[p for p in source_paths if p.is_file()]
for path in source_paths:
    assert subprocess.check_output(['git','show',IMPLEMENTATION+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)==path.read_bytes()
authored=ROOT/'docs/evidence/scene-snap-core/performance/samples'
native=json.loads((ROOT/'docs/evidence/scene-snap-core/performance/source-gzip/manifest.json').read_text())
for c in ['A','B','C']:
    names=[p for p in native['input_hashes'] if p.endswith(f'/input-{c}.json')]
    assert len(names)==1 and native['input_hashes'][names[0]]==sha(authored/f'input-{c}.json')
paths=[*source_paths,Path(__file__),HERE/'capture-driver-one-process.rs',DRIVER,
       Path('/private/tmp/formora-merge-target-actual185/release/libformora.rlib'),*[authored/f'input-{c}.json' for c in ['A','B','C']]]
hashes={str(p):sha(p) for p in paths}
def host(name):
    record={'captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    for key,cmd in [('top',['/usr/bin/top','-l','1','-n','0']),('swap',['/usr/sbin/sysctl','vm.swapusage'])]:
        p=subprocess.run(cmd,capture_output=True,text=True)
        record[key]={'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    (RUN/name).write_text(json.dumps(record,indent=2)+'\n')
host('host-before.json')
command=[str(DRIVER),str(authored),str(SAMPLES)]
with (RUN/'native.stdout').open('x') as out,(RUN/'native.stderr').open('x') as err:
    process=subprocess.run(command,stdout=out,stderr=err)
host('host-after.json')
summary_path=SAMPLES/'timing-summary.json'
summary=json.loads(summary_path.read_text()) if summary_path.exists() else None
groups=[]
if summary is not None:
    assert summary['samples']==90 and len(summary['groups'])==30
    for entry in summary['groups']:
        path=SAMPLES/entry['file'];report=json.loads(path.read_text())
        assert report['class']==entry['class'] and report['form']==entry['form'] and len(report['runs'])==3
        groups.append({'class':entry['class'],'form':entry['form'],'report':entry['file'],'report_sha256':sha(path),
                       'terminal_exit_code':process.returncode,'terminal_scope':'shared native process','passed':report['passed']})
    for c in ['A','B','C']:assert (SAMPLES/f'input-{c}.json').read_bytes()==(authored/f'input-{c}.json').read_bytes()
unchanged=hashes=={str(p):sha(p) for p in paths}
passed=process.returncode==0 and summary is not None and summary['passed'] and len(groups)==30 and all(g['passed'] for g in groups) and unchanged
result={'passed':passed,'samples':90 if summary is not None else 0,'groups':groups,'command':command,
        'terminal_exit_code':process.returncode,'native_process_id':None if summary is None else summary['process_id'],
        'input_hashes':hashes,'verification_inputs_unchanged':unchanged,'implementation_commit':IMPLEMENTATION,
        'same_filesystem_as_checkout':True,'timing_summary_sha256':sha(summary_path) if summary_path.exists() else None,
        'method':'all fixed groups in one native process; original clocks, counts and limits; output on same filesystem outside checkout',
        'source_comparison':'required separately for every output','product_acceptance':'unrun','milestone_acceptance':'unrun'}
(RUN/'controller-report.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':passed,'groups':len(groups),'samples':result['samples'],'terminal_exit_code':process.returncode}),flush=True)
if not passed:raise SystemExit(1)

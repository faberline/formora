#!/usr/bin/env python3
"""Run all frozen groups sequentially. Keep every raw sample and failed run."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
DRIVER=Path('/private/tmp/formora-scene-snap-performance-driver-09')
SAMPLES=HERE/'optimized-samples-09'
ORIGINAL=ROOT/'docs/evidence/mesh-snap-core/performance/fixed-samples/input.json'
FORMS=['selected-grid','selected-active','cursor-grid','cursor-selected','cursor-active','cursor-origin',
       'selected-cursor-false-false','selected-cursor-false-true','selected-cursor-true-false','selected-cursor-true-true']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=[ROOT/'Cargo.toml',ROOT/'Cargo.lock',HERE/'capture-driver.rs',Path(__file__),DRIVER,
       Path('/private/tmp/formora-target-actual185/release/libformora.rlib'),*[SAMPLES/f'input-{c}.json' for c in ['A','B','C']],
       *sorted((ROOT/'src').rglob('*.rs'))]
hashes={str(p):sha(p) for p in paths};groups=[]
IMPLEMENTATION='dcb484218708959ac28b4a1ac79d5ef8b4156a02'
for path in [ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'src').rglob('*.rs'))]:
    assert subprocess.check_output(['git','show',IMPLEMENTATION+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)==path.read_bytes()
assert not (HERE/'fixed-controller-report-09.json').exists()
for case in ['A','B','C']:
    for form in FORMS:
        report=SAMPLES/f'report-{case}-{form}.json'
        if report.exists():
            # Only the explicitly observed first three samples precede dispatch.
            assert case=='A' and form=='selected-grid'
            exit_code=0;origin='recorded first group'
        else:
            free=shutil.disk_usage(ROOT).free
            if free<160*1024*1024:
                result={'passed':False,'scope':'incomplete_storage_gate','groups':groups,'free_bytes':free,
                        'required_groups':30,'required_samples':90,'input_hashes':hashes,'implementation_commit':IMPLEMENTATION,'product_acceptance':'unrun'}
                (HERE/'fixed-controller-report-09.json').write_text(json.dumps(result,indent=2)+'\n')
                print(json.dumps({'storage_gate':'insufficient','completed_groups':len(groups),'free_bytes':free}),flush=True)
                raise SystemExit(2)
            command=[str(DRIVER),str(ORIGINAL),str(SAMPLES),'run',case,form]
            with (HERE/f'fixed09-{case}-{form}.stdout').open('x') as out,(HERE/f'fixed09-{case}-{form}.stderr').open('x') as err:
                process=subprocess.run(command,stdout=out,stderr=err)
            exit_code=process.returncode;origin='fresh sequential invocation'
        data=json.loads(report.read_text()) if report.exists() else None
        if data is not None:
            assert data['class']==case and data['form']==form and data['profile']=='release'
            assert data['samples']==3 and len(data['runs'])==3
            assert sorted(r['sample'] for r in data['runs'])==[1,2,3]
            for sample in data['runs']:
                assert sample['maximum_core_ms']==(500 if case=='C' else 250)
                assert sample['maximum_pipeline_ms']==(4000 if case=='C' else 2000)
                assert sample['fresh_reload_equal'] and sample['receipt_equal']
                assert (SAMPLES/f'{case}-{form}-{sample["sample"]}.json').is_file()
        record={'class':case,'form':form,'terminal_exit_code':exit_code,'origin':origin,'report':report.name,
                'report_sha256':sha(report) if report.exists() else None,'passed':exit_code==0 and data is not None and data['passed']}
        groups.append(record);print(json.dumps(record),flush=True)
unchanged=hashes=={str(p):sha(p) for p in paths}
passed=len(groups)==30 and all(r['passed'] for r in groups) and unchanged
result={'passed':passed,'groups':groups,'samples':90,'input_hashes':hashes,'verification_inputs_unchanged':unchanged,
        'source_comparison':'required separately for every output','implementation_commit':IMPLEMENTATION,'product_acceptance':'unrun','milestone_acceptance':'unrun'}
(HERE/'fixed-controller-report-09.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':passed,'groups':len(groups),'samples':90}),flush=True)
if not passed:raise SystemExit(1)

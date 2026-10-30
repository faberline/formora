#!/usr/bin/env python3
"""Repeat the original 30 single snaps and nine transforms with fixed limits."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
RUN=Path('/private/tmp/formora-delta-retained-39-02')
RUN.mkdir(exist_ok=False)
assert RUN.stat().st_dev==ROOT.stat().st_dev
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
commands=[('single',30,[
    '/private/tmp/formora-delta-single-30-driver',
    str(ROOT/'docs/evidence/mesh-snap-core/performance/fixed-samples/input.json'),str(RUN/'single')]),
    ('transform',9,['/private/tmp/formora-delta-transform-9-driver',str(RUN/'transform')])]
paths=[ROOT/'Cargo.toml',ROOT/'Cargo.lock',Path(__file__),HERE/'legacy-single-driver.rs',HERE/'legacy-transform-driver.rs',
       Path('/private/tmp/formora-target-actual185/release/libformora.rlib'),
       *[Path(command[0]) for _,_,command in commands],*[p for p in sorted((ROOT/'src').rglob('*')) if p.is_file()]]
hashes={str(p):sha(p) for p in paths}
records=[]
for name,count,command in commands:
    with (RUN/(name+'.stdout')).open('x') as out,(RUN/(name+'.stderr')).open('x') as err:
        process=subprocess.run(command,stdout=out,stderr=err)
    path=RUN/name/'report.json';data=json.loads(path.read_text()) if path.exists() else None
    if data is not None:
        assert len(data['runs'])==count and data['profile']=='release'
        for sample in data['runs']:assert sample['maximum_core_ms']==250 and sample['maximum_pipeline_ms']==2000
    record={'name':name,'command':command,'terminal_exit_code':process.returncode,'expected_samples':count,
            'passed':process.returncode==0 and data is not None and data['passed'],
            'report_sha256':sha(path) if path.exists() else None}
    records.append(record);print(json.dumps(record),flush=True)
unchanged=hashes=={str(p):sha(p) for p in paths}
result={'passed':unchanged and all(r['passed'] for r in records),'checks':records,'input_hashes':hashes,
        'verification_inputs_unchanged':unchanged,'implementation_commit':'e16eab6471f32aa85c2bbba867e6fd4e09ead640',
        'source_comparison':'required separately','product_acceptance':'unrun','milestone_acceptance':'unrun'}
(RUN/'controller-report.json').write_text(json.dumps(result,indent=2)+'\n')
if not result['passed']:raise SystemExit(1)

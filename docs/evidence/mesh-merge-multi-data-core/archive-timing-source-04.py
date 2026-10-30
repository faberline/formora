"""Preserve all completed retained timing/source proofs and failed host probes."""
from pathlib import Path
from collections import defaultdict
import gzip
import hashlib
import json

ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')
TEMP=Path('/private/tmp')
OUT=ROOT/'docs/evidence/mesh-merge-multi-data-core/completed-timing-source-04'
load=lambda p:json.loads(Path(p).read_text())
sha=lambda raw:hashlib.sha256(raw).hexdigest()
recovery=load(TEMP/'formora-multi-merge-timing-recovery-02/report.json')
assert recovery['passed'] and recovery['frozen_inputs_unchanged']
assert recovery['retained_timing_samples']==recovery['retained_physical_source_samples']==207
assert recovery['new_timing_samples']==168 and recovery['prior_passed_samples_reused']==39
assert len(recovery['records'])==6 and all(r['passed'] and r['terminal_exit_code']==0 for r in recovery['records'])
for row in recovery['records']:
    assert sha(Path(row['report_path']).read_bytes())==row['report_sha256']
retained39=load(TEMP/'formora-multi-merge-retained-39-01/controller-report.json')
assert retained39['passed'] and retained39['verification_inputs_unchanged']
assert sum(r['expected_samples'] for r in retained39['checks'])==39
assert all(r['passed'] and r['terminal_exit_code']==0 for r in retained39['checks'])
source177=load(TEMP/'formora-multi-merge-retained-source-02/report.json')
assert source177['passed'] and source177['samples']==177 and len(source177['records'])==5
assert sum(r['actual_samples'] for r in source177['records'])==177
assert all(r['passed'] and r['terminal_exit_code']==0 for r in source177['records'])
source30=load(TEMP/'formora-multi-merge-performance-source-01/report.json')
assert source30['passed'] and source30['samples']==30 and source30['all_30_timing_and_physical_source_results_passed']
timings=[]
ninety=TEMP/'formora-multi-merge-retained-90-02/samples'
summary=load(ninety/'timing-summary.json');assert summary['passed'] and summary['samples']==90
for group in summary['groups']:
    data=load(ninety/group['file']);assert data['passed'] and len(data['runs'])==3
    timings.extend((f"scene-{group['class']}",row) for row in data['runs'])
for name,relative,count in [
    ('rotation','formora-multi-merge-retained-rotation-02/samples/timing-summary.json',24),
    ('delta','formora-multi-merge-retained-delta-02/samples/timing-summary.json',24),
    ('single-snap','formora-multi-merge-retained-39-01/single/report.json',30),
    ('transform','formora-multi-merge-retained-39-01/transform/report.json',9),
    ('single-merge','formora-multi-merge-performance-01/samples/timing-summary.json',30)]:
    data=load(TEMP/relative);assert data['passed'] and len(data['runs'])==count
    timings.extend((name,row) for row in data['runs'])
assert len(timings)==207
groups=defaultdict(list)
for name,row in timings:
    assert row['passed'] and row['core_ms']<=row['maximum_core_ms'] and row['operation_save_reload_ms']<=row['maximum_pipeline_ms']
    assert (row['maximum_core_ms'],row['maximum_pipeline_ms'])==((500,4000) if name=='scene-C' else (250,2000))
    groups[name].append(row)
stats={name:{'samples':len(rows),'maximum_core_ms':max(r['core_ms'] for r in rows),
             'maximum_pipeline_ms':max(r['operation_save_reload_ms'] for r in rows),
             'core_limit_ms':rows[0]['maximum_core_ms'],'pipeline_limit_ms':rows[0]['maximum_pipeline_ms']}
       for name,rows in groups.items()}
OUT.mkdir(exist_ok=False)
rows=[];empty=[]
def copy(source,relative):
    assert source.is_file() and not source.is_symlink(),source
    raw=source.read_bytes()
    keep=source.suffix in ['.gz','.py','.png'] or source.name in ['report.json','bindings.json','started.json','terminal.json']
    payload=raw if keep else gzip.compress(raw,mtime=0,compresslevel=6)
    target=OUT/(relative if keep else relative+'.gz');target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:f.write(payload)
    assert target.read_bytes()==payload and (payload if keep else gzip.decompress(payload))==raw
    assert source.read_bytes()==raw
    rows.append({'source':str(source),'stored':target.relative_to(OUT).as_posix(),
                 'raw_bytes':len(raw),'raw_sha256':sha(raw),'stored_sha256':sha(payload)})
folders=[('scene-90',TEMP/'formora-multi-merge-retained-90-02'),
    ('rotation-24',TEMP/'formora-multi-merge-retained-rotation-02'),
    ('delta-24',TEMP/'formora-multi-merge-retained-delta-02'),
    ('single-transform-39',TEMP/'formora-multi-merge-retained-39-01'),
    ('single-merge-30',TEMP/'formora-multi-merge-performance-01'),
    ('source-177',TEMP/'formora-multi-merge-retained-source-02'),
    ('source-30',TEMP/'formora-multi-merge-performance-source-01'),
    ('recovery-parent',TEMP/'formora-multi-merge-timing-recovery-02'),
    ('recovery-bindings',TEMP/'formora-multi-merge-timing-recovery-drivers-02'),
    ('first-bindings',TEMP/'formora-multi-merge-timing-runners-01'),
    ('first-source-bindings',TEMP/'formora-multi-merge-source-runners-01'),
    ('failed-host-scene',TEMP/'formora-multi-merge-retained-90-01'),
    ('failed-host-rotation',TEMP/'formora-multi-merge-retained-rotation-01'),
    ('failed-host-delta',TEMP/'formora-multi-merge-retained-delta-01')]
for name,folder in folders:
    assert folder.is_dir(),folder
    if not list(folder.iterdir()):empty.append(str(folder))
    for path in sorted(folder.rglob('*')):
        if path.is_file():copy(path,name+'/'+path.relative_to(folder).as_posix())
        elif path.is_dir() and not list(path.iterdir()):empty.append(str(path))
with (OUT/'timing-summary.json').open('x') as f:json.dump({'all_207_timing_and_physical_sources_passed':True,'groups':stats},f,indent=2);f.write('\n')
with (OUT/'archive-manifest.json').open('x') as f:json.dump({'lossless_copies_verified':True,
    'originals_preserved':True,'files':rows,'preserved_empty_directories':empty,
    'retained_timing_samples_passed':207,'retained_physical_source_samples_passed':207,
    'previous_39_passed_samples_not_repeated':True,'workloads_clocks_limits_validation_unchanged':True,
    'source_continuous_absolute_limit':1e-6,'source_discrete_comparison':'exact',
    'first_host_probe_failures_preserved':True,'product_acceptance':'unrun','independent_acceptance':'unrun'},f,indent=2);f.write('\n')
print(json.dumps({'lossless_files_verified':len(rows),'timing_samples':207,'source_samples':207,'timing_groups':stats}),flush=True)

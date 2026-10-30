"""Losslessly preserve all completed full-interface raw records and audits."""
from pathlib import Path
import gzip
import hashlib
import json
import time

ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')
TEMP=Path('/private/tmp')
RAW=TEMP/'formora-multi-merge-api-full-01'
OUT=ROOT/'docs/evidence/mesh-merge-multi-data-core/completed-full-runtime-03'
load=lambda p:json.loads(Path(p).read_text())
digest=lambda b:hashlib.sha256(b).hexdigest()
report=load(RAW/'report.json')
assert report['complete'] and report['executed_records']==report['required_records']==26880 and report['failed_records']==0
assert report['outcomes']=={'finished_source_comparison':18176,'explicit_enum_rejection':8704}
audit=load(TEMP/'formora-multi-merge-api-full-audit-01.json')
assert audit['raw_evidence_passed'] and audit['full_interface_matrix_passed'] and audit['records']==26880 and audit['raw_calls_bound']==860160
assert audit['report_sha256']==digest((RAW/'report.json').read_bytes())
controls=load(TEMP/'formora-multi-merge-api-full-controls-01.json')
assert controls['negative_controls_passed'] and controls['controls']==30 and not controls['forged_operations_executed']
assert controls['pure_constructor_cases']==13440 and controls['constructor_filesystem_reads']==0
parent=load(TEMP/'formora-multi-merge-post-full-01/report.json')
assert parent['input_hashes_unchanged'] and not parent['passed']
assert [(r['name'],r['terminal_exit_code'],r['passed']) for r in parent['records'][:2]]==[
    ('full-raw-audit',0,True),('full-raw-controls',0,True)]
assert all(digest((ROOT/name).read_bytes())==sha for name,sha in report['input_hashes'].items())
OUT.mkdir(exist_ok=False)
rows=[];empty=[];started=time.monotonic()
def copy(source,relative):
    assert source.is_file() and not source.is_symlink(),source
    raw=source.read_bytes()
    keep=source.suffix in ['.gz','.py','.png'] or source.name in ['report.json','started.json','terminal.json']
    payload=raw if keep else gzip.compress(raw,mtime=0,compresslevel=6)
    target=OUT/(relative if keep else relative+'.gz')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:f.write(payload)
    assert target.read_bytes()==payload
    assert (payload if keep else gzip.decompress(payload))==raw
    assert source.read_bytes()==raw
    rows.append({'source':str(source),'stored':target.relative_to(OUT).as_posix(),
                 'raw_bytes':len(raw),'raw_sha256':digest(raw),'stored_sha256':digest(payload)})
    if len(rows)%5000==0:print(json.dumps({'verified_copies':len(rows)}),flush=True)
folders=[('runtime',RAW),('runtime-parent',TEMP/'formora-multi-merge-full-process-01'),
         ('audit-and-first-host-probe-diagnostic',TEMP/'formora-multi-merge-post-full-01'),
         ('first-timing-host-probe-diagnostic',TEMP/'formora-multi-merge-retained-timing-controller-01')]
for name,folder in folders:
    for path in sorted(folder.rglob('*')):
        if path.is_file():copy(path,name+'/'+path.relative_to(folder).as_posix())
        elif path.is_dir() and not list(path.iterdir()):empty.append(str(path))
for relative,source in [
    ('full-raw-audit.json',TEMP/'formora-multi-merge-api-full-audit-01.json'),
    ('full-corruption-controls.json',TEMP/'formora-multi-merge-api-full-controls-01.json'),
    ('controllers/full-runtime-parent.py',TEMP/'formora-multi-merge-full-controller-01.py'),
    ('controllers/first-post-full.py',TEMP/'formora-multi-merge-post-full-01.py'),
    ('controllers/timing-recovery-preparation.py',TEMP/'formora-multi-merge-prepare-timing-recovery-02.py'),
    ('controllers/timing-recovery.py',TEMP/'formora-multi-merge-timing-recovery-02.py')]:
    copy(source,relative)
for interface in ['cli','official_mcp_sdk']:
    records=[r for r in report['records'] if r['interface']==interface]
    assert len(records)==13440
    for r in records:
        assert digest((RAW/r['file']).read_bytes())==r['sha256']
manifest={'lossless_copies_verified':True,'originals_preserved':True,'files':rows,
          'preserved_empty_directories':empty,'full_interface_records':26880,'raw_calls_bound':860160,
          'outcomes':report['outcomes'],'full_raw_evidence_and_30_controls_passed':True,
          'first_post_full_timing_parent':'failed on sandbox host probes; not accepted as a timing pass',
          'retained_207_timing_source_evidence':'separate recovery run; not accepted by this archive',
          'source_constructor_filesystem_reads':0,'forged_operations_executed':False,
          'product_acceptance':'unrun','independent_acceptance':'unrun','milestones_accepted':0}
with (OUT/'archive-manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
print(json.dumps({'lossless_files_verified':len(rows),'raw_records':26880,'raw_calls_bound':860160,
                  'elapsed_seconds':time.monotonic()-started,'product_acceptance':'unrun'}),flush=True)

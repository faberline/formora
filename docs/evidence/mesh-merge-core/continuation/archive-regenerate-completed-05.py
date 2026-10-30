"""Archive the complete repaired-build retained run and all five raw audits."""
from pathlib import Path
import gzip,hashlib,json
HERE=Path(__file__).resolve().parent;OUT=HERE/'regenerate-completed-05';OUT.mkdir(exist_ok=False);rows=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def archive(p,relative):
 raw=p.read_bytes();compress=len(raw)>1024*1024 and p.suffix in ['.json','.stdout'];suffix='.gz' if compress else '.bytes' if p.name.endswith('.formora.lock') else ''
 q=OUT/(relative+suffix);q.parent.mkdir(exist_ok=True,parents=True);assert not q.exists();q.write_bytes(gzip.compress(raw,compresslevel=6,mtime=0) if compress else raw)
 assert hashlib.sha256(gzip.decompress(q.read_bytes()) if compress else q.read_bytes()).hexdigest()==sha(p)
 rows.append({'source':str(p),'archive':q.relative_to(OUT).as_posix(),'raw_bytes':len(raw),'raw_sha256':sha(p),'bytes':q.stat().st_size,'sha256':sha(q),'encoding':'lossless gzip; fixed mtime=0' if compress else 'original bytes'})
for name in ['retained-api-01','retained-api-audit-01']:
 source=Path('/private/tmp')/('formora-merge-regen-'+name)
 for p in sorted(source.rglob('*')):
  if p.is_file():archive(p,name+'/'+p.relative_to(source).as_posix())
 for ext in ['stdout','stderr']:
  p=source.with_suffix('.'+ext)
  if p.is_file():archive(p,'process-logs/'+p.name)
for name in ['delta','rotation','scene','single','transform']:
 for ext in ['stdout','stderr']:
  p=Path('/private/tmp')/f'formora-merge-regen-retained-audit-{name}-01.{ext}';archive(p,'process-logs/'+p.name)
for name in ['complete-api-audit-01.json','baseline-strict-01.stdout','baseline-strict-01.stderr']:
 p=Path('/private/tmp')/('formora-merge-regen-'+name);archive(p,p.name)
complete=json.loads(Path('/private/tmp/formora-merge-regen-complete-api-audit-01.json').read_bytes());assert complete['raw_api_audit_passed'] and complete['total_requests']==16374
result={'archive_valid':True,'files':len(rows),'raw_bytes':sum(r['raw_bytes'] for r in rows),'stored_bytes':sum(r['bytes'] for r in rows),'records':rows,'implementation_commit':'5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d','bounded_merge_and_regeneration_local_checks_passed':True,'all_16374_raw_interface_records_checked':True,'retained_asset_checks':1687,'retained_parent_terminal_exit':0,'all_207_timings_and_physical_source_comparisons_passed':True,'required_full_baseline_ready':False,'baseline_strict_terminal_exit':2,'three_platform_ci':'failed to start; not accepted','dependency_integration':'unrun','independent_codex_acceptance':'unrun','milestones_accepted':0,'overall_product_acceptance':'unrun','original_files_removed':False}
(OUT/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['archive_valid','files','raw_bytes','stored_bytes','bounded_merge_and_regeneration_local_checks_passed','milestones_accepted']}),flush=True)

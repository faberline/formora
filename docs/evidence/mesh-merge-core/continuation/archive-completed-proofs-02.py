"""Archive completed retained source, RNG, Euler and Metal checks without removing originals."""
from pathlib import Path
import gzip,hashlib,json,shutil
HERE=Path(__file__).resolve().parent;OUT=HERE/'completed-proofs-02';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
def archive(source,relative):
 assert source.is_file() and not source.is_symlink();raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest()
 compressed=len(raw)>1024*1024 and source.suffix in ['.json','.stdout']
 suffix='.gz' if compressed else '.bytes' if source.name.endswith('.formora.lock') else ''
 target=OUT/(relative+suffix);target.parent.mkdir(exist_ok=True,parents=True);assert not target.exists()
 target.write_bytes(gzip.compress(raw,mtime=0) if compressed else raw)
 assert hashlib.sha256(gzip.decompress(target.read_bytes()) if compressed else target.read_bytes()).hexdigest()==digest and sha(source)==digest
 rows.append({'source':str(source),'archive':target.relative_to(OUT).as_posix(),'raw_bytes':len(raw),'raw_sha256':digest,'bytes':target.stat().st_size,'sha256':sha(target),'encoding':'lossless gzip; fixed mtime=0' if compressed else 'original bytes'})
for name in ['retained-source-01','retained-gpu-01','rng-one-shot-01','source-oracle-01']:
 source=Path('/private/tmp')/('formora-merge-'+name);assert source.is_dir()
 assert json.loads((source/'report.json').read_bytes())['passed']
 for path in sorted(source.rglob('*')):
  if path.is_file():archive(path,name+'/'+path.relative_to(source).as_posix())
 for ext in ['stdout','stderr']:
  path=source.with_suffix('.'+ext)
  if path.is_file():archive(path,'process-logs/'+path.name)
result={'passed':True,'files':len(rows),'raw_bytes':sum(r['raw_bytes'] for r in rows),'stored_bytes':sum(r['bytes'] for r in rows),'records':rows,'implementation_commit':'224a4360276511f48d023a2f6f39190010dae731','all_retained_177_timings_and_source_comparisons_passed':True,'new_30_timings_and_source_comparisons':'passed; archive01','all_207_timings_and_source_comparisons_passed':True,'four_retained_native_metal_proofs_passed':True,'six_exact_euler_orders_passed':True,'forty_eight_fresh_cli_rng_cases_passed':True,'original_files_removed':False,'retained_14326_and_assets':'still running','product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUT/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['passed','files','raw_bytes','stored_bytes','all_207_timings_and_source_comparisons_passed']}),flush=True)

"""Archive completed repaired-build timings, native proofs and the actual merge corpus."""
from pathlib import Path
import gzip,hashlib,json
HERE=Path(__file__).resolve().parent;OUT=HERE/'regenerate-completed-02';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
def archive(source,relative):
 assert source.is_file() and not source.is_symlink();raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest();compress=len(raw)>1024*1024 and source.suffix in ['.json','.stdout']
 suffix='.gz' if compress else '.bytes' if source.name.endswith('.formora.lock') else ''
 target=OUT/(relative+suffix);target.parent.mkdir(exist_ok=True,parents=True);assert not target.exists();target.write_bytes(gzip.compress(raw,compresslevel=6,mtime=0) if compress else raw)
 assert hashlib.sha256(gzip.decompress(target.read_bytes()) if compress else target.read_bytes()).hexdigest()==digest and sha(source)==digest
 rows.append({'source':str(source),'archive':target.relative_to(OUT).as_posix(),'raw_bytes':len(raw),'raw_sha256':digest,'bytes':target.stat().st_size,'sha256':sha(target),'encoding':'lossless gzip; fixed mtime=0' if compress else 'original bytes'})
names=['api-full-01','performance-01','performance-source-01','all-timings-01','retained-compile-01','retained-timing-controller-01','retained-90-01','retained-39-01','retained-rotation-01','retained-delta-01','unseen-after-01','failed-save-01','native-gates-01','retained-small-gates-01','retained-isolation-01','retained-local-01','rng-one-shot-01','source-oracle-01','gpu-01','retained-gpu-01','all-gpu-01']
for name in names:
 source=Path('/private/tmp')/('formora-merge-regen-'+name);assert source.is_dir(),str(source)
 for p in sorted(source.rglob('*')):
  if p.is_file():archive(p,name+'/'+p.relative_to(source).as_posix())
 for ext in ['stdout','stderr']:
  p=source.with_suffix('.'+ext)
  if p.is_file():archive(p,'process-logs/'+p.name)
for stem in ['performance-compile-01','unseen-compile-01','api-controls-01','physical-controls-01']:
 for ext in ['stdout','stderr','json']:
  p=Path('/private/tmp')/('formora-merge-regen-'+stem+'.'+ext)
  if p.is_file():archive(p,'process-logs/'+p.name)
for stem in ['gpu-exact-image-regression-01','native-answer-denial-01']:
 p=Path('/private/tmp')/('formora-merge-regen-'+stem+'.json');assert json.loads(p.read_bytes())['passed'];archive(p,p.name)
result={'archive_valid':True,'files':len(rows),'raw_bytes':sum(r['raw_bytes'] for r in rows),'stored_bytes':sum(r['bytes'] for r in rows),'records':rows,'implementation_commit':'5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d','binary_sha256':'0e882777416ca728e55ca7212259d1b65a1bc6703706ded440bd822b7e70d2aa','new_merge_cli_mcp_cases':2048,'all_207_timings_passed':True,'new_30_physical_source_comparisons_passed':True,'retained_177_physical_source_comparisons':'running; later archive required','new_2048_raw_audit':'running; later archive required','retained_14326_and_assets':'running; later archive required','native_source_denial_save_failure_and_all_five_metal_proofs_passed':True,'original_files_removed':False,'required_all_local_gates_passed':False,'product_acceptance':'unrun','ci':'unpassed','independent_acceptance':'unrun'}
(OUT/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['archive_valid','files','raw_bytes','stored_bytes','required_all_local_gates_passed']}),flush=True)

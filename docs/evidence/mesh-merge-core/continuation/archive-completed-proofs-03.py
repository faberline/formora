"""Archive the complete retained API proof and the newly found required recipe failure."""
from pathlib import Path
import gzip,hashlib,json,shutil
HERE=Path(__file__).resolve().parent;OUT=HERE/'completed-proofs-03';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
def archive(source,relative):
 assert source.is_file() and not source.is_symlink();raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest()
 compressed=len(raw)>1024*1024 and source.suffix in ['.json','.stdout']
 suffix='.gz' if compressed else '.bytes' if source.name.endswith('.formora.lock') else ''
 target=OUT/(relative+suffix);target.parent.mkdir(exist_ok=True,parents=True);assert not target.exists()
 target.write_bytes(gzip.compress(raw,mtime=0) if compressed else raw)
 assert hashlib.sha256(gzip.decompress(target.read_bytes()) if compressed else target.read_bytes()).hexdigest()==digest and sha(source)==digest
 rows.append({'source':str(source),'archive':target.relative_to(OUT).as_posix(),'raw_bytes':len(raw),'raw_sha256':digest,'bytes':target.stat().st_size,'sha256':sha(target),'encoding':'lossless gzip; fixed mtime=0' if compressed else 'original bytes'})
for name in ['retained-api-01','retained-api-audit-01','recipe-proof-01','recipe-proof-02','recipe-proof-03']:
 source=Path('/private/tmp')/('formora-merge-'+name);assert source.is_dir()
 if name=='retained-api-01':assert json.loads((source/'report.json').read_bytes())['passed']
 for path in sorted(source.rglob('*')):
  if path.is_file():archive(path,name+'/'+path.relative_to(source).as_posix())
 for ext in ['stdout','stderr']:
  path=source.with_suffix('.'+ext)
  if path.is_file():archive(path,'process-logs/'+path.name)
for name in ['delta','rotation','scene','single','transform']:
 for ext in ['stdout','stderr']:
  path=Path('/private/tmp')/f'formora-merge-retained-audit-{name}-01.{ext}';archive(path,'process-logs/'+path.name)
archive(Path('/private/tmp/formora-merge-complete-api-audit-01.json'),'complete-api-audit-01.json')
result={'archive_valid':True,'files':len(rows),'raw_bytes':sum(r['raw_bytes'] for r in rows),'stored_bytes':sum(r['bytes'] for r in rows),'records':rows,'implementation_commit':'224a4360276511f48d023a2f6f39190010dae731','retained_14326_and_assets_controller_terminal_exit':0,'complete_16374_raw_source_audit_passed':True,'all_required_local_gates_passed':False,'required_recipe_gate':'FAILED; preserved real call27 edit-state validation error; issue76','original_files_removed':False,'product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUT/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['archive_valid','files','raw_bytes','stored_bytes','all_required_local_gates_passed']}),flush=True)

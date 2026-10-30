"""Archive repaired-build core checks and the complete actual recipe workflows."""
from pathlib import Path
import gzip,hashlib,json
HERE=Path(__file__).resolve().parent;OUT=HERE/'regenerate-completed-01';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
def archive(source,relative):
 raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest();compress=len(raw)>1024*1024 and source.suffix in ['.json','.stdout']
 suffix='.gz' if compress else '.bytes' if source.name.endswith('.formora.lock') else ''
 target=OUT/(relative+suffix);target.parent.mkdir(exist_ok=True,parents=True);assert not target.exists();target.write_bytes(gzip.compress(raw,mtime=0) if compress else raw)
 assert hashlib.sha256(gzip.decompress(target.read_bytes()) if compress else target.read_bytes()).hexdigest()==digest and sha(source)==digest
 rows.append({'source':str(source),'archive':target.relative_to(OUT).as_posix(),'raw_bytes':len(raw),'raw_sha256':digest,'bytes':target.stat().st_size,'sha256':sha(target),'encoding':'lossless gzip' if compress else 'original bytes'})
folder=Path('/private/tmp/formora-merge-recipe-proof-04');recipe=json.loads((folder/'report.json').read_bytes());assert recipe['passed'] and recipe['cases']==20 and recipe['negative_atomic_controls']==120 and recipe['inputs_unchanged']
for p in sorted(folder.rglob('*')):
 if p.is_file():archive(p,'recipe04/'+p.relative_to(folder).as_posix())
for stem in ['formora-merge-recipe-proof-04','formora-regen-native-tests-after-01','formora-regen-allfeatures-tests-01','formora-regen-python-tests-01','formora-regen-clippy-01','formora-regen-fmt-02','formora-regen-build-01','formora-regen-release-01','formora-regen-preview-build-01']:
 for ext in ['stdout','stderr']:
  p=Path('/private/tmp')/(stem+'.'+ext);archive(p,'process-logs/'+p.name)
result={'archive_valid':True,'files':len(rows),'records':rows,'implementation_commit':'5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d','binary_sha256':sha(Path('/private/tmp/formora-merge-regen-target-actual185/debug/formora')),'rust_tests':303,'python_tests':215,'rust_ignored':0,'core_clippy_format_build_terminals':0,'recipe_terminal':0,'recipe_workflows':20,'recipe_atomic_negative_requests':120,'all_required_prior_gates_on_this_build':'running or unrun','required_ci':'unpassed','product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUT/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['archive_valid','files','rust_tests','python_tests','recipe_workflows']}),flush=True)

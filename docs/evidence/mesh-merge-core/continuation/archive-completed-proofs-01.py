"""Copy completed proof outputs and bind every archived byte to its native file."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=HERE/'completed-proofs-01';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
names=['api-full-03','api-audit-03','performance-04','performance-source-04','unseen-after-01','failed-save-01','gpu-01','retained-compile-01','retained-timing-controller-01','retained-timing-controller-02','retained-90-01','retained-90-02','retained-39-01','retained-rotation-01','retained-rotation-02','retained-delta-01','retained-delta-02','retained-small-gates-01','retained-isolation-01','retained-local-controller-02','retained-local-02']
rows=[]
def copy_file(source,dest):
 assert source.is_file() and not source.is_symlink();dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
 before=sha(source);shutil.copyfile(source,dest);assert sha(source)==sha(dest)==before
 rows.append({'source':str(source),'archive':dest.relative_to(OUT).as_posix(),'bytes':source.stat().st_size,'sha256':before})
for name in names:
 source=Path('/private/tmp')/('formora-merge-'+name);assert source.is_dir(),str(source)
 for path in sorted(source.rglob('*')):
  if path.is_file():copy_file(path,OUT/name/path.relative_to(source))
for stem in ['api-full-03','api-audit-03','performance-04','performance-source-04','unseen-after-compile-01','retained-timing-controller-01','retained-timing-controller-02','retained-small-gates-01','retained-local-controller-02','api-controls-03','physical-controls-03','performance-compile-03']:
 for suffix in ['.stdout','.stderr','.json']:
  path=Path('/private/tmp')/('formora-merge-'+stem+suffix)
  if path.is_file():copy_file(path,OUT/'process-logs'/path.name)
for path in [Path('/private/tmp/formora-merge-gpu-projection-check-01.json'),Path('/private/tmp/formora-merge-authored-input-01.json'),Path('/private/tmp/formora-merge-render-vertices-01.rs'),Path('/private/tmp/formora-merge-render-vertices-before-01.json'),Path('/private/tmp/formora-merge-render-vertices-after-01.json')]:
 copy_file(path,OUT/'gpu-diagnostics'/path.name)
report={'passed':True,'files':len(rows),'raw_bytes':sum(r['bytes'] for r in rows),'records':rows,'implementation_commit':'224a4360276511f48d023a2f6f39190010dae731','binary_sha256':sha(Path('/private/tmp/formora-merge-target-actual185/debug/formora')),'retained_source_comparison':'running; not archived here','retained_14326_and_assets':'running; not archived here','first_failed_or_unrun_attempts_preserved':True,'product_acceptance':'unrun'}
(OUT/'archive-manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['passed','files','raw_bytes','binary_sha256']}),flush=True)

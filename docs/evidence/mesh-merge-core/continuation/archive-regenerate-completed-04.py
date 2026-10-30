"""Archive all retained physical timing comparisons and denied-source repair controls."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;OUT=HERE/'regenerate-completed-04';OUT.mkdir(exist_ok=False);rows=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def archive(source,relative):
 target=OUT/relative;target.parent.mkdir(exist_ok=True,parents=True);assert not target.exists();raw=source.read_bytes();target.write_bytes(raw);assert sha(source)==sha(target)
 rows.append({'source':str(source),'archive':target.relative_to(OUT).as_posix(),'bytes':len(raw),'sha256':sha(target)})
for name in ['retained-source-01','six-denied-run-01']:
 source=Path('/private/tmp')/('formora-merge-regen-'+name);assert json.loads((source/'report.json').read_bytes())['passed']
 for p in sorted(source.rglob('*')):
  if p.is_file():archive(p,name+'/'+p.relative_to(source).as_posix())
 for ext in ['stdout','stderr']:
  p=source.with_suffix('.'+ext)
  if p.is_file():archive(p,'process-logs/'+p.name)
for ext in ['stdout','stderr']:
 p=Path('/private/tmp/formora-merge-regen-six-denied-compile-01.'+ext);archive(p,'process-logs/'+p.name)
result={'archive_valid':True,'files':len(rows),'records':rows,'implementation_commit':'5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d','all_207_timing_and_physical_source_results_passed':True,'all_six_frozen_repair_controls_and_sixty_combinations_passed_with_source_and_answer_denial':True,'retained_full_interface_and_asset_gates':'still running','product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUT/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'archive_valid':True,'files':len(rows),'all_207_timing_and_source_samples_passed':True}))

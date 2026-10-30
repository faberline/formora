"""Run unchanged source checks with captured paths bound to this full checkout."""
import hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')
sys.path.insert(0,str(ROOT/'tools'))
name=sys.argv.pop(1)
relative={'scene':'docs/evidence/scene-snap-core/performance/compare-performance.py','rotation':'docs/evidence/snap-rotation-core/performance/compare-performance.py','delta':'docs/evidence/snap-delta-core/performance/compare-performance.py'}[name]
script=ROOT/relative
spec=importlib.util.spec_from_file_location('retained_source_'+name,script)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
resolutions=[]
def sha(path):
 path=Path(path);prefix='/Users/chrischeng/faberlines/formora/'
 actual=ROOT/str(path)[len(prefix):] if str(path).startswith(prefix) else path
 digest=hashlib.sha256(actual.read_bytes()).hexdigest()
 if actual!=path:resolutions.append({'captured_path':str(path),'actual_path':str(actual),'sha256':digest})
 return digest
module.sha=sha
try:module.main()
finally:
 output=Path(sys.argv[sys.argv.index('--output')+1]);path=output.with_suffix('.path-bindings.json')
 path.write_text(json.dumps({'checker':relative,'checker_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'changed_assertions':False,'path_bindings':resolutions},indent=2)+'\n')

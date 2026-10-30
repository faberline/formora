"""Bind unchanged fixed timing workloads and checks to the repaired implementation."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
impl='5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bindings=[]
def rebind(source,dest,extra=()):
 path=HERE/source;raw=path.read_text()
 for old,new in [('/private/tmp/formora-merge-target-actual185/','/private/tmp/formora-merge-regen-target-actual185/'),('224a4360276511f48d023a2f6f39190010dae731',impl),('86ad80551979b51ac339b83b2733455f589abdb486448afa19cd204d50e654ea','a06c8aa897ce51992ca08779627eb4041ef0db51d4ccca9dab08ce3fdbc1a0f6'),('formora-merge-retained-','formora-merge-regen-retained-'),*extra]:raw=raw.replace(old,new)
 target=HERE/dest;assert not target.exists();target.write_text(raw)
 bindings.append({'source':source,'source_sha256':sha(path),'copy':dest,'copy_sha256':sha(target),'changes':'only actual implementation/library/executable, controller and fresh output bindings; original native driver sources, workloads, clocks, validations and limits unchanged'})
rebind('retained-compile-config-01.json','regenerate-retained-compile-config-01.json')
rebind('retained-compile-01.py','regenerate-retained-compile-01.py',[('retained-compile-config-01.json','regenerate-retained-compile-config-01.json')])
for name in ['90','39','rotation','delta']:rebind(f'retained-run-{name}-01.py',f'regenerate-retained-run-{name}-01.py')
rebind('retained-timing-controller-01.py','regenerate-retained-timing-controller-01.py',[('retained-run-{name}-01.py','regenerate-retained-run-{name}-01.py')])
extra=[]
for name in ['90','rotation','delta']:extra.append((f'formora-merge-regen-retained-{name}-02',f'formora-merge-regen-retained-{name}-01'))
rebind('retained-compare-all-sources-01.py','regenerate-retained-compare-all-sources-01.py',extra)
rebind('run-performance-04.py','regenerate-run-performance-01.py',[('formora-merge-performance-04','formora-merge-regen-performance-01'),('formora-merge-performance-driver-03','formora-merge-regen-performance-driver-01')])
rebind('compare-performance-04.py','regenerate-compare-performance-01.py',[('formora-merge-performance-source-04','formora-merge-regen-performance-source-01'),('formora-merge-performance-04','formora-merge-regen-performance-01')])
(HERE/'regenerate-timing-bindings-01.json').write_text(json.dumps(bindings,indent=2)+'\n')

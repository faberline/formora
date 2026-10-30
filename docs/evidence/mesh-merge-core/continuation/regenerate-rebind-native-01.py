"""Bind retained native proofs to the repaired build, retaining their assertions."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;rows=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pairs=[('/private/tmp/formora-merge-target-actual185/','/private/tmp/formora-merge-regen-target-actual185/'),('/private/tmp/formora-merge-allfeatures-actual185/','/private/tmp/formora-merge-regen-allfeatures-actual185/'),('224a4360276511f48d023a2f6f39190010dae731','5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d'),('86ad80551979b51ac339b83b2733455f589abdb486448afa19cd204d50e654ea','a06c8aa897ce51992ca08779627eb4041ef0db51d4ccca9dab08ce3fdbc1a0f6'),('5bf40a3c99843bd7b9395d3d712f605756284cd44aa07c2925661b7c7bd5c3c2','0e882777416ca728e55ca7212259d1b65a1bc6703706ded440bd822b7e70d2aa'),('5fe37fe3ce8c556e4cd5c01fe27f086fd422e5de8ad3a765de4c428b0ee15f7f','0f1923e013d95d8b19a4c16bb5e05b949aa5c8f359dd93d869707b0146c1411d')]
for name in ['unseen-core-after-01','unseen-after-01','failed-save-01','gpu-01','rng-one-shot-01','source-oracle-01']:pairs.append(('formora-merge-'+name,'formora-merge-regen-'+name))
pairs.extend([('formora-merge-retained-','formora-merge-regen-retained-'),('formora-merge-(api|pilot|performance)','formora-merge-(regen-)?(api|pilot|performance|retained|recipe)')])
def rebind(source,dest,extra=()):
 p=HERE/source;raw=p.read_text()
 for before,after in [*pairs,*extra]:raw=raw.replace(before,after)
 q=HERE/dest;assert not q.exists();q.write_text(raw)
 rows.append({'source':source,'source_sha256':sha(p),'copy':dest,'copy_sha256':sha(q),'changes':'current implementation/build bindings and fresh outputs; expanded prior-answer read denial for both output families; original authored inputs, assertions and limits retained'})
for source in ['run-unseen-denial-after-01.py','failed-save-proof-01.py','gpu-proof-01.py','retained-rng-isolation-01.py','retained-rng-one-shot-01.py','retained-source-oracle-01.py','retained-gpu-rng-01.py','retained-gpu-mirror-01.py']:rebind(source,'regenerate-'+source)
rebind('retained-small-gates-config-01.json','regenerate-retained-small-gates-config-01.json',[('/continuation/retained-rng-isolation-01.py','/continuation/regenerate-retained-rng-isolation-01.py')])
rebind('retained-small-gates-01.py','regenerate-retained-small-gates-01.py',[('retained-small-gates-config-01.json','regenerate-retained-small-gates-config-01.json'),('records=[]',"Path('/private/tmp/formora-merge-regen-retained-local-01').mkdir(exist_ok=False)\nrecords=[]")])
rebind('retained-gpu-01.py','regenerate-retained-gpu-01.py',[("HERE/'retained-gpu-rng-01.py'","HERE/'regenerate-retained-gpu-rng-01.py'"),("HERE/'retained-gpu-mirror-01.py'","HERE/'regenerate-retained-gpu-mirror-01.py'")])
(HERE/'regenerate-native-bindings-01.json').write_text(json.dumps(rows,indent=2)+'\n')

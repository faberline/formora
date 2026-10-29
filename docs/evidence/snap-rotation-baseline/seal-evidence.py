"""Seal exact changed bytes without changing a source or raw artifact."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
DEST=HERE/'evidence-manifest.json'
BASE='9572c28100d2a0fed31ed620fed7a9b061e26ef6'
names=set()
for command in [['git','diff',BASE,'--name-only','-z'],
                ['git','ls-files','--others','--exclude-standard','-z']]:
    names.update(name for name in subprocess.check_output(command,cwd=ROOT).split(b'\0') if name)
records=[]
for name in sorted(names):
    path=ROOT/name.decode()
    if path==DEST:continue
    raw=path.read_bytes()
    records.append({'path':name.decode(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                    'git_blob_sha1':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
assert records and max(row['bytes'] for row in records)<100_000_000
value={'base_commit':BASE,'contract_commit':'bb3bdb3d','authored_inputs_commit':'de019498',
       'files':records,'file_count':len(records),'total_bytes':sum(row['bytes'] for row in records),
       'manifest_excludes_itself':True,'product_acceptance':'unrun','milestones_accepted':0}
with DEST.open('x') as output:json.dump(value,output,indent=2);output.write('\n')
print(json.dumps({key:item for key,item in value.items() if key!='files'}))

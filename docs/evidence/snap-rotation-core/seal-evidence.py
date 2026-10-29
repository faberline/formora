"""Seal exact changed bytes. Keep all raw data and the failed preparation trial."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
DEST=HERE/'evidence-manifest.json'
BASE='c425d470c78825412f182d39ae658f7c323c118c'
names=set()
for command in [['git','diff',BASE,'--name-only','-z'],['git','ls-files','--others','--exclude-standard','-z']]:
    names.update(name for name in subprocess.check_output(command,cwd=ROOT).split(b'\0') if name)
records=[]
for name in sorted(names):
    path=ROOT/name.decode()
    if path==DEST:continue
    size=path.stat().st_size;sha=hashlib.sha256();blob=hashlib.sha1(b'blob '+str(size).encode()+b'\0')
    with path.open('rb') as source:
        while chunk:=source.read(1024*1024):sha.update(chunk);blob.update(chunk)
    records.append({'path':name.decode(),'bytes':size,'sha256':sha.hexdigest(),'git_blob_sha1':blob.hexdigest()})
assert records and max(row['bytes'] for row in records)<100_000_000
value={'base_commit':BASE,'implementation_commit':'c67d2370c00d2031adb7d896c978b25ffdd3d885',
    'files':records,'file_count':len(records),'total_bytes':sum(row['bytes'] for row in records),
    'manifest_excludes_itself':True,'product_acceptance':'unrun','milestones_accepted':0}
with DEST.open('x') as out:json.dump(value,out,indent=2);out.write('\n')
print(json.dumps({key:item for key,item in value.items() if key!='files'}))

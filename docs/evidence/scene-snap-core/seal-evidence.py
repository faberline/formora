"""Hash retained evidence bytes without changing or removing any artifact."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DEST = HERE / 'evidence-manifest.json'
paths = subprocess.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '--',
     'docs/evidence/scene-snap-core', 'docs/verification/scene-snap-core.md'], cwd=ROOT
).split(b'\0')
records = []
for name in sorted(set(paths)):
    if not name:
        continue
    path = ROOT / name.decode()
    if path == DEST:
        continue
    size = path.stat().st_size
    sha = hashlib.sha256()
    blob = hashlib.sha1(b'blob ' + str(size).encode() + b'\0')
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            sha.update(chunk)
            blob.update(chunk)
    records.append({'path': name.decode(), 'bytes': size,
                    'sha256': sha.hexdigest(), 'git_blob_sha1': blob.hexdigest()})
assert records and max(row['bytes'] for row in records) < 100_000_000
value = {'implementation_commit': 'dcb484218708959ac28b4a1ac79d5ef8b4156a02',
         'files': records, 'file_count': len(records),
         'total_bytes': sum(row['bytes'] for row in records),
         'manifest_excludes_itself': True, 'milestones_accepted': 0,
         'product_acceptance': 'unrun'}
with DEST.open('x') as output:
    json.dump(value, output, indent=2)
    output.write('\n')
print(json.dumps({key: item for key, item in value.items() if key != 'files'}))

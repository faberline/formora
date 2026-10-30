"""Preserve all pilot raw records and parent receipts without deleting originals."""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE/'interface-pilots-01'
OUT.mkdir(exist_ok=False)
rows = []


def archive(source, relative):
    raw = source.read_bytes()
    target = OUT/(relative if source.suffix == '.gz' else relative+'.gz')
    payload = raw if source.suffix == '.gz' else gzip.compress(raw, mtime=0)
    if source.suffix != '.gz':
        assert gzip.decompress(payload) == raw
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(payload)
    assert source.read_bytes() == raw and target.read_bytes() == payload
    rows.append({'source': str(source), 'stored': target.relative_to(OUT).as_posix(),
                 'raw_bytes': len(raw), 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                 'stored_sha256': hashlib.sha256(payload).hexdigest()})


for name in ['api-pilot-02', 'api-pilot-03', 'pilot-process-03']:
    source = Path('/private/tmp')/('formora-multi-merge-'+name)
    for path in sorted(source.rglob('*')):
        if path.is_file():
            archive(path, name+'/'+path.relative_to(source).as_posix())
for name in ['pilot-plan-01.json', 'pilot-audit-03.json', 'pilot-controls-03.json', 'pilot-controller-03.py']:
    archive(Path('/private/tmp')/('formora-multi-merge-'+name), name)
with (OUT/'archive-manifest.json').open('x') as stream:
    json.dump({'originals_preserved': True, 'lossless_copies_verified': True, 'files': rows,
               'full_matrix_passed': False, 'product_acceptance': 'unrun'}, stream, indent=2)
    stream.write('\n')
print(json.dumps({'lossless_copies_verified': True, 'files': len(rows)}))

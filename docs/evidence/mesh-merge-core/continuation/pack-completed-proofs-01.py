"""Create a second, lossless archive without removing any original evidence."""
from pathlib import Path
import gzip
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / 'completed-proofs-01'
OUT = HERE / 'completed-proofs-gzip-01'
OUT.mkdir(exist_ok=False)
data = json.loads((ORIGINAL / 'archive-manifest.json').read_bytes())

def digest(stream):
    h = hashlib.sha256()
    while block := stream.read(1024 * 1024):
        h.update(block)
    return h.hexdigest()

for row in data['records']:
    source = ORIGINAL / row['archive']
    compressed = row['bytes'] > 1024 * 1024 and source.suffix in ['.json', '.stdout']
    target = OUT / (row['archive'] + ('.gz' if compressed else ''))
    target.parent.mkdir(parents=True, exist_ok=True)
    if compressed:
        with source.open('rb') as raw, target.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0, compresslevel=6) as packed:
            shutil.copyfileobj(raw, packed)
        with gzip.open(target, 'rb') as raw:
            assert digest(raw) == row['sha256']
    else:
        shutil.copyfile(source, target)
        with target.open('rb') as raw:
            assert digest(raw) == row['sha256']
    with Path(row['source']).open('rb') as raw:
        assert digest(raw) == row['sha256']
    row.update(raw_bytes=row['bytes'], raw_sha256=row['sha256'], archive=target.relative_to(OUT).as_posix(), bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest(), encoding='lossless gzip; fixed mtime=0' if compressed else 'original bytes')

data['stored_bytes'] = sum(r['bytes'] for r in data['records'])
data['all_decompressed_original_hashes_verified'] = True
data['original_files_removed'] = False
(OUT / 'archive-manifest.json').write_text(json.dumps(data, indent=2) + '\n')
print(json.dumps({k: data[k] for k in ['passed', 'files', 'raw_bytes', 'stored_bytes']}), flush=True)

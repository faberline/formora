#!/usr/bin/env python3
"""Preserve exact completed native artifacts and reconstruct their raw bytes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--restore', action='store_true')
args = parser.parse_args()
source, output = args.source.resolve(), args.output.resolve()
assert source.is_dir() and not output.exists()
sha = lambda data: hashlib.sha256(data).hexdigest()


def relative(name):
    path = Path(name)
    assert not path.is_absolute() and '..' not in path.parts
    return path


output.mkdir(parents=True, exist_ok=False)
if args.restore:
    manifest = json.loads((source / 'archive-manifest.json').read_bytes())
    for row in manifest['files']:
        stored = (source / relative(row['stored_path'])).read_bytes()
        assert sha(stored) == row['stored_sha256'] and len(stored) == row['stored_bytes']
        raw = gzip.decompress(stored) if row['gzip'] else stored
        assert sha(raw) == row['raw_sha256'] and len(raw) == row['raw_bytes']
        path = output / relative(row['raw_path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    print(json.dumps({'restored_files': len(manifest['files']), 'all_raw_hashes_match': True}))
else:
    assert source.parent == Path('/private/tmp') and source.name.startswith('formora-zero-')
    files = sorted(p for p in source.rglob('*') if p.is_file())
    rows = []
    for path in files:
        assert not path.is_symlink()
        raw = path.read_bytes()
        name = path.relative_to(source)
        compressed = len(raw) > 100000
        stored_name = Path(str(name) + '.gz') if compressed else name
        payload = gzip.compress(raw, mtime=0) if compressed else raw
        assert (gzip.decompress(payload) if compressed else payload) == raw
        target = output / stored_name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(payload)
        rows.append({'raw_path': str(name), 'stored_path': str(stored_name),
                     'raw_bytes': len(raw), 'raw_sha256': sha(raw), 'gzip': compressed,
                     'stored_bytes': len(payload), 'stored_sha256': sha(payload)})
    for row in rows:
        path = source / relative(row['raw_path'])
        assert sha(path.read_bytes()) == row['raw_sha256'], 'source changed during archive'
        stored = (output / relative(row['stored_path'])).read_bytes()
        assert sha(stored) == row['stored_sha256']
        assert sha(gzip.decompress(stored) if row['gzip'] else stored) == row['raw_sha256']
    manifest = {'source_directory': str(source), 'files': rows,
                'raw_bytes': sum(r['raw_bytes'] for r in rows),
                'stored_bytes': sum(r['stored_bytes'] for r in rows),
                'all_raw_bytes_preserved': True, 'original_files_unchanged': True,
                'compression_after_timing': True, 'archiver_sha256': sha(Path(__file__).read_bytes()),
                'source_comparisons': 'recorded separately', 'product_acceptance': 'unrun'}
    with (output / 'archive-manifest.json').open('x') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))

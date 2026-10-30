#!/usr/bin/env python3
"""Store lossless evidence copies. Keep every original and failed attempt."""
import gzip
import hashlib
import json
from pathlib import Path

from runtime_artifacts import write_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/evidence/object-state-query'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def archive(source, name, exclude=()):
    destination = OUT/name
    destination.mkdir(exist_ok=False)
    rows, external = [], []
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        raw = path.read_bytes()
        if str(relative) in exclude:
            external.append({'path': str(path), 'raw_sha256': sha(raw), 'raw_bytes': len(raw)})
            continue
        if path.suffix == '.gz':
            stored = destination/relative
            payload = raw
        else:
            stored = destination/(str(relative)+'.gz')
            payload = gzip.compress(raw, mtime=0)
            assert gzip.decompress(payload) == raw
        stored.parent.mkdir(exist_ok=True, parents=True)
        with stored.open('xb') as stream:
            stream.write(payload)
        assert path.read_bytes() == raw and stored.read_bytes() == payload
        rows.append({'original': relative.as_posix(), 'stored': stored.relative_to(destination).as_posix(),
                     'raw_sha256': sha(raw), 'stored_sha256': sha(payload), 'raw_bytes': len(raw)})
    write_json(destination/'archive-manifest.json', {
        'lossless_copies_verified': True, 'originals_preserved': True, 'source': str(source),
        'files': rows, 'external_artifacts_preserved': external})
    print(json.dumps({'archive': name, 'verified_files': len(rows)}), flush=True)


if __name__ == '__main__':
    runtime = Path('/private/tmp/formora-object-state-runtime-01')
    assert json.loads((runtime/'report.json').read_text())['complete']
    verification = Path('/private/tmp/formora-object-state-runtime-01-verification.json')
    assert json.loads(verification.read_text())['source_and_product_gate_passed']
    capacity = Path('/private/tmp/formora-object-state-capacity-product-01')
    assert json.loads((capacity/'report.json').read_text())['product_timing_passed']
    isolation = Path('/private/tmp/formora-object-state-isolation-02')
    assert json.loads((isolation/'report.json').read_text())['passed']
    archive(runtime, 'runtime-01')
    archive(capacity, 'capacity-01')
    archive(isolation, 'isolation-02')
    archive(Path('/private/tmp/formora-object-state-build-01'), 'compile-diagnostic-01')
    archive(Path('/private/tmp/formora-object-state-build-02'), 'build-02', exclude=('formora-preview',))
    with (OUT/'runtime-verification-01.json').open('xb') as stream:
        stream.write(verification.read_bytes())

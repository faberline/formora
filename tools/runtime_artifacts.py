"""Store exact runtime JSON bytes with optional lossless compression."""
import gzip
import json
from pathlib import Path


def write_json(path, data, compressed=False):
    raw=(json.dumps(data,allow_nan=False)+'\n').encode('utf-8')
    path=Path(path)
    if compressed:
        path=path.with_suffix(path.suffix+'.gz')
        payload=gzip.compress(raw,mtime=0)
        assert gzip.decompress(payload)==raw
    else:payload=raw
    # Exclusive creation preserves both previous outputs and failed partial files.
    with path.open('xb') as stream:stream.write(payload)
    return path


def read_json(path):
    path=Path(path);raw=path.read_bytes()
    if path.suffix=='.gz':raw=gzip.decompress(raw)
    return json.loads(raw)

"""Archive exact measured scene bytes losslessly; reconstruct before native reads."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

def sha(data):return hashlib.sha256(data).hexdigest()
def relative(name):
    path=Path(name)
    assert not path.is_absolute() and '..' not in path.parts
    return path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
parser.add_argument('--restore',action='store_true')
args=parser.parse_args();source=args.source.resolve();output=args.output.resolve()
assert source.is_dir() and not output.exists()
if args.restore:
    index=json.loads((source/'scene-archive-index.json').read_text());output.mkdir()
    for row in index['files']:
        stored=source/relative(row['stored_path']);encoded=stored.read_bytes()
        assert sha(encoded)==row['stored_sha256']
        if row['encoding']=='gzip':
            with gzip.open(stored,'rb') as stream:data=stream.read(row['raw_bytes']+1)
        else:data=encoded
        assert len(data)==row['raw_bytes'] and sha(data)==row['raw_sha256']
        path=output/relative(row['raw_path']);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
    print(json.dumps({'restored':len(index['files']),'all_raw_hashes_match':True}))
else:
    assert source.parent==Path('/private/tmp') and source.name.startswith('formora-delta-')
    controller=json.loads((source/'controller-report.json').read_text())
    assert controller['implementation_commit']=='e16eab6471f32aa85c2bbba867e6fd4e09ead640'
    files=sorted(p for p in source.rglob('*') if p.is_file() and not p.name.endswith('.formora.lock'))
    assert not (source/'scene-archive-index.json').exists()
    rows=[]
    for path in files:
        assert not path.is_symlink()
        data=path.read_bytes();name=path.relative_to(source).as_posix();scene=False
        if path.suffix=='.json':
            value=json.loads(data)
            scene=isinstance(value,dict) and value.get('schema_version')==1 and 'entities' in value and 'revision' in value
        stored=path
        if scene:
            stored=path.with_name(path.name+'.gz');assert not stored.exists()
            with stored.open('xb') as stream:
                with gzip.GzipFile(filename='',fileobj=stream,mode='wb',mtime=0) as compressed:compressed.write(data)
            assert gzip.decompress(stored.read_bytes())==data
        rows.append({'raw_path':name,'stored_path':stored.relative_to(source).as_posix(),
            'encoding':'gzip' if scene else 'raw','raw_bytes':len(data),'raw_sha256':sha(data),
            'stored_bytes':stored.stat().st_size,'stored_sha256':sha(stored.read_bytes())})
    # Verify every compressed copy before removing any redundant raw scene.
    for row in rows:
        path=source/relative(row['raw_path']);assert sha(path.read_bytes())==row['raw_sha256']
        stored=source/relative(row['stored_path']);assert sha(stored.read_bytes())==row['stored_sha256']
        if row['encoding']=='gzip':assert sha(gzip.decompress(stored.read_bytes()))==row['raw_sha256']
    index={'original_run_path':str(source),'archive_path':str(output),'files':rows,
        'raw_scene_count':sum(r['encoding']=='gzip' for r in rows),'all_raw_bytes_preserved':True,
        'compression_after_timing':True,'raw_bytes':sum(r['raw_bytes'] for r in rows),
        'stored_bytes':sum(r['stored_bytes'] for r in rows),'controller_passed':controller['passed'],
        'requires_exact_reconstruction_before_native_reads':True,'product_acceptance':'unrun'}
    with (source/'scene-archive-index.json').open('x') as stream:json.dump(index,stream,indent=2);stream.write('\n')
    for row in rows:
        if row['encoding']=='gzip':
            path=source/relative(row['raw_path']);assert sha(path.read_bytes())==row['raw_sha256'];path.unlink()
    output.parent.mkdir(parents=True,exist_ok=True)
    assert source.stat().st_dev==output.parent.stat().st_dev
    source.rename(output)
    for row in rows:
        stored=output/relative(row['stored_path']);assert sha(stored.read_bytes())==row['stored_sha256']
        if row['encoding']=='gzip':assert sha(gzip.decompress(stored.read_bytes()))==row['raw_sha256']
    print(json.dumps({'archived':len(rows),'raw_scenes':index['raw_scene_count'],
        'all_raw_bytes_preserved':True,'raw_bytes':index['raw_bytes'],'stored_bytes':index['stored_bytes']}))

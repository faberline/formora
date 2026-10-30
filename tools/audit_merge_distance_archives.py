"""Verify every retained native diagnostic copy without rerunning Blender."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def audit(root):
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    rows = []
    for path in sorted(root.glob('diagnostic-[0-9][0-9]/archive-manifest.json')):
        manifest = json.loads(path.read_text())
        assert manifest['originals_preserved'] and manifest['lossless_copies_verified']
        assert manifest['initial_binding_cases_passed']+manifest['initial_binding_failures'] == manifest['captured_cases']
        for row in manifest['files']:
            data = (path.parent/row['stored']).read_bytes()
            assert sha(data) == row['stored_sha256'], row['stored']
            raw = data if sha(data) == row['raw_sha256'] else gzip.decompress(data)
            assert sha(raw) == row['raw_sha256'], row['stored']
        rows.append({'attempt': path.parent.name, 'cases': manifest['captured_cases'],
                     'passes': manifest['initial_binding_cases_passed'], 'failures': manifest['initial_binding_failures'],
                     'files': len(manifest['files']), 'manifest_sha256': sha(path.read_bytes())})
    return {'archives': rows, 'attempts': len(rows), 'native_cases': sum(row['cases'] for row in rows),
            'lossless_files': sum(row['files'] for row in rows), 'failed_initial_checks_retained': sum(row['failures'] for row in rows),
            'full_source_gate': 'unrun', 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = audit(args.root)
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'archives'}))

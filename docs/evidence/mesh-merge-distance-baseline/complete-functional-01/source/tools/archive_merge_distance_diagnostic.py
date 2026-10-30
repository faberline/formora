"""Keep lossless diagnostic copies, including failed checks and exact inputs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def archive(native, check_path, controller, output):
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((native/'capture/manifest.json').read_text())
    terminal = json.loads((native/'terminal.json').read_text())
    started = json.loads((native/'started.json').read_text())
    check = json.loads(check_path.read_text())
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    assert terminal['terminal_exit_code'] == 0 and terminal['timed_out'] is False
    assert terminal['process_id'] == started['process_id'] == manifest['process_id']
    assert sha((native/'stdout').read_bytes()) == terminal['stdout_sha256']
    assert sha((native/'stderr').read_bytes()) == terminal['stderr_sha256']
    assert check['cases'] == len(manifest['runs'])
    assert check['full_source_gate'] == check['product_acceptance'] == 'unrun'
    output.mkdir(exist_ok=False)
    rows = []

    def copy(source, relative):
        raw = source.read_bytes()
        # Preserve upstream whitespace exactly. Store Python sources with blank
        # EOF lines as gzip so repository format checks do not alter evidence.
        keep = (source.suffix == '.gz' or (source.suffix == '.py' and not raw.endswith(b'\n\n')) or
                source.name in ['report.json', 'manifest.json', 'started.json', 'terminal.json'])
        data = raw if keep else gzip.compress(raw, mtime=0)
        target = output/(relative if keep else relative+'.gz')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream: stream.write(data)
        assert target.read_bytes() == data and (data if keep else gzip.decompress(data)) == raw
        assert source.read_bytes() == raw
        rows.append({'source': str(source), 'stored': target.relative_to(output).as_posix(),
                     'raw_sha256': sha(raw), 'stored_sha256': sha(data)})

    for path in sorted(native.rglob('*')):
        if path.is_file(): copy(path, 'native/'+path.relative_to(native).as_posix())
    for name, digest in manifest['input_hashes'].items():
        path = Path(name)
        assert sha(path.read_bytes()) == digest, name
        copy(path, 'source/'+path.relative_to(root).as_posix())
    copy(controller, 'controllers/'+controller.name)
    copy(check_path, 'initial-check.json')
    result = {'originals_preserved': True, 'lossless_copies_verified': True, 'files': rows,
              'captured_cases': check['cases'], 'native_terminal_exit': 0,
              'initial_binding_cases_passed': sum(row['checks_passed'] for row in check['records']),
              'initial_binding_failures': sum(not row['checks_passed'] for row in check['records']),
              'full_source_gate': 'unrun', 'product_acceptance': 'unrun'}
    with (output/'archive-manifest.json').open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    return {'preserved_files': len(rows), 'initial_binding_failures_preserved': result['initial_binding_failures']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['native', 'check', 'controller', 'output']: parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(archive(args.native, args.check, args.controller, args.output)))

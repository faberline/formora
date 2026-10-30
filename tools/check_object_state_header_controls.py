#!/usr/bin/env python3
"""Exercise the frozen source validator without modifying source artifacts."""
import argparse
import copy
import json
from pathlib import Path
from unittest.mock import patch

from compare_object_state_reference import digest, load_capture
from generate_object_state_cases import author


def check(suite_path, folder, output):
    suite = json.loads(suite_path.read_text())
    assert suite == author()
    load_capture(folder, suite_path, suite)
    paths = {'manifest': folder/'manifest.json',
             'terminal': folder.with_name(folder.name+'-process')/'terminal.json'}
    originals = {key: path.read_text() for key, path in paths.items()}
    hashes = {key: digest(path) for key, path in paths.items()}
    read_text = Path.read_text
    rows = []

    def reject(name, key, mutate, expected):
        value = copy.deepcopy(json.loads(originals[key]))
        if mutate is not None:
            mutate(value)

        def read(path, *args, **kwargs):
            if path == paths[key]:
                if mutate is None:
                    raise FileNotFoundError('deliberately absent terminal receipt')
                return json.dumps(value)
            return read_text(path, *args, **kwargs)

        with patch.object(Path, 'read_text', read):
            try:
                load_capture(folder, suite_path, suite)
            except (AssertionError, ValueError, KeyError, FileNotFoundError) as error:
                assert expected in str(error), (name, str(error))
                rows.append({'control': name, 'rejected': True, 'error': str(error)})
            else:
                raise AssertionError('forged header admitted: '+name)

    reject('missing_case', 'manifest', lambda m: m['runs'].pop(), 'missing/duplicate')
    reject('duplicate_case', 'manifest', lambda m: m['runs'].__setitem__(1, m['runs'][0]), 'missing/duplicate')
    reject('wrong_source_version', 'manifest', lambda m: m.update(version=[5, 2, 2]), 'source identity')
    reject('wrong_source_binary', 'manifest', lambda m: m.update(binary_sha256='0'*64), 'source identity')
    reject('failed_terminal', 'terminal', lambda t: t.update(terminal_exit_code=1), 'terminal failed/missing')
    reject('timed_out_terminal', 'terminal', lambda t: t.update(timed_out=True), 'terminal failed/missing')
    reject('missing_terminal', 'terminal', None, 'absent terminal receipt')
    assert hashes == {key: digest(path) for key, path in paths.items()}
    report = {'negative_controls_passed': True, 'controls': len(rows), 'rows': rows,
              'forged_operations_executed': False, 'source_artifacts_unchanged': True,
              'method': 'override only the selected file read within the frozen validator',
              'validator_sha256': digest(Path(__file__).with_name('compare_object_state_reference.py')),
              'source_manifest_sha256': hashes['manifest'], 'product_acceptance': 'unrun'}
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'negative_controls_passed': True, 'controls': len(rows)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check(args.suite.resolve(), args.capture.resolve(), args.output.resolve())

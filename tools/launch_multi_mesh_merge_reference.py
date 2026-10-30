#!/usr/bin/env python3
"""Run one dedicated native capture and retain its actual terminal status."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path('/Applications/Blender.app/Contents/MacOS/Blender')
BINARY_SHA = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def launch(suite, output, case_ids, timeout):
    assert digest(BINARY) == BINARY_SHA
    assert not output.exists() and not output.with_name(output.name + '.staging').exists()
    receipt = output.with_name(output.name + '-process')
    receipt.mkdir(parents=True, exist_ok=False)
    command = [str(BINARY), '--factory-startup', '--python',
               str(ROOT / 'tools/blender_multi_mesh_merge_reference.py'), '--',
               '--suite', str(suite), '--output', str(output)]
    for id in case_ids:
        command.extend(['--case', id])
    with (receipt / 'stdout').open('xb') as stdout, (receipt / 'stderr').open('xb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        started = time.monotonic()
        write(receipt / 'started.json', {
            'process_id': process.pid, 'command_line': command,
            'started_utc': datetime.now(timezone.utc).isoformat(),
            'binary_sha256': BINARY_SHA, 'suite_sha256': digest(suite),
            'scope': 'focused_diagnostic' if case_ids else 'complete_13440_multi_data_merge_cases',
        })
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
    terminal = {
        'process_id': process.pid, 'terminal_exit_code': code, 'timed_out': timed_out,
        'elapsed_seconds': time.monotonic() - started,
        'ended_utc': datetime.now(timezone.utc).isoformat(),
        'manifest_sha256': digest(output / 'manifest.json') if (output / 'manifest.json').is_file() else None,
        'capture_lock_sha256': digest(output / 'capture-lock.json') if (output / 'capture-lock.json').is_file() else None,
        'stdout_sha256': digest(receipt / 'stdout'), 'stderr_sha256': digest(receipt / 'stderr'),
        'product_acceptance': 'unrun',
    }
    write(receipt / 'terminal.json', terminal)
    print(json.dumps(terminal), flush=True)
    return code if code else (1 if timed_out or terminal['manifest_sha256'] is None else 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[], dest='case_ids')
    parser.add_argument('--timeout', type=float, default=7200.)
    args = parser.parse_args()
    raise SystemExit(launch(args.suite.resolve(), args.output.resolve(), args.case_ids, args.timeout))

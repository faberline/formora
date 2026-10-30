#!/usr/bin/env python3
"""Run a dedicated fixed Blender process and retain its real terminal exit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path('/Applications/Blender.app/Contents/MacOS/Blender')
SHA = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def launch(suite, output):
    assert digest(BINARY) == SHA and not output.exists()
    assert not output.with_name(output.name+'.staging').exists()
    receipt = output.with_name(output.name+'-process')
    receipt.mkdir(parents=True, exist_ok=False)
    command = [str(BINARY), '--factory-startup', '--python',
               str(ROOT/'tools/blender_object_state_reference.py'), '--',
               '--suite', str(suite), '--output', str(output)]
    with (receipt/'stdout').open('xb') as stdout, (receipt/'stderr').open('xb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        started = time.monotonic()
        write(receipt/'started.json', {'process_id': process.pid, 'command_line': command,
              'binary_sha256': SHA, 'suite_sha256': digest(suite),
              'started_utc': datetime.now(timezone.utc).isoformat()})
        timed_out = False
        try:
            code = process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
    terminal = {'process_id': process.pid, 'terminal_exit_code': code,
                'timed_out': timed_out, 'elapsed_seconds': time.monotonic()-started,
                'manifest_sha256': digest(output/'manifest.json') if (output/'manifest.json').exists() else None,
                'stdout_sha256': digest(receipt/'stdout'), 'stderr_sha256': digest(receipt/'stderr')}
    write(receipt/'terminal.json', terminal)
    print(json.dumps(terminal), flush=True)
    return 0 if code == 0 and not timed_out and terminal['manifest_sha256'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(launch(args.suite.resolve(), args.output.resolve()))

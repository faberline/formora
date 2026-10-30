#!/usr/bin/env python3
"""Retain actual native child identity, logs and terminal status."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--cases', type=Path)
parser.add_argument('--diagnostic', action='store_true')
args = parser.parse_args()
folder = Path(__file__).resolve().parent / args.name
folder.mkdir(exist_ok=False)
binary = Path('/Applications/Blender.app/Contents/MacOS/Blender')
command = [str(binary), '--factory-startup', '--python', str(root / ('tools/blender_snap_singular_diagnostic.py' if args.diagnostic else 'tools/blender_snap_singular_reference.py')),
    '--', '--suite', str(root / 'baseline/fixtures/snap-singular.json'), '--output', str(args.output.resolve())]
if args.cases:
    for id in json.loads(args.cases.read_text()):
        command += ['--case', id]
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
receipt = {'command': command, 'started_utc': datetime.now(timezone.utc).isoformat(),
    'launcher_sha256': digest(Path(__file__)), 'binary_sha256': digest(binary),
    'capture': str(args.output.resolve()), 'terminal_exit_code': None}
with (folder / 'stdout').open('xb') as stdout, (folder / 'stderr').open('xb') as stderr:
    child = subprocess.Popen(command, stdout=stdout, stderr=stderr)
    receipt['process_id'] = child.pid
    (folder / 'started.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'started_native_pid': child.pid}), flush=True)
    code = child.wait()
receipt['terminal_exit_code'] = code
receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
if (args.output / 'manifest.json').exists():
    receipt['manifest_sha256'] = digest(args.output / 'manifest.json')
    receipt['capture_lock_sha256'] = digest(args.output / 'capture-lock.json')
receipt['stdout_sha256'] = digest(folder / 'stdout')
receipt['stderr_sha256'] = digest(folder / 'stderr')
(folder / 'terminal.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt), flush=True)
sys.exit(code if code >= 0 else 1)

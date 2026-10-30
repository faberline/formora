#!/usr/bin/env python3
"""Retain actual before-code native grid process, logs and terminal exit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--name', required=True)
args = parser.parse_args()
folder = HERE / args.name
folder.mkdir(exist_ok=False)
binary = Path('/Applications/Blender.app/Contents/MacOS/Blender')
command = [str(binary), '--factory-startup', '--python', str(HERE / 'blender-grid-reference.py'),
           '--', '--output', str(args.output.resolve())]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
record = {'command': command, 'started_utc': datetime.now(timezone.utc).isoformat(),
          'launcher_sha256': sha(Path(__file__)), 'binary_sha256': sha(binary),
          'capture': str(args.output.resolve()), 'terminal_exit_code': None}
with (folder / 'stdout').open('xb') as stdout, (folder / 'stderr').open('xb') as stderr:
    child = subprocess.Popen(command, stdout=stdout, stderr=stderr)
    record['process_id'] = child.pid
    (folder / 'started.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'started_native_pid': child.pid}), flush=True)
    code = child.wait()
record['terminal_exit_code'] = code
record['finished_utc'] = datetime.now(timezone.utc).isoformat()
if (args.output / 'manifest.json').exists():
    record['manifest_sha256'] = sha(args.output / 'manifest.json')
record['stdout_sha256'] = sha(folder / 'stdout')
record['stderr_sha256'] = sha(folder / 'stderr')
(folder / 'terminal.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
sys.exit(code if code >= 0 else 1)

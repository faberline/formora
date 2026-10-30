#!/usr/bin/env python3
"""Bind actual Blender process, logs, hashes and waited terminal status."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
binary = Path('/Applications/Blender.app/Contents/MacOS/Blender')
command = [str(binary), '--factory-startup', '--python', str(HERE / 'blender-grid-reference.py'),
           '--', '--output', str(args.output / 'capture')]
receipt = {'command': command, 'binary_sha256': sha(binary), 'launcher_sha256': sha(Path(__file__)),
           'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
with (args.output / 'stdout').open('xb') as stdout, (args.output / 'stderr').open('xb') as stderr:
    child = subprocess.Popen(command, stdout=stdout, stderr=stderr)
    receipt['process_id'] = child.pid
    (args.output / 'started.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'process_id': child.pid}), flush=True)
    code = child.wait()
receipt.update(terminal_exit_code=code, stdout_sha256=sha(args.output / 'stdout'),
               stderr_sha256=sha(args.output / 'stderr'))
manifest = args.output / 'capture/manifest.json'
if manifest.exists():
    receipt['manifest_sha256'] = sha(manifest)
(args.output / 'terminal.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt), flush=True)
raise SystemExit(code if code >= 0 else 1)

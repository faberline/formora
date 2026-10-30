"""Retain the actual corruption-check process and wait result."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT=Path('/private/tmp/formora-merge-distance-baseline')
OUT=Path('/private/tmp/formora-distance-control-driver-06');OUT.mkdir(exist_ok=False)
SCRIPT=ROOT/'tools/check_merge_distance_diagnostic_controls.py'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
script_hash=sha(SCRIPT)
command=['/Users/chrischeng/.pyenv/versions/3.12.11/bin/python3',str(SCRIPT),
         '--suite',str(ROOT/'baseline/fixtures/mesh-merge-distance-diagnostic-08.json'),
         '--native','/private/tmp/formora-merge-distance-native-diagnostic-10',
         '--output',str(ROOT/'docs/evidence/mesh-merge-distance-baseline/diagnostic-controls-06')]
started=time.monotonic()
with (OUT/'stdout').open('x') as stdout,(OUT/'stderr').open('x') as stderr:
    child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
    (OUT/'started.json').write_text(json.dumps({'process_id':child.pid,'command_line':command,'script_sha256':script_hash},indent=2)+'\n')
    code=child.wait(timeout=180)
receipt={'process_id':child.pid,'terminal_exit_code':code,'elapsed_seconds':time.monotonic()-started,
         'stdout_sha256':sha(OUT/'stdout'),'stderr_sha256':sha(OUT/'stderr'),'script_unchanged':script_hash==sha(SCRIPT)}
(OUT/'terminal.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt));print((OUT/'stderr').read_text()[-6000:])
raise SystemExit(code or (0 if receipt['script_unchanged'] else 1))

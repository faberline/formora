"""Wait on all frozen full-registry corruption checks without short timeout."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT=Path('/private/tmp/formora-merge-distance-baseline')
OUT=Path('/private/tmp/formora-distance-complete-control-driver-01');OUT.mkdir(exist_ok=False)
SCRIPT=ROOT/'tools/check_merge_distance_diagnostic_controls.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(SCRIPT)
command=['/Users/chrischeng/.pyenv/versions/3.12.11/bin/python3',str(SCRIPT),
         '--suite',str(ROOT/'baseline/fixtures/mesh-merge-distance-complete-02.json'),
         '--seal',str(ROOT/'baseline/fixtures/mesh-merge-distance-source-seal-01.json'),
         '--native','/private/tmp/formora-distance-complete-source-01',
         '--output',str(ROOT/'docs/evidence/mesh-merge-distance-baseline/complete-controls-01')]
start=time.monotonic()
with (OUT/'stdout').open('x') as stdout,(OUT/'stderr').open('x') as stderr:
    child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
    (OUT/'started.json').write_text(json.dumps({'process_id':child.pid,'command_line':command,'script_sha256':before},indent=2)+'\n')
    code=child.wait(timeout=3600)
receipt={'process_id':child.pid,'terminal_exit_code':code,'elapsed_seconds':time.monotonic()-start,
         'stdout_sha256':sha(OUT/'stdout'),'stderr_sha256':sha(OUT/'stderr'),'script_unchanged':before==sha(SCRIPT)}
(OUT/'terminal.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt));print((OUT/'stdout').read_text()[-2000:]);print((OUT/'stderr').read_text()[-6000:])
raise SystemExit(code or (0 if receipt['script_unchanged'] else 1))

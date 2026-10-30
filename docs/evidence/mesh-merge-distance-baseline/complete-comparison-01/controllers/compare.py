"""Retain the real two-fresh-process comparison command and terminal wait."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT=Path('/private/tmp/formora-merge-distance-baseline')
OUT=Path('/private/tmp/formora-distance-complete-pair-driver-01');OUT.mkdir(exist_ok=False)
command=['/Users/chrischeng/.pyenv/versions/3.12.11/bin/python3',str(ROOT/'tools/compare_merge_distance_complete.py'),
         '--suite',str(ROOT/'baseline/fixtures/mesh-merge-distance-complete-02.json'),
         '--seal',str(ROOT/'baseline/fixtures/mesh-merge-distance-source-seal-01.json'),
         '--first','/private/tmp/formora-distance-complete-source-01',
         '--second','/private/tmp/formora-distance-complete-source-02',
         '--output','/private/tmp/formora-distance-complete-pair-01.json']
start=time.monotonic()
with (OUT/'stdout').open('x') as stdout,(OUT/'stderr').open('x') as stderr:
    child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
    (OUT/'started.json').write_text(json.dumps({'process_id':child.pid,'command_line':command},indent=2)+'\n')
    code=child.wait(timeout=1200)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt={'process_id':child.pid,'terminal_exit_code':code,'elapsed_seconds':time.monotonic()-start,
         'stdout_sha256':sha(OUT/'stdout'),'stderr_sha256':sha(OUT/'stderr')}
(OUT/'terminal.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt));print((OUT/'stdout').read_text()[-2000:]);print((OUT/'stderr').read_text()[-6000:])
raise SystemExit(code)

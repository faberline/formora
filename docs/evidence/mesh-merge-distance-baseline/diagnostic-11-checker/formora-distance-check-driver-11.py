"""Record the actual checker exit, including uncaught source-probe failures."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT=Path('/private/tmp/formora-merge-distance-baseline')
OUT=Path('/private/tmp/formora-distance-diagnostic-check-driver-11');OUT.mkdir(exist_ok=False)
command=['/Users/chrischeng/.pyenv/versions/3.12.11/bin/python3',str(ROOT/'tools/check_merge_distance_diagnostic.py'),
         '--suite',str(ROOT/'baseline/fixtures/mesh-merge-distance-diagnostic-11.json'),
         '--capture','/private/tmp/formora-merge-distance-native-diagnostic-11/capture',
         '--output','/private/tmp/formora-merge-distance-diagnostic-check-11.json']
started=time.monotonic()
with (OUT/'stdout').open('x') as stdout,(OUT/'stderr').open('x') as stderr:
    child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
    (OUT/'started.json').write_text(json.dumps({'process_id':child.pid,'command_line':command},indent=2)+'\n')
    code=child.wait(timeout=120)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt={'process_id':child.pid,'terminal_exit_code':code,'elapsed_seconds':time.monotonic()-started,
         'stdout_sha256':sha(OUT/'stdout'),'stderr_sha256':sha(OUT/'stderr')}
(OUT/'terminal.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt));print((OUT/'stderr').read_text()[-6000:])
raise SystemExit(code)

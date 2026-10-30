"""Record real terminal results even if the first source adapter fails."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT=Path('/private/tmp/formora-merge-distance-baseline')
OUT=Path('/private/tmp/formora-merge-distance-native-diagnostic-04');OUT.mkdir(exist_ok=False)
BINARY=Path('/Applications/Blender.app/Contents/MacOS/Blender')
SUITE=ROOT/'baseline/fixtures/mesh-merge-distance-diagnostic-03.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(BINARY)=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
command=[str(BINARY),'--factory-startup','--python',str(ROOT/'tools/blender_merge_distance_reference.py'),
         '--','--suite',str(SUITE),'--output',str(OUT/'capture')]
started=time.monotonic()
with (OUT/'stdout').open('x') as stdout,(OUT/'stderr').open('x') as stderr:
    child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
    (OUT/'started.json').write_text(json.dumps({'process_id':child.pid,'command_line':command,
        'binary_sha256':sha(BINARY),'suite_sha256':sha(SUITE)},indent=2)+'\n')
    timed_out=False
    try:code=child.wait(timeout=180)
    except subprocess.TimeoutExpired:
        timed_out=True;child.terminate()
        try:code=child.wait(timeout=20)
        except subprocess.TimeoutExpired:child.kill();code=child.wait()
terminal={'process_id':child.pid,'terminal_exit_code':code,'timed_out':timed_out,
          'elapsed_seconds':time.monotonic()-started,'stdout_sha256':sha(OUT/'stdout'),'stderr_sha256':sha(OUT/'stderr')}
(OUT/'terminal.json').write_text(json.dumps(terminal,indent=2)+'\n')
print(json.dumps(terminal),flush=True)
raise SystemExit(0 if code==0 and not timed_out else 1)

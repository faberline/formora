"""Wait for the real native schema probe and validate the complete RNA surface."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import time

ROOT=Path('/private/tmp/formora-merge-distance-baseline')
OUT=ROOT/'docs/evidence/mesh-merge-distance-baseline/native-schema-01';OUT.mkdir(exist_ok=False)
BINARY=Path('/Applications/Blender.app/Contents/MacOS/Blender')
SCRIPT=ROOT/'tools/blender_merge_distance_schema.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
f32=lambda n:struct.unpack('<f',struct.pack('<f',n))[0]
assert sha(BINARY)=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
before={str(p):sha(p) for p in [BINARY,SCRIPT]}
command=[str(BINARY),'--factory-startup','--python',str(SCRIPT),'--','--output',str(OUT/'schema.json')]
started=time.monotonic()
with (OUT/'stdout').open('x') as stdout,(OUT/'stderr').open('x') as stderr:
    child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr)
    (OUT/'started.json').write_text(json.dumps({'process_id':child.pid,'command':command,'input_hashes':before},indent=2)+'\n')
    code=child.wait()
terminal={'process_id':child.pid,'terminal_exit_code':code,'elapsed_seconds':time.monotonic()-started,
          'stdout_sha256':sha(OUT/'stdout'),'stderr_sha256':sha(OUT/'stderr')}
(OUT/'terminal.json').write_text(json.dumps(terminal,indent=2)+'\n')
assert code==0,terminal
schema=json.loads((OUT/'schema.json').read_text())
assert schema['schema_captured'] and schema['process_id']==child.pid and schema['version']==[5,2,3]
assert schema['build_hash']=='e13b728c6880' and schema['background'] is False
assert schema['script_sha256']==before[str(SCRIPT)] and schema['mesh_operations_executed']==0
p=schema['properties']
assert set(p)=={'threshold','use_centroid','use_unselected','use_sharp_edge_from_normals'}
assert p['threshold']['type']=='FLOAT' and p['threshold']['default']==f32(1e-4)
assert p['threshold']['hard_min']==f32(1e-6) and p['threshold']['hard_max']==50.
assert p['threshold']['soft_min']==f32(1e-5) and p['threshold']['soft_max']==10.
for name,default in [('use_centroid',True),('use_unselected',False),('use_sharp_edge_from_normals',False)]:
    assert p[name]['type']=='BOOLEAN' and type(p[name]['default']) is bool and p[name]['default']==default
assert before=={str(p):sha(p) for p in [BINARY,SCRIPT]}
result={'schema_probe_passed':True,'native_process_id':child.pid,'terminal_exit_code':code,
        'schema_sha256':sha(OUT/'schema.json'),'input_hashes_unchanged':True,
        'all_actual_operator_parameters_bound':True,'operator_source_commit':'e13b728c6880d3084d9d57c30031ed5df8b39dee',
        'full_source_cases_executed':0,'input_freeze':'pending','product_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)

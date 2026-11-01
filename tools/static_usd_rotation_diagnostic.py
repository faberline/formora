#!/usr/bin/env python3
"""Bounded diagnosis of retained cross-platform rotation failures; not acceptance."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import time
from runtime_binary import resolve_binary

binary=resolve_binary(sys.argv[1]);output=Path(sys.argv[2]).resolve();output.mkdir(parents=True,exist_ok=False)
retained=json.loads((Path(__file__).resolve().parents[1]/'baseline/static-usd-rotation-diagnostic/748-full-failures.json').read_text())
cases=sorted({97,99,139,*range(900,950),*(int(x['id'].rsplit('_',1)[1]) for x in retained['first_failures'])})
command=[sys.executable,str(Path(__file__).with_name('rotation_snap_runtime.py')),str(binary),str(output/'cases'),'--interface','cli','--gzip-output']
for case in cases:command += ['--case',f'rotation_snap_{case:04}']
start=time.monotonic_ns();process=subprocess.Popen(command);code=process.wait()
(output/'process.json').write_text(json.dumps({'command':command,'pid':process.pid,'waited':True,'exit_code':code,'elapsed_ns':time.monotonic_ns()-start})+'\n')
report=json.loads((output/'cases/report.json').read_text());failed=[r for r in report['runs'] if r['status']=='failed']
print(json.dumps({'diagnostic_only':True,'whole_acceptance':False,'failed_count':len(failed),'failures':failed}),flush=True)
for case in failed[:3]:
    p=output/'cases'/case['file'];print('FORMORA_ROTATION_DIAGNOSTIC_'+case['id'].upper()+'='+base64.b64encode(p.read_bytes()).decode(),flush=True)
sys.exit(code)

#!/usr/bin/env python3
"""Transparent stdio launcher: record the actual child's PID, wait and exit."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

path=Path(sys.argv[1]); command=sys.argv[2:]; start=time.monotonic_ns()
child=subprocess.Popen(command)
def forward(signum, frame):
    if child.poll() is None:
        child.terminate()
signal.signal(signal.SIGTERM,forward)
code=child.wait()
path.write_text(json.dumps({'command':command,'pid':child.pid,'waited':True,
                           'exit_code':code,'elapsed_ns':time.monotonic_ns()-start})+'\n')
sys.exit(code)

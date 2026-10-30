#!/usr/bin/env python3
"""Keep actual product child PIDs and terminal results for official MCP tests."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from runtime_artifacts import write_json
from compare_object_state_reference import digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    args.receipt.mkdir(parents=True, exist_ok=False)
    command = [str(args.binary), 'mcp', '--scene', str(args.scene)]
    with (args.receipt/'stderr').open('xb') as stderr:
        process = subprocess.Popen(command, stdin=sys.stdin, stdout=sys.stdout, stderr=stderr)
        write_json(args.receipt/'started.json', {
            'bridge_pid': os.getpid(), 'process_id': process.pid,
            'command': command, 'binary_sha256': digest(args.binary)})
        code = process.wait()
    write_json(args.receipt/'terminal.json', {
        'process_id': process.pid, 'terminal_exit_code': code,
        'stderr_sha256': digest(args.receipt/'stderr')})
    raise SystemExit(code)

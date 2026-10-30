"""Run one fresh, sealed native viewport capture and retain its actual wait."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

from merge_distance_source_seal import BINARY, digest, verify
from merge_distance_provenance import ROOT


def launch(suite, seal_path, output, timeout):
    seal = verify(suite, seal_path)
    binary = Path('/Applications/Blender.app/Contents/MacOS/Blender')
    assert digest(binary) == BINARY, 'fixed binary changed'
    output.mkdir(exist_ok=False)
    command = [str(binary), '--factory-startup', '--window-geometry', '0', '0', '1080', '800',
               '--python', str(ROOT/'tools/blender_merge_distance_reference.py'), '--',
               '--suite', str(suite), '--seal', str(seal_path), '--output', str(output/'capture')]
    start = time.monotonic(); timed_out = False
    with (output/'stdout').open('x') as stdout, (output/'stderr').open('x') as stderr:
        child = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        (output/'started.json').write_text(json.dumps({'process_id': child.pid, 'command_line': command,
            'binary_sha256': BINARY, 'suite_sha256': digest(suite), 'source_seal_sha256': digest(seal_path),
            'source_code_commit': seal['code_commit'], 'started_utc': datetime.now(timezone.utc).isoformat()}, indent=2)+'\n')
        try: code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True; child.terminate()
            try: code = child.wait(timeout=20)
            except subprocess.TimeoutExpired: child.kill(); code = child.wait()
    result = {'process_id': child.pid, 'terminal_exit_code': code, 'timed_out': timed_out,
              'elapsed_seconds': time.monotonic()-start, 'stdout_sha256': digest(output/'stdout'),
              'stderr_sha256': digest(output/'stderr'), 'source_seal_sha256': digest(seal_path)}
    (output/'terminal.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['suite', 'seal', 'output']: parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args(); result = launch(args.suite.resolve(), args.seal.resolve(), args.output.resolve(), args.timeout)
    print(json.dumps(result), flush=True)
    raise SystemExit(0 if result['terminal_exit_code'] == 0 and not result['timed_out'] else 1)

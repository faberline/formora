#!/usr/bin/env python3
"""Repeat every retained API corpus against the current exact executable."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('binary', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
binary = args.binary.resolve()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = [ROOT / 'Cargo.toml', ROOT / 'Cargo.lock', *sorted((ROOT / 'src').rglob('*.rs')),
         *sorted((ROOT / 'tests').rglob('*.rs')), *sorted((ROOT / 'tools').rglob('*.py'))]
hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
binary_sha = sha(binary)
snap = [('delta', 'tools/delta_snap_runtime.py', 3584),
        ('raw-rotation', 'tools/rotation_snap_runtime.py', 4992),
        ('scene-snap', 'tools/scene_snap_runtime_smoke.py', 1100),
        ('single-snap', 'tools/snap_runtime_smoke.py', 2244),
        ('mesh-transform', 'tools/transform_runtime_smoke.py', 2406)]
assets = [('primitive', 'tools/primitive_reference_smoke.py', 162),
          ('scale', 'tools/remaining_scale_regression.py', 8),
          ('selection', 'tools/selection_runtime_smoke.py', 1060),
          ('creation', 'tools/creation_context_runtime.py', 262),
          ('payload', 'tools/polygon_reference_smoke.py', 57),
          ('normal', 'tools/normal_runtime_smoke.py', 42),
          ('rng', 'tools/random_falloff_runtime.py', 96),
          ('mcp', 'tools/mcp_smoke.py', None)]
assert sum(n for _, _, n in snap) == 14326
records = []
for name, tool, count in [*snap, *assets]:
    command = [sys.executable, tool, str(binary)]
    if name != 'mcp':
        command.append(str(out / name))
    if name in {r[0] for r in snap}:
        command.append('--gzip-output')
    start = time.monotonic_ns()
    with (out / (name + '.stdout')).open('xb') as stdout, (out / (name + '.stderr')).open('xb') as stderr:
        child = subprocess.Popen(command, cwd=ROOT, env=os.environ, stdout=stdout, stderr=stderr)
        (out / (name + '-started.json')).write_text(json.dumps({'process_id': child.pid, 'command': command}, indent=2) + '\n')
        code = child.wait()
    report_path = out / name / ('manifest.json' if name == 'normal' else 'report.json')
    report = json.loads(report_path.read_bytes()) if report_path.exists() else None
    actual = None if report is None else report.get('checks', report.get('cases', len(report.get('runs', []))))
    passed = code == 0 and (name == 'mcp' or (report is not None and report['passed'] is True and actual == count))
    if name in {r[0] for r in snap}:
        passed = passed and report is not None and report['required_full_gate_passed'] is True
    row = {'name': name, 'command': command, 'native_process_id': child.pid, 'terminal_exit_code': code,
           'passed': passed, 'expected_checks': count, 'actual_checks': actual,
           'report_sha256': sha(report_path) if report_path.exists() else None,
           'start_ns': start, 'end_ns': time.monotonic_ns()}
    records.append(row)
    print(json.dumps(row), flush=True)
    (out / 'progress.json').write_text(json.dumps(records, indent=2) + '\n')
unchanged = hashes == {str(p.relative_to(ROOT)): sha(p) for p in paths} and sha(binary) == binary_sha
report = {'passed': all(r['passed'] for r in records) and unchanged,
          'required_retained_snap_requests': 14326, 'records': records,
          'verification_inputs_unchanged': unchanged, 'input_hashes': hashes,
          'binary_sha256': binary_sha, 'driver_sha256': sha(Path(__file__)),
          'implementation_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'product_acceptance': 'unrun'}
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(0 if report['passed'] else 1)

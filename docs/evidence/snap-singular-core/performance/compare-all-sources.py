#!/usr/bin/env python3
"""Run every original retained source gate plus all sixty new results."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('binary', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
binary = args.binary.resolve()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
binary_sha = sha(binary)
base = ROOT / 'docs/evidence'
fresh = Path('/private/tmp')


def common(script, samples, source, controller, report):
    return [sys.executable, str(script), '--binary', str(binary), '--samples', str(samples),
            '--source', str(source), '--controller', str(controller), '--output', str(out / report)]


commands = [
    ('new-zero-60', 60, common(Path(__file__).with_name('compare-physical-results.py'),
        fresh / 'formora-zero-performance-03/samples', base / 'snap-singular-core/performance/source',
        fresh / 'formora-zero-performance-03/controller-report.json', 'new-zero-60.json')),
    ('retained-scene-90', 90, common(base / 'scene-snap-core/performance/compare-performance.py',
        fresh / 'formora-zero-retained-90-01/samples', base / 'scene-snap-core/performance/source-gzip',
        fresh / 'formora-zero-retained-90-01/controller-report.json', 'retained-scene-90.json')),
    ('retained-rotation-24', 24, common(base / 'snap-rotation-core/performance/compare-performance.py',
        fresh / 'formora-zero-retained-rotation-01/samples', base / 'snap-rotation-core/performance/source',
        fresh / 'formora-zero-retained-rotation-01/controller-report.json', 'retained-rotation-24.json')),
    ('retained-delta-24', 24, common(base / 'snap-delta-core/performance/compare-performance.py',
        fresh / 'formora-zero-retained-delta-01/samples', base / 'snap-delta-core/performance/source',
        fresh / 'formora-zero-retained-delta-01/controller-report.json', 'retained-delta-24.json')),
    ('retained-single-30', 30, [sys.executable, str(ROOT / 'tools/compare_snap_performance.py'),
        '--binary', str(binary), '--samples', str(fresh / 'formora-zero-retained-39-01/single'),
        '--source', str(base / 'mesh-snap-core/performance/source'), '--output', str(out / 'retained-single-30.json')]),
    ('retained-transform-9', 9, [sys.executable, str(base / 'snap-delta-core/performance/compare-retained-transform.py'),
        str(fresh / 'formora-zero-retained-39-01/transform'), str(out / 'retained-transform-9.json')]),
]
assert sum(count for _, count, _ in commands) == 237
records = []
for name, count, command in commands:
    with (out / (name + '.stdout')).open('xb') as stdout, (out / (name + '.stderr')).open('xb') as stderr:
        child = subprocess.Popen(command, cwd=ROOT, env=os.environ, stdout=stdout, stderr=stderr)
        (out / (name + '-started.json')).write_text(json.dumps({'pid': child.pid, 'command': command}, indent=2) + '\n')
        code = child.wait()
    path = out / (name + '.json')
    result = json.loads(path.read_bytes()) if path.exists() else None
    actual = None if result is None else result.get('samples', len(result.get('records', [])))
    passed = code == 0 and result is not None and result['passed'] is True and actual == count
    row = {'name': name, 'command': command, 'terminal_exit_code': code, 'process_id': child.pid,
           'expected_samples': count, 'actual_samples': actual, 'passed': passed,
           'report_sha256': sha(path) if path.exists() else None}
    records.append(row)
    (out / 'progress.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(row), flush=True)
report = {'passed': all(r['passed'] for r in records) and sha(binary) == binary_sha,
          'samples': 237, 'new_samples': 60, 'retained_samples': 177, 'records': records,
          'binary_sha256': binary_sha, 'driver_sha256': sha(Path(__file__)),
          'first_failed_trials_remain_failed': True, 'product_acceptance': 'unrun'}
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(0 if report['passed'] else 1)

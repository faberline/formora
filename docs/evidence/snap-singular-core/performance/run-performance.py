#!/usr/bin/env python3
"""Record the fixed native driver and every sample without selecting trials."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
for name in ['binary', 'driver', 'library', 'output']:
    parser.add_argument('--' + name, type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
assert args.output.stat().st_dev == ROOT.stat().st_dev
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = [ROOT / 'Cargo.toml', ROOT / 'Cargo.lock', *sorted((ROOT / 'src').rglob('*.rs')),
         ROOT / 'docs/contracts/snap-singular-core.md',
         *sorted(p for p in HERE.iterdir() if p.suffix in ['.py', '.rs'] or p.name.startswith(('authored-', 'input-'))),
         args.binary, args.driver, args.library]
hashes = {str(p.resolve()): sha(p) for p in paths}
hardware = subprocess.run(['/usr/sbin/sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True)
assert hardware.returncode == 0 and hardware.stdout.strip() == 'Apple M1 Max'


def host(name):
    value = {'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'hardware': hardware.stdout.strip()}
    for key, command in [('top', ['/usr/bin/top', '-l', '1', '-n', '0']),
                         ('swap', ['/usr/sbin/sysctl', 'vm.swapusage'])]:
        p = subprocess.run(command, capture_output=True, text=True)
        value[key] = {'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
    (args.output / name).write_text(json.dumps(value, indent=2) + '\n')


host('host-before.json')
command = [str(args.driver), str(HERE), str(args.output / 'samples')]
with (args.output / 'stdout').open('xb') as stdout, (args.output / 'stderr').open('xb') as stderr:
    child = subprocess.Popen(command, stdout=stdout, stderr=stderr)
    (args.output / 'started.json').write_text(json.dumps({'process_id': child.pid, 'command': command}, indent=2) + '\n')
    code = child.wait()
host('host-after.json')
path = args.output / 'samples/timing-summary.json'
summary = json.loads(path.read_bytes()) if path.exists() else None
unchanged = hashes == {str(p.resolve()): sha(p) for p in paths}
passed = code == 0 and summary is not None and summary['passed'] and unchanged
report = {'passed': passed, 'terminal_exit_code': code, 'process_id': child.pid, 'command': command,
          'input_hashes': hashes, 'verification_inputs_unchanged': unchanged,
          'implementation_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'binary_sha256': sha(args.binary), 'library_sha256': sha(args.library),
          'samples': len(summary['runs']) if summary else 0,
          'timing_summary_sha256': sha(path) if path.exists() else None,
          'source_comparisons': 'unrun', 'product_acceptance': 'unrun'}
(args.output / 'controller-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['passed', 'terminal_exit_code', 'process_id', 'samples']}), flush=True)
raise SystemExit(0 if passed else 1)

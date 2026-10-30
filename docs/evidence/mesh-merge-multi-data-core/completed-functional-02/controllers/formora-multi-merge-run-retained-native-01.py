"""Run retained native save, one-shot RNG and exact Euler checks."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
DRIVERS = Path('/private/tmp/formora-multi-merge-retained-native-drivers-01')
OUT = Path('/private/tmp/formora-multi-merge-retained-native-gates-01')
OUT.mkdir(exist_ok=False)
BINARY = Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected = '64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019'
assert sha(BINARY) == expected
assert sha('/Applications/Blender.app/Contents/MacOS/Blender') == 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
tasks = [
    ('failed-save19', 'regenerate-failed-save-proof-01.py', '/private/tmp/formora-multi-merge-retained-failed-save-01/report.json', 'native_calls', 19),
    ('rng48', 'regenerate-retained-rng-one-shot-01.py', '/private/tmp/formora-multi-merge-retained-rng-one-shot-01/report.json', 'checks', 48),
    ('euler6', 'regenerate-retained-source-oracle-01.py', '/private/tmp/formora-multi-merge-retained-source-oracle-01/report.json', 'cases', 6)]
records = []
for name, filename, result, field, count in tasks:
    command = [sys.executable, str(DRIVERS/filename)]
    with (OUT/(name+'.stdout')).open('x') as so, (OUT/(name+'.stderr')).open('x') as se:
        child = subprocess.Popen(command, cwd=ROOT, env=os.environ, stdout=so, stderr=se)
        with (OUT/(name+'-started.json')).open('x') as f:
            json.dump({'process_id': child.pid, 'command': command}, f)
            f.write('\n')
        code = child.wait()
    path = Path(result)
    data = json.loads(path.read_text()) if path.exists() else None
    actual = None if data is None else (len(data[field]) if isinstance(data[field], list) else data[field])
    passed = code == 0 and data is not None and data['passed'] is True and actual == count and data['binary_sha256'] == expected
    row = {'name': name, 'command': command, 'process_id': child.pid, 'terminal_exit_code': code,
           'passed': passed, 'expected_checks': count, 'actual_checks': actual,
           'report': str(path), 'report_sha256': sha(path) if path.exists() else None,
           'driver_sha256': sha(DRIVERS/filename)}
    records.append(row)
    with (OUT/(name+'-terminal.json')).open('x') as f:
        json.dump(row, f, indent=2)
        f.write('\n')
    (OUT/'progress.json').write_text(json.dumps(records, indent=2)+'\n')
    print(json.dumps({key: row[key] for key in ['name', 'terminal_exit_code', 'passed', 'actual_checks']}), flush=True)
assert sha(BINARY) == expected
with (OUT/'report.json').open('x') as f:
    json.dump({'passed': len(records) == 3 and all(r['passed'] for r in records), 'records': records,
               'binary_sha256': expected, 'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}, f, indent=2)
    f.write('\n')
raise SystemExit(0 if all(r['passed'] for r in records) else 1)

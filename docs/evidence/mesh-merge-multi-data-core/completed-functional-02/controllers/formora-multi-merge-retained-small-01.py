"""Run the original seven isolation and five lifecycle suites on the current binary."""
from pathlib import Path
import copy
import difflib
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
BASE = ROOT/'docs/evidence/mesh-merge-core/continuation'
OUT = Path('/private/tmp/formora-multi-merge-retained-small-gates-01')
OUT.mkdir(exist_ok=False)
DRIVERS = Path('/private/tmp/formora-multi-merge-retained-small-drivers-01')
DRIVERS.mkdir(exist_ok=False)
BINARY = Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected = '64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019'
assert sha(BINARY) == expected
config = BASE/'regenerate-retained-small-gates-config-01.json'
original = json.loads(config.read_text())
source = BASE/'regenerate-retained-rng-isolation-01.py'
old = source.read_text()
new = old
replacements = [('/private/tmp/formora-mesh-merge-sparse', str(ROOT)),
    ('/private/tmp/formora-merge-regen-target-actual185/debug/formora', str(BINARY)),
    ('/private/tmp/formora-merge-regen-retained-isolation-01/rng', '/private/tmp/formora-multi-merge-retained-isolation-01/rng')]
for before, after in replacements:
    assert before in new
    new = new.replace(before, after)
restored = new
for before, after in reversed(replacements):
    restored = restored.replace(after, before)
assert restored == old
rng_driver = DRIVERS/'retained-rng-isolation.py'
with rng_driver.open('x') as f:
    f.write(new)
with (DRIVERS/'bindings.json').open('x') as f:
    json.dump({'source': str(source), 'source_sha256': sha(source), 'copy': str(rng_driver),
        'copy_sha256': sha(rng_driver), 'reverse_mapping_recovers_exact_original': True,
        'only_path_bindings_changed': replacements,
        'diff': list(difflib.unified_diff(old.splitlines(True), new.splitlines(True)))}, f, indent=2)
    f.write('\n')
rows = copy.deepcopy(original)
for row in rows:
    row['original_command'] = row['command'][:]
    row['command'] = [argument.replace('/private/tmp/formora-mesh-merge-sparse', str(ROOT))
        .replace('/private/tmp/formora-merge-regen-target-actual185/debug/formora', str(BINARY))
        .replace('/private/tmp/formora-merge-regen-retained-', '/private/tmp/formora-multi-merge-retained-')
        for argument in row['command']]
    row['command'][0] = sys.executable
    row['report'] = row['report'].replace('/private/tmp/formora-merge-regen-retained-',
                                         '/private/tmp/formora-multi-merge-retained-')
    if row['name'] == 'rng':
        row['command'][1] = str(rng_driver)
with (OUT/'commands.json').open('x') as f:
    json.dump({'original_config': str(config), 'original_config_sha256': sha(config),
        'rows': rows, 'assertions_counts_limits_and_inputs': 'unchanged'}, f, indent=2)
    f.write('\n')
Path('/private/tmp/formora-multi-merge-retained-local-01').mkdir(exist_ok=False)
paths = [p for name in ['src', 'tests', 'tools', 'docs/contracts'] for p in (ROOT/name).rglob('*')
         if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
records = []
for row in rows:
    name = row['kind']+'-'+row['name']
    command = row['command']
    with (OUT/(name+'.stdout')).open('x') as stdout, (OUT/(name+'.stderr')).open('x') as stderr:
        child = subprocess.Popen(command, cwd=ROOT, env=os.environ, stdout=stdout, stderr=stderr)
        with (OUT/(name+'-started.json')).open('x') as f:
            json.dump({'process_id': child.pid, 'command': command}, f)
            f.write('\n')
        code = child.wait()
    report_path = Path(row['report'])
    data = json.loads(report_path.read_text()) if report_path.exists() else None
    record = {**row, 'process_id': child.pid, 'terminal_exit_code': code,
        'passed': code == 0 and data is not None and data['passed'],
        'report_sha256': sha(report_path) if report_path.exists() else None,
        'driver_sha256': sha(command[1])}
    records.append(record)
    with (OUT/(name+'-terminal.json')).open('x') as f:
        json.dump(record, f, indent=2)
        f.write('\n')
    (OUT/'progress.json').write_text(json.dumps(records, indent=2)+'\n')
    print(json.dumps({key: record[key] for key in ['kind', 'name', 'terminal_exit_code', 'passed']}), flush=True)
unchanged = sha(BINARY) == expected and hashes == {str(p.relative_to(ROOT)): sha(p) for p in paths}
result = {'passed': unchanged and len(records) == 12 and all(r['passed'] for r in records),
    'suites': len(records), 'records': records, 'binary_sha256': expected,
    'input_hashes': hashes, 'inputs_unchanged': unchanged,
    'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}
with (OUT/'report.json').open('x') as f:
    json.dump(result, f, indent=2)
    f.write('\n')
raise SystemExit(0 if result['passed'] else 1)

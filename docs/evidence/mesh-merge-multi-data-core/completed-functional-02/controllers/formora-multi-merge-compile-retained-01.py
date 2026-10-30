"""Compile the five frozen retained timing drivers; do not run timing samples."""
from pathlib import Path
import copy
import hashlib
import json
import subprocess

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
OUT = Path('/private/tmp/formora-multi-merge-retained-compile-01')
OUT.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
library = Path('/private/tmp/formora-multi-merge-target-actual185/release/libformora.rlib')
assert sha(library) == '9b6e850f4cbe2e348d9aea69c48ed0f6e5ba8b0a94f6325eed67f2844e568d40'
config = ROOT/'docs/evidence/mesh-merge-core/continuation/regenerate-retained-compile-config-01.json'
original = json.loads(config.read_text())
rows = copy.deepcopy(original)
bindings = [('/private/tmp/formora-mesh-merge-sparse/', str(ROOT)+'/'),
            ('/private/tmp/formora-merge-regen-target-actual185/', '/private/tmp/formora-multi-merge-target-actual185/'),
            ('/private/tmp/formora-merge-regen-retained-', '/private/tmp/formora-multi-merge-retained-')]
for row in rows:
    row['original_command'] = row['command'][:]
    row['command'] = [argument for argument in row['command']]
    for before, after in bindings:
        row['command'] = [argument.replace(before, after) for argument in row['command']]
    assert sha(Path(row['command'][5])) == row['driver_source_sha256']
with (OUT/'frozen-commands.json').open('x') as f:
    json.dump({'original_config': str(config), 'original_config_sha256': sha(config),
               'only_path_bindings_changed': bindings, 'rows': rows}, f, indent=2)
report = {'passed': False, 'library_sha256': sha(library), 'drivers': [], 'timing_samples_executed': 0,
          'performance_acceptance': 'unrun', 'source_drivers_changed': False}
for row in rows:
    command = row['command']
    assert not Path(command[7]).exists(), command[7]
    with (OUT/(row['name']+'.stdout')).open('x') as so, (OUT/(row['name']+'.stderr')).open('x') as se:
        child = subprocess.Popen(command, cwd=ROOT, stdout=so, stderr=se)
        code = child.wait()
    value = {**row, 'process_id': child.pid, 'terminal_exit_code': code}
    if code == 0:
        value['driver_sha256'] = sha(Path(command[7]))
    report['drivers'].append(value)
    print(json.dumps({'driver': row['name'], 'compile_exit': code}), flush=True)
assert sha(library) == report['library_sha256']
report['passed'] = all(r['terminal_exit_code'] == 0 for r in report['drivers'])
with (OUT/'report.json').open('x') as f:
    json.dump(report, f, indent=2)
    f.write('\n')
raise SystemExit(0 if report['passed'] else 1)

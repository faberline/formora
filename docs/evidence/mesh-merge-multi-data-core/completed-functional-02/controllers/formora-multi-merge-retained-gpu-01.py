"""Repeat the five retained Metal suites with unchanged source assertions."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
BASE = ROOT/'docs/evidence/mesh-merge-core/continuation'
OUT = Path('/private/tmp/formora-multi-merge-retained-gpu-01')
OUT.mkdir(exist_ok=False)
DRIVERS = Path('/private/tmp/formora-multi-merge-retained-gpu-drivers-01')
DRIVERS.mkdir(exist_ok=False)
BINARY = Path('/private/tmp/formora-object-state-build-02/formora-preview')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected = '518d5cb60791ccbd40c972e875807d836120aceadb4183c95e0647147bc00b65'
assert sha(BINARY) == expected
bindings = []
for filename in ['regenerate-gpu-proof-01.py', 'regenerate-retained-gpu-rng-01.py', 'regenerate-retained-gpu-mirror-01.py']:
    source = BASE/filename
    old = source.read_text()
    new = old
    replacements = [("ROOT=Path(__file__).resolve().parents[4]", "ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')"),
        ('/private/tmp/formora-mesh-merge-sparse', str(ROOT)),
        ('/private/tmp/formora-merge-regen-allfeatures-actual185/debug/formora', str(BINARY)),
        ('/private/tmp/formora-merge-regen-retained-gpu-01', str(OUT)),
        ('/private/tmp/formora-merge-regen-gpu-01', '/private/tmp/formora-multi-merge-retained-merge-gpu-01'),
        ('5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d', 'bd13f3d424f2649b4b25c16305c4e5b0eb7f8542')]
    applied = []
    for before, after in replacements:
        if before in new:
            new = new.replace(before, after)
            applied.append((before, after))
    restored = new
    for before, after in reversed(applied):
        restored = restored.replace(after, before)
    assert restored == old
    target = DRIVERS/filename
    with target.open('x') as f:
        f.write(new)
    bindings.append({'source': str(source), 'source_sha256': sha(source), 'copy': str(target),
        'copy_sha256': sha(target), 'only_path_head_bindings_changed': applied,
        'reverse_mapping_recovers_exact_original': True,
        'diff': list(difflib.unified_diff(old.splitlines(True), new.splitlines(True)))})
with (DRIVERS/'bindings.json').open('x') as f:
    json.dump({'drivers': bindings, 'all_assertions_counts_pixel_limits_and_inputs': 'unchanged'}, f, indent=2)
    f.write('\n')
tasks = [
    ('merge', DRIVERS/'regenerate-gpu-proof-01.py', [], Path('/private/tmp/formora-multi-merge-retained-merge-gpu-01/report.json')),
    ('delta', ROOT/'docs/evidence/snap-delta-core/gpu-driver.py', [str(BINARY), str(OUT/'delta')], OUT/'delta/manifest.json'),
    ('raw', ROOT/'docs/evidence/snap-rotation-core/gpu-driver.py', [str(BINARY), str(OUT/'raw')], OUT/'raw/manifest.json'),
    ('rng', DRIVERS/'regenerate-retained-gpu-rng-01.py', [], OUT/'rng/manifest.json'),
    ('mirror', DRIVERS/'regenerate-retained-gpu-mirror-01.py', [], OUT/'mirror/manifest.json')]
rows = []
for name, driver, args, report_path in tasks:
    command = [sys.executable, str(driver), *args]
    with (OUT/(name+'.stdout')).open('x') as so, (OUT/(name+'.stderr')).open('x') as se:
        child = subprocess.Popen(command, cwd=ROOT, env=os.environ, stdout=so, stderr=se)
        with (OUT/(name+'-started.json')).open('x') as f:
            json.dump({'process_id': child.pid, 'command': command}, f)
            f.write('\n')
        code = child.wait()
    data = json.loads(report_path.read_text()) if report_path.exists() else None
    passed = code == 0 and data is not None and data['passed'] is True
    row = {'name': name, 'command': command, 'process_id': child.pid, 'terminal_exit_code': code,
        'passed': passed, 'report': str(report_path), 'report_sha256': sha(report_path) if report_path.exists() else None,
        'driver_sha256': sha(driver)}
    rows.append(row)
    with (OUT/(name+'-terminal.json')).open('x') as f:
        json.dump(row, f, indent=2)
        f.write('\n')
    (OUT/'progress.json').write_text(json.dumps(rows, indent=2)+'\n')
    print(json.dumps({key: row[key] for key in ['name', 'terminal_exit_code', 'passed']}), flush=True)
assert sha(BINARY) == expected
with (OUT/'report.json').open('x') as f:
    json.dump({'passed': len(rows) == 5 and all(r['passed'] for r in rows), 'suites': 5, 'records': rows,
        'binary_sha256': expected, 'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}, f, indent=2)
    f.write('\n')
raise SystemExit(0 if all(r['passed'] for r in rows) else 1)

"""Change only exclusive output bindings after sandbox-denied host probes."""
from pathlib import Path
import ast
import difflib
import hashlib
import json

TIMING=Path('/private/tmp/formora-multi-merge-timing-runners-01')
SOURCE=Path('/private/tmp/formora-multi-merge-source-runners-01')
OUT=Path('/private/tmp/formora-multi-merge-timing-recovery-drivers-02');OUT.mkdir(exist_ok=False)
rows=[]
def copy(path,pairs):
    original=path.read_text();actual=original
    for old,new in pairs:
        assert old in actual
        actual=actual.replace(old,new)
    reverse=actual
    for old,new in reversed(pairs):reverse=reverse.replace(new,old)
    assert reverse==original
    asserts=lambda s:[ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Assert)]
    assert asserts(original)==asserts(actual)
    target=OUT/path.name
    with target.open('x') as f:f.write(actual)
    rows.append({'original':str(path),'actual':str(target),'original_sha256':hashlib.sha256(original.encode()).hexdigest(),
        'actual_sha256':hashlib.sha256(actual.encode()).hexdigest(),'bindings':pairs,'assertions_unchanged':True,
        'reverse_bindings_exact':True,'diff':''.join(difflib.unified_diff(original.splitlines(True),actual.splitlines(True)))})
bindings=[]
for name in ['90','rotation','delta']:
    pair=(f'formora-multi-merge-retained-{name}-01',f'formora-multi-merge-retained-{name}-02')
    bindings.append(pair);copy(TIMING/f'regenerate-retained-run-{name}-01.py',[pair])
copy(SOURCE/'regenerate-retained-compare-all-sources-01.py',bindings)
copy(SOURCE/'retained-source-relocation-01.py',[])
with (OUT/'bindings.json').open('x') as f:json.dump({'records':rows,'workloads_clocks_limits_unchanged':True,
    'first_sandbox_denied_attempts_preserved':True,'already_passed_39_samples_not_repeated':True,
    'new_timing_samples_executed':0,'product_acceptance':'unrun'},f,indent=2);f.write('\n')
print(json.dumps({'prepared':len(rows),'assertions_unchanged':True,'completed_39_not_repeated':True}))

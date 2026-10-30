"""Bind capacity code/assets, fixed budgets and actual M1 Max hardware."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from merge_distance_source_seal import ROOT, BINARY, LIMITS, verify as verify_functional
from check_merge_distance_capacity_inputs import verify as verify_inputs


FUNCTIONAL = ROOT/'baseline/fixtures/mesh-merge-distance-complete-02.json'
FUNCTIONAL_SEAL = ROOT/'baseline/fixtures/mesh-merge-distance-source-seal-01.json'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def hardware():
    cpu = subprocess.check_output(['/usr/sbin/sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
    memory = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.memsize'], text=True))
    result = {'cpu': cpu, 'memory_bytes': memory, 'machine': platform.machine(),
              'system': platform.system(), 'macos_version': platform.mac_ver()[0]}
    assert cpu == 'Apple M1 Max' and memory == 68719476736, 'fixed capacity hardware'
    assert result['machine'] == 'arm64' and result['system'] == 'Darwin', 'native capacity platform'
    return result


def input_paths(suite_path):
    suite = json.loads(suite_path.read_text())
    functional = json.loads(FUNCTIONAL_SEAL.read_text())
    paths = {ROOT/name for name in functional['input_hashes']}
    paths.update([FUNCTIONAL_SEAL, suite_path.resolve(), suite_path.parent/suite['capacity_assets']['file'],
                  ROOT/'docs/contracts/mesh-merge-distance-capacity.md'])
    pending = [ROOT/'tools'/name for name in ['blender_merge_distance_capacity_reference.py',
               'merge_distance_capacity_seal.py', 'launch_merge_distance_capacity_reference.py',
               'compare_merge_distance_capacity_reference.py', 'check_merge_distance_capacity_reference.py']]
    scanned = set()
    while pending:
        path = pending.pop().resolve()
        if path in scanned: continue
        scanned.add(path); paths.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in modules:
                local = ROOT/'tools'/(name.split('.')[0]+'.py')
                if local.is_file() and local.resolve() not in scanned: pending.append(local)
    return sorted(paths)


def verify(suite_path, seal_path, require_host=False):
    verify_functional(FUNCTIONAL, FUNCTIONAL_SEAL)
    value = json.loads(seal_path.read_text()); suite = json.loads(suite_path.read_text())
    assert value['scope'] == suite['scope'] == 'complete_distance_merge_class_a_capacity_registry', 'capacity seal scope'
    assert value['suite_sha256'] == digest(suite_path) and value['cases'] == len(suite['runs']) == 192, 'capacity seal registry'
    assert value['binary_sha256'] == BINARY and value['product_limits'] == LIMITS, 'capacity fixed identity/limits'
    assert value['functional_seal_sha256'] == digest(FUNCTIONAL_SEAL), 'capacity functional dependency'
    assert value['rust_distance_implementation_at_seal'] == value['complete_capacity_execution_at_seal'] == 'unrun', 'capacity before-code seal'
    assert value['hardware']['cpu'] == 'Apple M1 Max' and value['hardware']['memory_bytes'] == 68719476736, 'capacity recorded hardware'
    expected = {path.relative_to(ROOT).as_posix(): digest(path) for path in input_paths(suite_path)}
    assert value['input_hashes'] == expected, 'capacity code/input seal'
    subprocess.run(['git', 'merge-base', '--is-ancestor', value['code_commit'], 'HEAD'], cwd=ROOT, check=True, capture_output=True)
    for name, sha in expected.items():
        raw = subprocess.check_output(['git', 'show', value['code_commit']+':'+name], cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest() == sha, 'capacity committed input '+name
    if require_host: assert hardware() == value['hardware'], 'capacity actual hardware differs'
    return value


def create(suite_path, output):
    report = verify_inputs(suite_path)
    assert report['capacity_input_checks_passed'] and report['cases'] == 192
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in input_paths(suite_path)}
    for name, sha in hashes.items():
        raw = subprocess.check_output(['git', 'show', commit+':'+name], cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest() == sha, 'commit capacity inputs/code before sealing'
    value = {'schema_version': 1, 'scope': 'complete_distance_merge_class_a_capacity_registry',
             'code_commit': commit, 'created_utc': datetime.now(timezone.utc).isoformat(),
             'binary_sha256': BINARY, 'functional_seal_sha256': digest(FUNCTIONAL_SEAL),
             'suite_sha256': digest(suite_path), 'cases': 192, 'product_limits': LIMITS,
             'hardware': hardware(), 'input_hashes': hashes, 'rust_distance_implementation_at_seal': 'unrun',
             'complete_capacity_execution_at_seal': 'unrun', 'product_acceptance': 'unrun'}
    with output.open('x') as stream: json.dump(value, stream, indent=2); stream.write('\n')
    verify(suite_path, output, True)
    return {'sealed_capacity_cases': 192, 'sealed_files': len(hashes), 'seal_sha256': digest(output), 'hardware': value['hardware']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(create(args.suite.resolve(), args.output.resolve())))

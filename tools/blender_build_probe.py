"""Run inside factory-startup Blender. Capture version evidence, not feature acceptance."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import bpy


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


lock = json.loads(Path(os.environ['FORMORA_REFERENCE_LOCK']).read_bytes())
pin = next(p for p in lock['products'] if p['id'] == 'blender')
version = '.'.join(map(str, bpy.app.version))
build = bpy.app.build_hash.decode()
if version != pin['version'] or build != pin['reference_build']['id']:
    raise ValueError('Blender runtime version or build differs from the frozen pin')
output = Path(os.environ['FORMORA_REFERENCE_OUTPUT'])
if output.exists():
    raise ValueError('version evidence must not be overwritten')
executable = Path(bpy.app.binary_path)
report = {
    'schema_version': 1, 'product': 'blender', 'version': version,
    'documentation_version': pin['documentation_version'], 'build_id': build,
    'version_probe_status': 'passed', 'runtime_version': bpy.app.version_string,
    'entry_executable': executable.name,
    'files': {executable.name: {'sha256': digest(executable), 'bytes': executable.stat().st_size}},
    'build': {name: getattr(bpy.app, name).decode() for name in
              ['build_branch', 'build_date', 'build_time', 'build_platform', 'build_type']},
    'platform': platform.platform(), 'architecture': platform.machine(), 'python_version': sys.version,
    'probe_sha256': digest(Path(__file__)),
    'feature_tests': 'unrun', 'gpu_tests': 'unrun', 'product_acceptance': 'unrun',
}
output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
print('FORMORA_REFERENCE_VERSION '+version+' '+build)

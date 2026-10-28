"""Run inside Unreal's NullRHI Python commandlet. Capture version evidence only."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import unreal


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


lock = json.loads(Path(os.environ['FORMORA_REFERENCE_LOCK']).read_bytes())
pin = next(p for p in lock['products'] if p['id'] == 'unreal')
root = Path(os.environ['FORMORA_REFERENCE_ENGINE']).resolve()
entry = Path(os.environ['FORMORA_REFERENCE_ENTRY']).resolve()
entry_name = str(entry.relative_to(root))
output = Path(os.environ['FORMORA_REFERENCE_OUTPUT'])
version = unreal.SystemLibrary.get_engine_version()
if version != pin['reference_build']['id']:
    raise ValueError('Unreal runtime version or build differs from the frozen pin')
if output.exists():
    raise ValueError('version evidence must not be overwritten')
build_path = root/'Build/Build.version'
build = json.loads(build_path.read_bytes())
if '.'.join(str(build[k]) for k in ['MajorVersion', 'MinorVersion', 'PatchVersion']) != pin['version']:
    raise ValueError('installed build metadata differs from the frozen product version')
command = unreal.SystemLibrary.get_command_line().lower()
if '-nullrhi' not in command or '-run=pythonscript' not in command:
    raise ValueError('version probe requires the non-rendering Python commandlet')
paths = [build_path, entry]
for path in [entry.parent/'UnrealEditor.version', entry.parent/'UnrealEditor.app/Contents/MacOS/UnrealEditor']:
    if path.is_file():
        paths.append(path)
files = {str(p.relative_to(root)): {'sha256': digest(p), 'bytes': p.stat().st_size} for p in paths}
report = {
    'schema_version': 1, 'product': 'unreal', 'version': pin['version'],
    'documentation_version': pin['documentation_version'], 'build_id': version,
    'version_probe_status': 'passed', 'runtime_version': version, 'build': build,
    'entry_executable': entry_name, 'files': files,
    'platform': platform.platform(), 'architecture': platform.machine(), 'python_version': sys.version,
    'probe_sha256': digest(Path(__file__)), 'render_backend': 'NullRHI',
    'feature_tests': 'unrun', 'gpu_tests': 'unrun', 'product_acceptance': 'unrun',
}
output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
print('FORMORA_REFERENCE_VERSION '+version)

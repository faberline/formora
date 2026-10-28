#!/usr/bin/env python3
"""Capture a pinned upstream version in a new directory. This is not a product test."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPOSITORY = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product', choices=['blender', 'unreal'], required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--engine-root', type=Path, help='Unreal Engine directory')
    parser.add_argument('--lock', type=Path, default=REPOSITORY/'baseline/lock.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; evidence must not be overwritten')
    if not args.executable.is_file():
        parser.error('reference executable does not exist')
    if args.product == 'unreal' and (args.engine_root is None or not (args.engine_root/'Build/Build.version').is_file()):
        parser.error('--engine-root must point to the installed Unreal Engine directory')
    pin = next(p for p in json.loads(args.lock.read_bytes())['products'] if p['id'] == args.product)
    if not pin.get('reference_build'):
        parser.error('the lock must declare the expected reference build before probing')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='formora-version-probe-', dir=args.output.parent)).resolve()
    report_path = stage/'report.json'
    env = dict(os.environ)
    env.update({'FORMORA_REFERENCE_LOCK': str(args.lock.resolve()),
                'FORMORA_REFERENCE_OUTPUT': str(report_path)})
    adapter = REPOSITORY/f'tools/{args.product}_build_probe.py'
    if args.product == 'blender':
        command = [str(args.executable.resolve()), '--background', '--factory-startup',
                   '--disable-autoexec', '--python-exit-code', '1', '--python', str(adapter)]
    else:
        project = stage/'project'
        (project/'Config').mkdir(parents=True)
        write_json(project/'FormoraReference.uproject', {
            'FileVersion': 3, 'EngineAssociation': pin['documentation_version'],
            'Description': 'Formora version probe; not a feature test',
            'DisableEnginePluginsByDefault': True,
            'Plugins': [{'Name': 'PythonScriptPlugin', 'Enabled': True}],
        })
        (project/'Config/DefaultEditor.ini').write_text(
            '[/Script/PythonScriptPlugin.PythonScriptPluginSettings]\n'
            'bIsolateInterpreterEnvironment=True\nbDeveloperMode=False\n'
            '!StartupScripts=ClearArray\n!AdditionalPaths=ClearArray\n', encoding='utf-8')
        env.pop('UE_PYTHONPATH', None)
        env.update({'FORMORA_REFERENCE_ENGINE': str(args.engine_root.resolve()),
                    'FORMORA_REFERENCE_ENTRY': str(args.executable.resolve()),
                    'UE-LocalDataCachePath': str(stage/'ddc'), 'UE-SharedDataCachePath': 'None'})
        command = [str(args.executable.resolve()), str(project/'FormoraReference.uproject'),
                   '-run=pythonscript', '-script='+str(adapter), '-unattended', '-nullrhi',
                   '-nosound', '-nosplash', '-stdout', '-FullStdOutLogOutput', '-notraceserver',
                   '-NoSharedDDC', '-DDC=NoZenLocalFallback', '-LocalDataCachePath='+str(stage/'ddc'),
                   '-UserDir='+str(stage/'user')]
    write_json(stage/'command.json', command)
    with (stage/'stdout.log').open('wb') as log:
        process = subprocess.Popen(command, cwd=stage, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(f'{args.product} version probe started: {process.pid}', flush=True)
        status = process.wait()
    write_json(stage/'process.json', {'exit_code': status, 'adapter_sha256': digest(adapter),
                                    'stdout_sha256': digest(stage/'stdout.log')})
    if status != 0 or not report_path.is_file():
        raise RuntimeError(f'version capture failed (exit {status}); diagnostic files: {stage}')
    report = json.loads(report_path.read_bytes())
    if (report.get('version_probe_status') != 'passed' or report['version'] != pin['version']
            or report['build_id'] != pin['reference_build']['id']):
        raise RuntimeError(f'version evidence differs from the pin; diagnostic files: {stage}')
    stage.rename(args.output)
    print(json.dumps({'output': str(args.output.resolve()), 'version': report['version'],
                      'build_id': report['build_id'], 'product_acceptance': 'unrun'}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, StopIteration) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)

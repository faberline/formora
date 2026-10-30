"""Reject retained forged capacity records without executing a native operator."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil

from check_merge_distance_capacity_reference import check


def controls(suite, seal, native, output, case_ids):
    genuine = check(suite, seal, native, case_ids)
    assert genuine['source_capture_checks_passed'], 'genuine capacity capture must pass first'
    output.mkdir(exist_ok=False)
    rows = []
    sha = lambda raw: hashlib.sha256(raw).hexdigest()

    def reject(name, reason, envelope=None, mutate=None, missing=None, checkpoint=False, admitted_cases=None):
        target = output/name
        shutil.copytree(native, target)
        manifest_path = target/'capture/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        if missing:
            path = target/missing
            path.rename(path.with_suffix(path.suffix+'.retained'))
        if envelope:
            filename, change = envelope
            path = target/filename; value = json.loads(path.read_text()); change(value)
            path.write_text(json.dumps(value, indent=2)+'\n')
        if mutate:
            row = manifest['runs'][0]; path = target/'capture'/row['file']
            value = json.loads(gzip.decompress(path.read_bytes())); mutate(value)
            if checkpoint:
                before = {'run': value['run'], 'scene_spec': value['scene_spec'],
                          'phase': 'creation', 'before': value['before']}
                raw = (json.dumps(before, indent=2, allow_nan=False)+'\n').encode()
                stored = gzip.compress(raw, mtime=0)
                (target/'capture'/value['checkpoint']['file']).write_bytes(stored)
                value['checkpoint'].update(sha256=sha(stored), raw_sha256=sha(raw), raw_bytes=len(raw))
            raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode(); stored = gzip.compress(raw, mtime=0)
            path.write_bytes(stored); row.update(sha256=sha(stored), raw_sha256=sha(raw), raw_bytes=len(raw))
            manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
        try:
            check(suite, seal, target, case_ids if admitted_cases is None else admitted_cases)
        except (AssertionError, KeyError, FileNotFoundError) as error:
            message = str(error)
        else:
            raise AssertionError('forged capacity capture accepted: '+name)
        assert reason in message, (name, 'wrong rejection', reason, message)
        rows.append({'control': name, 'rejected': True, 'expected_check': reason,
                     'error': message, 'retained_forged_capture': str(target)})
        (output/(name+'.result.json')).write_text(json.dumps(rows[-1], indent=2)+'\n')

    if case_ids:
        reject('diagnostic_as_complete', 'capacity complete/diagnostic scope', admitted_cases=[])
    reject('missing_case', 'capacity case membership', envelope=('capture/manifest.json', lambda v:v['runs'].pop()))
    reject('duplicate_case', 'capacity case membership', envelope=('capture/manifest.json', lambda v:v['runs'].append(copy.deepcopy(v['runs'][0]))))
    reject('wrong_binary', 'source binary', envelope=('capture/manifest.json', lambda v:v.update(binary_sha256='0'*64)))
    for name, value, reason in [('failed_terminal', 1, 'native terminal failed'),
                                ('boolean_terminal', False, 'native terminal type'),
                                ('float_terminal', 0., 'native terminal type')]:
        reject(name, reason, envelope=('terminal.json', lambda v, value=value:v.update(terminal_exit_code=value)))
    reject('missing_terminal', 'terminal.json', missing='terminal.json')
    reject('timed_out_terminal', 'native terminal failed', envelope=('terminal.json', lambda v:v.update(timed_out=True)))
    reject('wrong_pid', 'native PID binding', envelope=('terminal.json', lambda v:v.update(process_id=1)))
    reject('wrong_log', 'native log identity', envelope=('terminal.json', lambda v:v.update(stdout_sha256='0'*64)))
    reject('wrong_suite', 'capacity parent input', envelope=('started.json', lambda v:v.update(suite_sha256='0'*64)))
    reject('wrong_seal', 'capacity parent seal', envelope=('terminal.json', lambda v:v.update(capacity_seal_sha256='0'*64)))
    reject('wrong_hardware', 'capacity captured hardware', envelope=('capture/manifest.json', lambda v:v['hardware'].update(cpu='unknown')))
    reject('wrong_scope', 'capacity complete/diagnostic scope', envelope=('capture/manifest.json', lambda v:v.update(scope='pretend_complete')))
    reject('missing_input', 'capacity input registry', envelope=('capture/manifest.json', lambda v:v['input_hashes'].pop(next(iter(v['input_hashes'])))))
    reject('wrong_run', 'capacity run', mutate=lambda v:v['run']['parameters'].update(threshold=.5))
    reject('authored_answer_leak', 'capacity authored scene', mutate=lambda v:v['scene_spec'].update(source_answer={}))
    reject('wrong_checkpoint_digest', 'capacity checkpoint identity', mutate=lambda v:v['checkpoint'].update(sha256='0'*64))
    reject('failed_operation', 'capacity operation status', mutate=lambda v:v['result'].update(status=['CANCELLED']))
    reject('failed_save', 'capacity native save/reopen status', mutate=lambda v:v.update(save_status=['CANCELLED']))
    reject('failed_reopen', 'capacity native save/reopen status', mutate=lambda v:v.update(reopen_status=['CANCELLED']))
    reject('wrong_native_file', 'capacity native file digest', mutate=lambda v:v.update(native_file_sha256='0'*64))
    reject('lost_initial_zero_weight', 'a/groups/weights', checkpoint=True,
           mutate=lambda v:v['before']['meshes']['a']['groups']['weights']['v000000'].pop('pin'))
    reject('wrong_output_position', 'source-cluster/vertices/a', mutate=lambda v:v['after']['meshes']['a']['geometry']['vertices']['v000000'].__setitem__(0, 99.))
    def change_reloaded_integer(value):
        for name in ['a', 'alias']:
            layer = value['reloaded']['meshes'][name]['integer_attributes']['VERT']['vertices_signed']
            layer['v000000'] += 1
    reject('lost_reloaded_integer', 'capacity complete reload/meshes/a/integer_attributes',
           mutate=change_reloaded_integer)
    reject('boolean_clock', 'capacity clock type', mutate=lambda v:v['native_clocks'].update(before_ns=True))
    reject('reversed_clock', 'capacity clock order', mutate=lambda v:v['native_clocks'].update(pipeline_after_ns=1))
    reject('forged_core_ms', 'capacity core clock', mutate=lambda v:v['native_clocks'].update(core_ms=0.))
    reject('forged_pipeline_ms', 'capacity pipeline clock', mutate=lambda v:v['native_clocks'].update(pipeline_ms=0.))
    reject('validation_removed', 'capacity validation/timing scope', mutate=lambda v:v['native_clocks'].update(full_validation_inside_clock=False))
    reject('source_claimed_as_rust', 'capacity validation/timing scope', mutate=lambda v:v['native_clocks'].update(is_rust_product_timing=True))
    reject('raised_budget', 'capacity budget observations', mutate=lambda v:v['native_budget_observations'].update(core_limit_ms=999999))
    reject('false_source_pass', 'capacity budget observations', mutate=lambda v:v['native_budget_observations'].update(native_core_within_product_budget=True))
    result = {'genuine_capture_checks_passed': True, 'controls_rejected': len(rows), 'controls': rows,
              'suite_sha256': sha(suite.read_bytes()), 'capacity_seal_sha256': sha(seal.read_bytes()),
              'genuine_manifest_sha256': sha((native/'capture/manifest.json').read_bytes()),
              'control_script_sha256': sha(Path(__file__).read_bytes()),
              'forged_native_operations_executed': False, 'complete_source_gate': 'unrun',
              'rust_product_timing': 'unrun', 'product_acceptance': 'unrun'}
    (output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    return {key:value for key,value in result.items() if key != 'controls'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['suite', 'capacity-seal', 'native', 'output']: parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--case', action='append', default=[])
    args = parser.parse_args()
    print(json.dumps(controls(args.suite.resolve(), args.capacity_seal.resolve(), args.native.resolve(), args.output.resolve(), args.case)))

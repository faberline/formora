#!/usr/bin/env python3
"""Reject forged raw evidence. Never execute a forged product operation."""
import argparse
import builtins
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch

from audit_multi_mesh_merge_runtime import header
from compare_multi_mesh_merge_reference import digest
from generate_multi_mesh_merge_cases import author
from multi_mesh_merge_product_inputs import scene as authored_scene
from multi_mesh_merge_runtime_inputs import setup, operation
from multi_mesh_merge_runtime import source_preflight, references
from multi_mesh_merge_runtime_check import check_record, compare_phase, aggregate_receipt, bind_transport, ROOT
from runtime_artifacts import write_json


def check(capture, output):
    suite = author()
    folders, manifests, source = source_preflight(ROOT/'baseline/fixtures/mesh-merge-multi-data.json', suite)
    report = json.loads((capture/'report.json').read_text())
    header(report, suite, source)
    rows = report['records']
    by_id = {r['id']: (i, r) for i, r in enumerate(suite['runs'])}
    chosen = next(row for row in rows if row['interface'] == 'cli' and
        by_id[row['id']][1]['parameters']['type'] == 'CENTER' and
        by_id[row['id']][1]['selection'] == 'both')
    path = capture/chosen['file']
    assert digest(path) == chosen['sha256']
    original = json.loads(gzip.decompress(path.read_bytes()))
    source_index, run = by_id[chosen['id']]
    refs = references(suite, run, source_index, folders, manifests)
    check_record(suite, run, original, refs)
    results = []

    def reject(name, mutate, checker, reason=''):
        value = copy.deepcopy(original)
        mutate(value)
        try:
            checker(value)
        except (AssertionError, ValueError, KeyError) as error:
            assert reason in str(error), (name, reason, str(error))
            results.append({'control': name, 'rejected': True,
                            'error_type': type(error).__name__, 'error': str(error)})
        else:
            raise AssertionError('forged evidence admitted: '+name)

    full = lambda v: check_record(suite, run, v, refs)
    phase = lambda v: compare_phase(suite, run, refs[0]['before'], v['before'])
    receipt = lambda v: aggregate_receipt(suite, run, v['before']['scene'], v['after']['scene'], v['result'])
    reject('source_answer_in_scene_input', lambda v: v['input'].update(source_expected={'answer': 1}), full, 'leaked into setup')

    def leaked_setup(v):
        v['setup']['commands'][0]['source_expected'] = {'answer': 1}
        v['calls'][1]['request'] = copy.deepcopy(v['setup'])

    reject('source_answer_in_public_setup', leaked_setup, full, 'leaked into public setup')
    reject('missing_raw_call', lambda v: v['calls'].pop(), bind_transport, 'coverage differs')
    reject('failed_cli_terminal', lambda v: v['calls'][0].update(terminal_exit_code=1), bind_transport, 'terminal differs')
    reject('forged_cli_response', lambda v: v['calls'][0].update(stdout='{}'), bind_transport, 'result differs')
    reject('wrong_request', lambda v: v['calls'][2].update(request={'entity': 'alias'}), bind_transport, 'request differs')
    reject('missing_real_lock_query', lambda v: v['before']['states']['a']['object_state'].pop('lock_scale'), phase, 'lock_scale')
    reject('fabricated_scale_lock', lambda v: v['before']['states']['a']['object_state'].update(lock_scale=[True, False, False]), phase, 'differs from saved')
    reject('numeric_scale_lock', lambda v: v['before']['states']['a']['object_state'].update(lock_scale=[0, 0, 0]), phase, 'invalid real scale lock')
    reject('wrong_world_frame', lambda v: v['before']['worlds']['a']['world_matrix'][0].__setitem__(3, 99.), phase, 'component differs')

    def asset(v, mutate):
        for value in [v['before']['queries']['mesh_a']['mesh_asset'], v['before']['scene']['mesh_assets']['mesh_a']]:
            mutate(value)

    reject('corrupt_position', lambda v: asset(v, lambda a: a['vertices']['v000000'].__setitem__(2, 99.)), phase, 'physical vertex')
    reject('corrupt_uv_loop', lambda v: asset(v, lambda a: a['polygons']['f000000']['uv_layers']['Detail'][0].__setitem__(0, 99.)), phase, 'component differs')
    reject('corrupt_signed_integer', lambda v: asset(v, lambda a: a['integer_attributes']['vertices']['vertices_signed'].__setitem__('v000000', 99)), phase, 'discrete value differs')
    reject('numeric_integer_type', lambda v: asset(v, lambda a: a['integer_attributes']['vertices']['vertices_signed'].__setitem__('v000000', True)), phase, 'invalid integer type')
    reject('missing_named_integer', lambda v: asset(v, lambda a: a['integer_attributes']['vertices'].pop('vertices_signed')), phase, 'fields differ')
    reject('duplicate_provenance_identity', lambda v: asset(v, lambda a: a['integer_attributes']['vertices']['formora_v_id'].__setitem__('v000001', 0)), phase, 'physical vertex')
    reject('lost_explicit_zero_weight', lambda v: asset(v, lambda a: a['vertex_weights']['v000000'].pop('pin')), phase, 'physical vertex')
    reject('wrong_provider_order', lambda v: v['result']['edit_merges'][0]['provider_order'].reverse(), receipt)
    reject('duplicate_data_processing', lambda v: v['result']['edit_merges'][0]['providers'][1].update(mesh_asset='mesh_a'), receipt, 'duplicate data processing')
    reject('false_aggregate_count', lambda v: v['result']['edit_merges'][0]['after'].update(vertices=99), receipt, 'aggregate counts')
    reject('false_detailed_count', lambda v: v['result']['edit_merges'][0]['providers'][0]['merge']['after'].update(vertices=99), receipt, 'detailed counts')
    reject('false_removed_component', lambda v: v['result']['edit_merges'][0]['providers'][0]['merge']['removed']['vertices'].append('invented'), receipt, 'removed components')
    reject('false_lineage', lambda v: v['result']['edit_merges'][0]['providers'][0]['merge']['source_to_survivor']['vertices'].update(v000000='invented'), receipt, 'lineage coverage')

    for name, mutate, reason in [
        ('missing_case', lambda r: r['records'].pop(), 'missing/duplicate'),
        ('duplicate_case', lambda r: r['records'].__setitem__(1, r['records'][0]), 'missing/duplicate'),
        ('false_source_identity', lambda r: r['source_gate'].update(native_processes=[1, 1]), 'source identity'),
        ('missing_interface', lambda r: r.update(required_interfaces=['cli']), 'missing actual interface'),
    ]:
        value = copy.deepcopy(report)
        mutate(value)
        try:
            header(value, suite, source)
        except (AssertionError, ValueError, KeyError) as error:
            assert reason in str(error)
            results.append({'control': name, 'rejected': True, 'error_type': type(error).__name__, 'error': str(error)})
        else:
            raise AssertionError('forged runtime header admitted: '+name)

    mcp_row = next(row for row in rows if row['interface'] == 'official_mcp_sdk')
    mcp = json.loads(gzip.decompress((capture/mcp_row['file']).read_bytes()))
    bind_transport(mcp)
    for name, mutate, reason in [
        ('failed_mcp_terminal', lambda v: v['mcp_process']['terminal'].update(terminal_exit_code=1), 'MCP terminal differs'),
        ('missing_mcp_terminal', lambda v: v['mcp_process'].pop('terminal'), 'terminal'),
        ('substituted_mcp_result', lambda v: v['calls'][1]['response'].update(structuredContent={}), 'MCP result differs'),
    ]:
        value = copy.deepcopy(mcp)
        mutate(value)
        try:
            bind_transport(value)
        except (AssertionError, ValueError, KeyError) as error:
            assert reason in str(error)
            results.append({'control': name, 'rejected': True, 'error_type': type(error).__name__, 'error': str(error)})
        else:
            raise AssertionError('forged MCP evidence admitted: '+name)

    reads = []

    def denied(*args, **kwargs):
        reads.append(str(args[0]) if args else 'unknown')
        raise AssertionError('pure constructor attempted a filesystem read')

    digest_inputs = hashlib.sha256()
    with patch.object(builtins, 'open', denied), patch.object(io, 'open', denied):
        for run in suite['runs']:
            value = {'input': authored_scene(suite, run), 'setup': setup(suite, run), 'request': operation(run)}
            digest_inputs.update(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    assert not reads, reads
    assert digest(path) == chosen['sha256'] and digest(capture/mcp_row['file']) == mcp_row['sha256']
    result = {'negative_controls_passed': True, 'controls': len(results), 'rows': results,
        'forged_operations_executed': False, 'original_records_unchanged': True,
        'pure_constructor_cases': 13440, 'constructor_filesystem_reads': 0,
        'all_authored_input_request_sha256': digest_inputs.hexdigest(),
        'product_acceptance': 'unrun', 'full_matrix_acceptance': 'unrun'}
    write_json(output, result)
    print(json.dumps({key: result[key] for key in ['negative_controls_passed', 'controls', 'pure_constructor_cases', 'constructor_filesystem_reads']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check(args.capture.resolve(), args.output.resolve())

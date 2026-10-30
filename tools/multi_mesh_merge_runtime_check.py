"""Bind real multi-data queries and receipts to independent source results."""
import copy
import importlib.util
import json
from pathlib import Path

from compare_snap_menu_reference import tree
from compare_multi_mesh_merge_reference import edit_providers, selected_data, context
from multi_mesh_merge_product_inputs import scene as authored_scene
from multi_mesh_merge_runtime_inputs import setup, operation

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT/'docs/evidence/mesh-merge-core/continuation'
spec = importlib.util.spec_from_file_location('multi_merge_physical_matcher', LEGACY/'pilot-native.py')
physical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(physical)
DOMAINS = [('VERT', 'vertices', 'formora_v_id'), ('EDGE', 'edges', 'formora_e_id'),
           ('FACE', 'polygons', 'formora_f_id')]


def counts(asset):
    return {'vertices': len(asset['vertices']), 'edges': len(asset.get('edges', {})),
            'faces': len(asset.get('polygons', {}))+len(asset['triangles']),
            'corners': sum(len(p['vertices']) for table in ['polygons', 'triangles']
                           for p in asset.get(table, {}).values())}


def components(asset):
    return {'vertices': set(asset['vertices']), 'edges': set(asset.get('edges', {})),
            'faces': {(kind, id) for kind, table in [('polygon', 'polygons'), ('triangle', 'triangles')]
                      for id in asset.get(table, {})}}


def elements(value):
    result = {'vertices': set(value['vertices']), 'edges': set(value['edges']),
              'faces': {(f['kind'], f['id']) for f in value['faces']}}
    assert all(len(result[k]) == len(value[k]) for k in result), 'duplicate receipt component'
    return result


def mesh_match(reference, query, world, scene, name):
    assert query['id'] == scene['entities'][name]['content']['geometry']['id']
    assert query['mesh_asset'] == scene['mesh_assets'][query['id']], 'asset query differs from saved scene'
    view = copy.deepcopy(query)
    asset = view['mesh_asset']
    for field in ['edges', 'polygons']:
        asset.setdefault(field, {})
    asset.setdefault('editing', {'mode': [], 'selected': {'vertices': [], 'edges': [], 'faces': []},
        'hidden': {'vertices': [], 'edges': [], 'faces': []}, 'history': [], 'active_face': None})
    for domain, table, tag in DOMAINS:
        actual = asset['integer_attributes'][table]
        assert 'capture' not in actual and tag in actual, 'missing actual provenance layer'
        assert all(type(value) is int for layer in actual.values() for value in layer.values()), 'invalid integer type'
        actual['capture'] = copy.deepcopy(actual[tag])
    normalized, maps = physical.normalize(view, world, reference)
    original = query['mesh_asset']
    normalized['integer_attributes'] = {
        domain: {layer: {id: values[other] for id, other in maps[key].items()}
                 for layer, values in original['integer_attributes'][table].items()}
        for (domain, table, _), key in zip(DOMAINS, ['vertices', 'edges', 'faces'])}
    live_data = {scene['entities'][id]['content']['geometry']['id']
                 for id in scene['object_context']['edit_objects']}
    normalized['data_edit_mode'] = query['id'] in live_data
    normalized['active_material_index'] = original.get('active_material_index', 0)
    normalized['vertices_metres'] = normalized['geometry']['vertices']
    normalized['world_vertices_metres'] = normalized['world_vertices']
    # Global mirror flags are fixed native operator context. Rust's explicit
    # merge command does not inherit a global mirror operation.
    assert reference['flags'] == dict(mirror_x=False, mirror_y=False, mirror_z=False, mirror_topology=False)
    assert set(reference)-{'flags'} == set(normalized), 'mesh comparison coverage differs'
    tree({key: reference[key] for key in normalized}, normalized, 'mesh/'+name)
    return maps


def compare_phase(suite, run, source, actual):
    scene = actual['scene']
    assert set(actual['worlds']) == set(actual['states']) == set(scene['entities']) == set(source['objects'])
    assert set(actual['queries']) == set(scene['mesh_assets'])
    object_context = scene['object_context']
    owners = edit_providers(suite, run)
    active = object_context['active']
    order = [active, *[n for n in object_context['order'] if n != active]]
    unique, seen = [], set()
    for name in order:
        if name in object_context['edit_objects']:
            data = scene['entities'][name]['content']['geometry']['id']
            if data not in seen:
                unique.append(name)
                seen.add(data)
    assert unique == owners == source['edit_context']['unique_data_iteration'], 'provider iteration differs'
    assert object_context['order'] == source['edit_context']['view_layer_order']
    assert [n for n in object_context['order'] if n in object_context['edit_objects']] == source['edit_context']['edit_objects']
    assert active == source['active_object'] and source['mode'] == 'EDIT_MESH'
    sharing = {}
    for name, entity in scene['entities'].items():
        world, state = actual['worlds'][name], actual['states'][name]
        assert world['id'] == state['id'] == name and world['entity'] == state['entity'] == entity
        assert world['revision'] == state['revision'] == scene['revision']
        transform, frame = entity['transform'], world['object_frames']
        assert transform['rotation']['kind'] == 'euler'
        lock = state['object_state']['lock_scale']
        assert len(lock) == 3 and all(type(v) is bool for v in lock), 'missing/invalid real scale lock'
        stored = object_context.get('states', {}).get(name, {})
        assert lock == stored.get('lock_scale', [False]*3), 'scale lock query differs from saved state'
        assert state['object_state']['lock_location'] == frame['lock_location']
        assert state['object_state']['lock_rotation'] == frame['lock_rotation']
        delta = transform.get('delta', {'translation': [0.]*3, 'euler': [0.]*3, 'scale': [1.]*3})
        fields = {'type': 'EMPTY' if entity['content']['kind'] == 'empty' else 'MESH',
            'mode': 'EDIT' if frame['edit_mode'] else 'OBJECT', 'parent': entity['parent'],
            'location': transform['translation'], 'rotation': transform['rotation']['angles'],
            'rotation_mode': transform['rotation']['order'].upper(), 'scale': transform['scale'],
            'matrix_world': world['world_matrix'], 'matrix_local': frame['matrix_local'],
            'matrix_basis': frame['matrix_basis'], 'matrix_parent_inverse': frame['matrix_parent_inverse'],
            'delta_location': delta['translation'], 'delta_rotation': delta['euler'], 'delta_scale': delta['scale'],
            'lock_location': frame['lock_location'], 'lock_rotation': frame['lock_rotation'],
            'lock_scale': lock, 'selected': frame['selected']}
        assert set(source['objects'][name])-set(fields) == {'animation_data', 'constraints', 'modifiers'}
        assert source['objects'][name]['animation_data'] is False
        assert source['objects'][name]['constraints'] == source['objects'][name]['modifiers'] == 0
        tree({key: source['objects'][name][key] for key in fields}, fields, 'object/'+name)
        if entity['content']['kind'] == 'mesh':
            data = entity['content']['geometry']['id']
            sharing.setdefault(data, []).append(name)
            mesh_match(source['meshes'][name], actual['queries'][data], world, scene, name)
    assert sorted(sorted(group) for group in sharing.values()) == source['sharing']
    assert set(source['meshes']) == {n for n, e in scene['entities'].items() if e['content']['kind'] == 'mesh'}
    tree(source['materials'], scene['materials'], 'materials')
    tree(source['cursor']['location'], scene['authoring_context']['cursor_location'], 'cursor/location')
    tree(source['cursor']['rotation'], scene['authoring_context']['cursor_rotation'], 'cursor/rotation')
    assert source['physical_metres_factor'] == 1.


def detailed_receipt(old, new, receipt):
    before, after = components(old), components(new)
    assert receipt['before'] == counts(old) and receipt['after'] == counts(new), 'false detailed counts'
    assert elements(receipt['removed']) == {k: before[k]-after[k] for k in before}, 'false removed components'
    assert elements(receipt['created']) == {k: after[k]-before[k] for k in before}, 'false created components'
    moved = {id for id in before['vertices'] & after['vertices'] if old['vertices'][id] != new['vertices'][id]}

    def attributes(asset, domain, id):
        face = domain == 'faces'
        field, key = (('polygons' if id[0] == 'polygon' else 'triangles'), id[1]) if face else (domain, id)
        item = {'kind': id[0], 'id': id[1]} if face else id
        value = {'selected': item in asset.get('editing', {}).get('selected', {}).get(domain, []),
                 'hidden': item in asset.get('editing', {}).get('hidden', {}).get(domain, []),
                 'integers': {n: v.get(key) for n, v in asset.get('integer_attributes', {}).get(field, {}).items()}}
        if domain == 'vertices':
            value.update(point=asset['vertices'][id], weights=asset.get('vertex_weights', {}).get(id))
        elif domain == 'edges':
            value.update(edge=asset['edges'][id], moved=bool(moved & set(asset['edges'][id])),
                         seam=id in asset.get('edge_seams', []))
        else:
            value.update(face=asset[field][key], moved=bool(moved & set(asset[field][key]['vertices'])),
                         smooth=key in asset.get('smooth_triangles', []))
        return value

    changed = {domain: {id for id in before[domain] & after[domain]
                       if attributes(old, domain, id) != attributes(new, domain, id)} for domain in before}
    # Incident geometry is changed whenever a surviving vertex moves, on both
    # sides of the comparison. Its flag must be independent of old/new lookup.
    for domain in ['edges', 'faces']:
        for id in before[domain] & after[domain]:
            points = new['edges'][id] if domain == 'edges' else new['polygons' if id[0] == 'polygon' else 'triangles'][id[1]]['vertices']
            if moved & set(points):
                changed[domain].add(id)
    assert elements(receipt['changed']) == changed, 'false changed components'
    lineage = receipt['source_to_survivor']
    vertices = lineage['vertices']
    assert set(vertices) == before['vertices'] and set(vertices.values()) == after['vertices'], 'false vertex lineage coverage'
    assert all(vertices[id] == id for id in after['vertices']), 'surviving vertex identity changed'
    selected = set(old.get('editing', {}).get('selected', {}).get('vertices', []))
    if selected and receipt['method'] != 'collapse':
        target = min(selected)
        if receipt['method'] in ['first', 'last']:
            target = old['editing']['history'][0 if receipt['method'] == 'first' else -1]['id']
        assert vertices == {id: target if id in selected else id for id in before['vertices']}, 'false point merge lineage'
    if receipt['method'] == 'collapse':
        adjacency = {}
        for id in old['editing']['selected']['edges']:
            a, b = old['edges'][id]
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
        remaining = set(adjacency)
        while remaining:
            reached, pending = set(), [min(remaining)]
            while pending:
                id = pending.pop()
                if id not in reached:
                    reached.add(id)
                    pending.extend(adjacency[id]-reached)
            survivors = reached & after['vertices']
            assert len(survivors) == 1 and {vertices[id] for id in reached} == survivors, 'false collapse lineage'
            remaining -= reached
        assert all(vertices[id] == id for id in before['vertices']-set(adjacency))
    pairs = {tuple(sorted(pair)): id for id, pair in new.get('edges', {}).items()}
    assert lineage['edges'] == {id: pairs[tuple(sorted([vertices[a], vertices[b]]))]
        for id, (a, b) in old.get('edges', {}).items() if vertices[a] != vertices[b]}, 'false edge lineage'
    faces = {}
    for row in lineage['faces']:
        key = (row['source']['kind'], row['source']['id'])
        assert key not in faces
        values = {(v['kind'], v['id']) for v in row['survivors']}
        assert len(values) == len(row['survivors']) and values <= after['faces']
        source = old['polygons' if key[0] == 'polygon' else 'triangles'][key[1]]
        mapped = {vertices[id] for id in source['vertices']}
        for kind, id in values:
            assert set(new['polygons' if kind == 'polygon' else 'triangles'][id]['vertices']) <= mapped
        faces[key] = values
    assert set(faces) == before['faces'] and set().union(set(), *faces.values()) == after['faces'], 'false face lineage'


def aggregate_receipt(suite, run, before, after, result):
    assert result['revision'] == after['revision'] == before['revision']+1
    assert len(result['edit_merges']) == 1 and not any(result.get(k) for k in
        ['merges', 'snaps', 'scene_snaps', 'transforms', 'selection', 'creation'])
    receipt = result['edit_merges'][0]
    owners = edit_providers(suite, run)
    assert receipt['command_index'] == 0 and receipt['active_entity'] == context(suite, run)['active']
    assert receipt['method'] == run['parameters']['type'].lower() and receipt['uvs'] is run['parameters']['uvs']
    assert receipt['status'] == 'finished' and receipt['provider_order'] == owners
    assert [p['entity'] for p in receipt['providers']] == owners, 'false provider order'
    assert len({p['mesh_asset'] for p in receipt['providers']}) == len(owners), 'duplicate data processing'
    totals = [{k: 0 for k in ['vertices', 'edges', 'faces', 'corners']} for _ in range(2)]
    stopped = False
    processed = set()
    for owner, provider in zip(owners, receipt['providers']):
        data = suite['data_sharing'][owner]
        old, new = before['mesh_assets'][data], after['mesh_assets'][data]
        assert provider['mesh_asset'] == data
        users = sorted(n for n, e in after['entities'].items()
                       if e['content'].get('geometry') == {'kind': 'asset', 'id': data})
        assert provider['shared_instances'] == users
        for total, asset in zip(totals, [old, new]):
            for key, number in counts(asset).items():
                total[key] += number
        if stopped or not selected_data(suite, run, data):
            assert provider['outcome'] == ('not_processed_after_success' if stopped else 'skipped_empty_selection')
            assert provider['merge'] is None and old == new, 'skipped data changed'
        else:
            detail = provider['merge']
            assert detail['command_index'] == 0 and detail['entity'] == owner and detail['mesh_asset'] == data
            assert detail['method'] == receipt['method'] and detail['uvs'] == receipt['uvs']
            assert detail['shared_instances'] == users and detail['status'] == 'finished'
            assert provider['outcome'] == ('unchanged' if detail['reason'] is not None else 'merged')
            detailed_receipt(old, new, detail)
            processed.add(data)
            stopped = receipt['method'] in ['first', 'last']
    assert receipt['before'] == totals[0] and receipt['after'] == totals[1], 'false aggregate counts'
    assert set(before['mesh_assets']) == set(after['mesh_assets'])
    for data in set(before['mesh_assets'])-processed:
        assert before['mesh_assets'][data] == after['mesh_assets'][data], 'unprocessed asset changed'


def check_record(suite, run, record, references):
    bind_transport(record)
    assert record['run'] == run and record['input'] == authored_scene(suite, run), 'source answer leaked into setup'
    assert record['setup'] == setup(suite, run), 'source answer leaked into public setup'
    assert record['request'] == operation(run), 'authored request differs'
    before, after = [record[p]['scene'] for p in ['before', 'after']]
    for field in set(before)-{'revision', 'mesh_assets'}:
        assert before[field] == after[field], 'unrelated scene state changed/'+field
    assert record['saved_after'] == record['fresh_scene'] == after, 'fresh load differs'
    for reference in references:
        compare_phase(suite, run, reference['before'], record['before'])
        compare_phase(suite, run, reference['after'], record['after'])
    if run['expected_enum_unavailable']:
        assert record['result'] is None and isinstance(record['error'], str) and 'unavailable' in record['error']
        assert before == after and record['saved_before_sha256'] == record['saved_after_sha256'], 'rejected mutation'
        return 'explicit_enum_rejection'
    assert record['error'] is None
    aggregate_receipt(suite, run, before, after, record['result'])
    return 'finished_source_comparison'


def bind_transport(record):
    expected = [('init', {}, {'revision': 0}, None),
                ('scene_apply', record['setup'], record['setup_result'], None)]
    for phase in ['before', 'after']:
        part = record[phase]
        current = part['scene']
        expected.append(('scene_inspect', {}, {'revision': current['revision'], 'scene': current}, None))
        for data in sorted(current['mesh_assets']):
            expected.append(('scene_inspect', {'mesh_asset': data, 'normals': True}, part['queries'][data], None))
        for name in sorted(current['entities']):
            expected.append(('scene_inspect', {'entity': name, 'world': True}, part['worlds'][name], None))
            expected.append(('scene_inspect', {'entity': name, 'object_state': True}, part['states'][name], None))
        if phase == 'before':
            expected.append(('scene_apply', record['request'], record['result'], record['error']))
    expected.append(('scene_inspect', {}, {'revision': record['fresh_scene']['revision'], 'scene': record['fresh_scene']}, None))
    assert len(expected) == len(record['calls']) == 32, 'raw call coverage differs'
    for index, (call, (name, args, result, error)) in enumerate(zip(record['calls'], expected)):
        assert call['request'] == args, 'raw request differs'
        expected_cli = record['interface'] == 'cli' or index in [0, len(expected)-1]
        assert (call['interface'] == 'cli') == expected_cli, 'wrong actual interface'
        if expected_cli:
            command = call['command']
            assert command[1:3] == ['scene', name.removeprefix('scene_')]
            assert type(call['process_id']) is int and call['process_id'] > 0
            assert (call['terminal_exit_code'] == 0) == (error is None), 'raw CLI terminal differs'
            assert json.loads(call['stdout']) == (result if error is None else {'error': error}), 'raw CLI result differs'
            if name == 'scene_apply':
                assert command[-2:] == ['--request', '-']
            else:
                actual = {}
                for key in ['entity', 'mesh_asset']:
                    flag = '--'+key.replace('_', '-')
                    if flag in command:
                        actual[key] = command[command.index(flag)+1]
                for key in ['normals', 'world', 'object_state']:
                    if '--'+key.replace('_', '-') in command:
                        actual[key] = True
                assert actual == args, 'raw CLI flags differ'
        else:
            assert call['name'] == name
            response = call['response']
            assert response['isError'] is (error is not None), 'raw MCP error flag differs'
            if error is None:
                assert response['structuredContent'] == result, 'raw MCP result differs'
                assert json.loads(response['content'][0]['text']) == result, 'raw MCP text differs'
            else:
                assert response['structuredContent'] is None and response['content'][0]['text'] == error
    if record['interface'] == 'official_mcp_sdk':
        assert record['mcp_initialization']['protocolVersion'] == '2025-11-25'
        started, terminal = [record['mcp_process'][key] for key in ['started', 'terminal']]
        assert type(started['process_id']) is int and started['process_id'] > 0
        assert started['process_id'] == terminal['process_id'] and terminal['terminal_exit_code'] == 0, 'raw MCP terminal differs'

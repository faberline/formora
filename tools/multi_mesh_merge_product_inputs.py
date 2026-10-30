"""Author product setup from inputs only; never read native or product answers."""
import copy
import struct

DOMAINS = [('VERT', 'vertex', 'vertices'), ('EDGE', 'edge', 'edges'),
           ('FACE', 'face', 'polygons')]


def floats(value):
    if isinstance(value, dict):
        return {key: floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [floats(item) for item in value]
    return struct.unpack('<f', struct.pack('<f', value))[0] if type(value) is float else value


def providers(suite, run):
    context = next(c for c in suite['contexts'] if c['id'] == run['context'])
    order = [context['active'], *[name for name in context['order'] if name != context['active']]]
    seen = set()
    owners = []
    for name in order:
        data = suite['data_sharing'].get(name)
        if data in suite['active_edit_data'] and data not in seen:
            owners.append(name)
            seen.add(data)
    return owners


def editing(suite, run, data):
    context = next(c for c in suite['contexts'] if c['id'] == run['context'])
    active = suite['data_sharing'][context['active']] == data
    selected = run['selection'] == 'both' or (
        run['selection'] == 'active_empty' and not active) or (
        run['selection'] == 'other_empty' and active)
    asset = suite['mesh_assets'][data]
    masks = {native: sorted(asset[table]) if selected else [] for native, _, table in DOMAINS}
    faces = [{'kind': 'polygon', 'id': id} for id in masks['FACE']]
    history = []
    if selected:
        vertices = list(asset['vertices'])
        edges = list(asset['edges'])
        first = {'domain': 'vertex', 'id': vertices[0]}
        last = {'domain': 'vertex', 'id': vertices[-1]}
        pattern = run['history']
        if pattern == 'both_reverse':
            history = [last, first]
        elif active and pattern == 'active_first_only':
            history = [first, {'domain': 'edge', 'id': edges[-1]}]
        elif active and pattern == 'active_last_only':
            history = [{'domain': 'edge', 'id': edges[0]}, last]
        elif not ((active and pattern == 'active_none') or (not active and pattern == 'other_none')):
            history = [first, last]
    return {
        'mode': [domain for native, domain, _ in DOMAINS if native in run['mode']],
        'selected': {'vertices': masks['VERT'], 'edges': masks['EDGE'], 'faces': faces},
        'hidden': {'vertices': [], 'edges': [], 'faces': []},
        'history': history, 'active_face': faces[-1] if faces else None,
    }


def scene(suite, run):
    """Build the canonical scene. No output, captured frame or result is input."""
    context = next(c for c in suite['contexts'] if c['id'] == run['context'])
    assets = floats(copy.deepcopy(suite['mesh_assets']))
    for name, asset in assets.items():
        if name in suite['active_edit_data']:
            asset['editing'] = editing(suite, run, name)
    entities = {}
    for name in context['order']:
        frame = suite['entity_frames'][run['frame']][name]
        content = {'kind': 'empty'}
        if name in suite['data_sharing']:
            content = {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': suite['data_sharing'][name]},
                       'material': None}
        entities[name] = {'name': name, 'parent': frame['parent'],
                          'transform': floats(copy.deepcopy(frame['transform'])), 'content': content}
    return {
        'schema_version': 1, 'revision': 0, 'time_seconds': 0.,
        'entities': entities, 'materials': floats(copy.deepcopy(suite['materials'])),
        'mesh_assets': assets, 'doors': {}, 'active_camera': None, 'annotations': [],
        'object_context': {'order': context['order'].copy(), 'selected': ['a', 'alias', 'b'],
                           'active': context['active'], 'edit_objects': providers(suite, run)},
        'authoring_context': {'cursor_location': floats(suite['authoring_context']['cursor_location']),
                              'cursor_rotation': floats(suite['authoring_context']['cursor_rotation']),
                              'view_rotation': [.25, -.375, .5]},
    }


def request(run, budget=1_000_000):
    return {'operation': 'merge_edit_meshes', 'merge': {
        'method': run['parameters']['type'].lower(), 'uvs': run['parameters']['uvs'],
        'max_components': budget,
    }}

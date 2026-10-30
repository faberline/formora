"""Build literal distance-merge scene inputs, without opening source answers."""
import copy

from generate_merge_distance_cases import asset, f32


def floats(value):
    if isinstance(value, dict):
        return {key: floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [floats(item) for item in value]
    return f32(value) if type(value) is float else value


def scene(suite, run):
    factors = run['factors']
    assets = {'mesh_a': copy.deepcopy(suite['mesh_fixtures'][factors['fixture']]),
              'mesh_b': asset([[-1., -.5, .25], [-.875, -.5, .25], [0., .5, .25], [-1., 1., .25]], [[0, 1, 2, 3]]),
              'mesh_outside': asset([[8., 0., 0.], [8.0625, 0., 0.], [8., 1., 0.]], [[0, 1, 2]])}
    names = ['parent', 'a', 'b', 'alias', 'untouched']
    identity = {'translation': [0., 0., 0.], 'rotation': {'angles': [0., 0., 0.], 'order': 'yzx'}, 'scale': [1., 1., 1.]}
    frames = {name: {'parent': None, 'transform': copy.deepcopy(identity)} for name in names}
    frame = factors['frame']
    if frame == 'noncommuting':
        values = {'parent': ([1.125, -.75, .625], [.31, -.47, .19], [1.2, .7, 1.6]),
                  'a': ([.25, -.5, .75], [.13, .23, -.37], [-.8, 1.3, .9]),
                  'b': ([-2.25, .75, 1.125], [-.29, .41, .17], [.7, 1.2, 1.6]),
                  'alias': ([3.25, -1.5, .375], [.37, -.19, .23], [1.1, -.9, .8])}
        for name, (translation, rotation, scale) in values.items():
            frames[name]['transform'] = {'translation': translation, 'rotation': {'angles': rotation, 'order': 'yzx'}, 'scale': scale}
        frames['a']['parent'] = 'parent'
    elif frame in ['nonuniform', 'negative', 'zero_axis', 'zero_parent']:
        frames['a']['transform']['scale'] = {'nonuniform': [2., .5, 1.5], 'negative': [-1., 2., -.5],
                                           'zero_axis': [0., 1., 1.], 'zero_parent': [1., 1., 1.]}[frame]
        frames['b']['transform']['translation'] = [.5, -.25, 1.]
        frames['alias']['transform']['translation'] = [3., 1., -.5]
        if frame == 'zero_parent':
            frames['parent']['transform']['scale'] = [0., 1., 1.]
            frames['a']['parent'] = 'parent'
    else:
        assert frame == 'identity'
    intent = suite['context_intent'][factors['context']]
    units = {'none': {'unit_system': 'NONE', 'unit_scale_length': 1.},
             'metric_small': {'unit_system': 'METRIC', 'unit_scale_length': .01},
             'metric_large': {'unit_system': 'METRIC', 'unit_scale_length': 100.}}[factors['units']]
    for name, mesh in assets.items():
        preset = factors['normals'] if name != 'mesh_outside' else 'automatic'
        if preset != 'automatic':
            vectors = suite['custom_normal_vectors'][preset]
            mesh['custom_corner_normals'] = {face: [copy.deepcopy(vectors[i % len(vectors)]) for i in range(len(p['vertices']))]
                                             for face, p in mesh['polygons'].items()}
        mesh['normal_preset'] = preset
    return floats({'mesh_assets': assets, 'entity_frames': frames,
                   'data_sharing': {'a': 'mesh_a', 'alias': 'mesh_a', 'b': 'mesh_b', 'untouched': 'mesh_outside'},
                   'object_context': {'order': names, 'active': intent['active'], 'selected': intent['edit_owners'].copy(),
                                      'edit_objects': intent['edit_owners'].copy()},
                   'units': units, 'mode': run['selection_mask'], 'selection': factors['selection'],
                   'history': factors['history'], 'hidden_pattern': run.get('hidden_pattern', 'none'),
                   'materials': {'mat0': {'base_color': [.8, .3, .2, 1.], 'roughness': .5, 'metallic': 0.},
                                 'mat1': {'base_color': [.2, .4, .9, 1.], 'roughness': .7, 'metallic': 0.}}})


def selection(mesh, spec, editing):
    vertices, edges, faces = [mesh[name] for name in ['vertices', 'edges', 'polygons']]
    hidden_v = {list(vertices)[-1]} if editing and spec['hidden_pattern'] == 'last_vertex' else set()
    assert spec['hidden_pattern'] in ['none', 'last_vertex']
    hidden_e = {name for name, pair in edges.items() if hidden_v.intersection(pair)}
    hidden_f = {name for name, face in faces.items() if hidden_v.intersection(face['vertices'])}
    chosen = lambda table, hidden: {name for i, name in enumerate(table) if name not in hidden and editing and
                                  (spec['selection'] == 'all' or (spec['selection'] == 'alternating' and i % 2 == 1))}
    if 'VERT' in spec['mode']:
        sv = chosen(vertices, hidden_v)
        se = {name for name, pair in edges.items() if set(pair) <= sv and name not in hidden_e}
        sf = {name for name, face in faces.items() if set(face['vertices']) <= sv and name not in hidden_f}
    elif 'EDGE' in spec['mode']:
        se = chosen(edges, hidden_e); sv = {v for name in se for v in edges[name]}
        selected_pairs = {frozenset(edges[name]) for name in se}
        sf = {name for name, face in faces.items() if name not in hidden_f and all(
            frozenset((face['vertices'][i-1], face['vertices'][i])) in selected_pairs for i in range(len(face['vertices'])))}
    else:
        assert spec['mode'] == ['FACE']
        sf = chosen(faces, hidden_f); sv = {v for name in sf for v in faces[name]['vertices']}
        pairs = {frozenset((faces[name]['vertices'][i-1], faces[name]['vertices'][i])) for name in sf for i in range(len(faces[name]['vertices']))}
        se = {name for name, pair in edges.items() if frozenset(pair) in pairs}
    selected = {'VERT': sorted(sv), 'EDGE': sorted(se), 'FACE': sorted(sf)}
    history = [{'domain': domain, 'id': name} for domain in spec['mode'] for name in selected[domain]]
    if spec['history'] == 'none': history = []
    elif spec['history'] == 'reverse': history.reverse()
    else: assert spec['history'] == 'forward'
    return {'selected': selected, 'hidden': {'VERT': sorted(hidden_v), 'EDGE': sorted(hidden_e), 'FACE': sorted(hidden_f)},
            'history': history, 'active_face': selected['FACE'][-1] if selected['FACE'] else None}

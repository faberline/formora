"""Check complete distance-capture state with retained source invariants.

Only an approved singular-parent local query is replaced in the validation
view. Its raw value remains in the capture and gets no numeric-match claim.
"""
import copy

from compare_multi_mesh_merge_reference import validate_state as validate_multi_state


def validate(spec, run, state):
    reduced = copy.deepcopy(state)
    extras = ['custom_normals_present', 'packed_custom_normals', 'native_attributes']
    for name, mesh in reduced['meshes'].items():
        for key in extras: mesh.pop(key)
        mesh['geometry'].pop('edge_sharp')
    singular = []
    for name, frame in spec['entity_frames'].items():
        parent = frame['parent']
        if parent and 0. in spec['entity_frames'][parent]['transform']['scale']:
            singular.append({'entity': name, 'classification': 'cannot_invert',
                             'raw_source_matrix_local': state['objects'][name]['matrix_local'],
                             'numeric_match_claimed': False})
            reduced['objects'][name]['matrix_local'] = reduced['objects'][name]['matrix_basis']
    validate_multi_state(spec, {'mode': run['selection_mask']}, reduced)
    for name, mesh in state['meshes'].items():
        geometry = mesh['geometry']; sharp = geometry['edge_sharp']
        assert set(sharp) == set(geometry['edges']) and all(type(v) is bool for v in sharp.values()), 'edge sharp fields'
        assert type(mesh['custom_normals_present']) is bool, 'custom normal presence type'
        packed = mesh['packed_custom_normals']
        assert not packed or set(packed) == set(geometry['faces']), 'packed normal face identities'
        for face, values in packed.items():
            assert len(values) == len(geometry['faces'][face]), 'packed normal corner count'
            assert all(len(pair) == 2 and all(type(v) is int and -32768 <= v <= 32767 for v in pair)
                       for pair in values), 'packed normal type/range'
        attributes = mesh['native_attributes']
        assert len(attributes) == len({row['name'] for row in attributes}), 'duplicate native attribute'
        lengths = {'POINT': len(geometry['vertices']), 'EDGE': len(geometry['edges']),
                   'FACE': len(geometry['faces']), 'CORNER': sum(map(len, geometry['faces'].values()))}
        for row in attributes:
            assert set(row) == {'name', 'type', 'domain', 'length'}, 'native attribute fields'
            assert type(row['name']) is str and type(row['type']) is str, 'native attribute metadata type'
            assert type(row['length']) is int and row['length'] == lengths[row['domain']], 'native attribute length'
    for group in state['sharing']:
        for name in group[1:]:
            for key in extras:
                assert state['meshes'][name][key] == state['meshes'][group[0]][key], 'shared '+key
    return singular

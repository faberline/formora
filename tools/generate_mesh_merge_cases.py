#!/usr/bin/env python3
"""Author vertex merge requests without measured source answers."""
import argparse
import copy
import itertools
import json
from pathlib import Path

from generate_snap_menu_cases import author as snap_inputs

ROOT = Path(__file__).resolve().parents[1]
METHODS = ['CENTER', 'CURSOR', 'COLLAPSE', 'FIRST', 'LAST']
SEEDS = {'grid_edge': [0, 1], 'grid_diagonal': [0, 2, 8],
         'tetrahedron': [9, 10, 11, 12], 'isolated': [13, 14], 'wire': [15, 16],
         'bow_tie': [17, 18, 19, 20, 21], 'nonmanifold': [22, 23, 24],
         'winding': [27, 28, 29, 30], 'interior': [31, 32, 33, 34, 35],
         'ngon': [43, 44, 45, 46, 47]}
DOMAINS = [(['EDGE'], 'EDGE', [0, 3]), (['FACE'], 'FACE', [0, 1]),
           (['VERT', 'EDGE'], 'EDGE', [1, 2]), (['VERT', 'FACE'], 'FACE', [4, 5]),
           (['EDGE', 'FACE'], 'FACE', [0]), (['VERT', 'EDGE', 'FACE'], 'FACE', [0, 1])]


def author():
    suite = snap_inputs()
    template = copy.deepcopy(suite['runs'][0])
    suite['runs'] = []
    suite['profiles'] = {k: v for k, v in suite['profiles'].items() if k != 'singular'}
    mesh = copy.deepcopy(json.loads((ROOT / 'baseline/fixtures/mesh-selection.json').read_text())['mesh'])
    mesh['active_material_index'] = 1
    mesh['group_scenarios'] = {'authored': {'names': ['pin', 'soft'], 'weights': {
        f'v{i:06}': {**({'pin': 0. if i % 4 == 0 else .25} if i % 2 == 0 else {}),
                     **({'soft': .75} if i % 3 == 0 else {})} for i in range(len(mesh['vertices']))}}}
    suite['mesh'] = mesh
    suite['scope'] = '1024 native vertex merge source cases; no product acceptance.'
    suite['groups_expected'] = {'vertex_topology': 800, 'selection_domains': 144, 'empty_single': 80}
    suite['operators'] = ['merge']

    def add(group, method, uvs, frame, label, indices, mode=('VERT',), domain='VERT', reverse=False):
        run = copy.deepcopy(template)
        run.update(id=f'merge_{len(suite["runs"]):04}', label=group, selection_label=label,
                   operator='merge', feature='mesh.merge', mode='EDIT_MESH', initial_mode=list(mode),
                   seed={'domain': domain, 'indices': list(reversed(indices)) if reverse else list(indices)},
                   parameters={'type': method, 'uvs': uvs})
        run['context'].update(profile=frame, multi_object=True, linked_data=True,
                              object_selection=['target', 'secondary'], active_object='target',
                              history='preserve', origins_only=False, skip_children=False)
        run['expected_empty_enum_boundary'] = not indices and method in ['FIRST', 'LAST']
        suite['runs'].append(run)

    for method, uvs, (label, indices), frame, reverse in itertools.product(
            METHODS, [False, True], SEEDS.items(), suite['profiles'], [False, True]):
        add('vertex_topology', method, uvs, frame, label, indices, reverse=reverse)
    for method, uvs, (mode, domain, indices), frame in itertools.product(
            METHODS[:3], [False, True], DOMAINS, suite['profiles']):
        add('selection_domains', method, uvs, frame, '+'.join(mode), indices, mode, domain)
    for method, uvs, (label, indices), frame in itertools.product(METHODS, [False, True],
            [('empty', []), ('single', [0])], suite['profiles']):
        add('empty_single', method, uvs, frame, label, indices)
    assert len(suite['runs']) == 1024
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x') as output:
        json.dump(author(), output, indent=2, allow_nan=False)
        output.write('\n')

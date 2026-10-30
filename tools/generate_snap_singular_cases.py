#!/usr/bin/env python3
"""Author exact zero-scale inputs without measured source answers."""
import argparse
import copy
import itertools
import json
from pathlib import Path

from generate_snap_delta_cases import author as delta_inputs, delta
from generate_snap_rotation_cases import MODES, FORMS, channels

OTHER = ['snap_selected_to_grid', 'snap_selected_to_active', 'snap_cursor_to_grid',
         'snap_cursor_to_selected', 'snap_cursor_to_active', 'snap_cursor_to_center']
FORMS_ALL = [('snap_selected_to_cursor', f) for f in FORMS] + [(o, None) for o in OTHER]


def author():
    suite = delta_inputs()
    template = copy.deepcopy(suite['runs'][0])
    original = copy.deepcopy(suite['profiles'])
    suite['runs'] = []
    suite['scope'] = '1764 exact zero-scale direct-snap source cases; product acceptance unrun.'
    suite['groups_expected'] = {'normal_scale': 1120, 'mesh_edit': 84,
                                'origin_children': 112, 'delta_scale': 448}
    suite['profiles'] = {}
    for role, mask in itertools.product(['target', 'parent'], range(1, 8)):
        p = copy.deepcopy(original['unparented' if role == 'target' else 'rotated_parent'])
        affected = p if role == 'target' else p['parent']
        affected['scale'] = [0. if mask & (1 << i) else v
                             for i, v in enumerate([-1.2, .7, 1.6])]
        suite['profiles'][f'{role}_{mask}'] = p
    for role in ['target', 'parent']:
        suite['profiles'][f'{role}_delta'] = copy.deepcopy(
            original['unparented' if role == 'target' else 'rotated_parent'])

    def add(group, role, mask, mode, operator, form, edit=False, settings=(False, False)):
        run = copy.deepcopy(template)
        run.update(id=f'singular_snap_{len(suite["runs"]):04}', label=group,
                   mode='EDIT_MESH' if edit else 'OBJECT', operator=operator,
                   feature='scene.' + operator, parameters={} if form is None else
                   {'use_offset': form[0], 'use_rotation': form[1]})
        run['context'].update(profile=f'{role}_delta' if group == 'delta_scale' else f'{role}_{mask}',
                              lock_rotation=[False] * 3, lock_location=[False] * 3,
                              origins_only=settings[0], skip_children=settings[1])
        run['rotations'] = {'objects': channels(mode, 'regular' if role == 'target' else 'zero'),
                            'cursor': channels(mode, cursor=True),
                            'lock_rotation_w': False, 'lock_rotations_4d': False}
        run['deltas'] = delta('combined' if role == 'target' else 'translation')
        run['role_deltas'] = copy.deepcopy(suite['role_deltas'])
        run['zero_scale'] = {'role': role, 'mask': mask,
                              'channel': 'delta' if group == 'delta_scale' else 'normal'}
        if group == 'delta_scale':
            affected = run['deltas'] if role == 'target' else run['role_deltas']['parent']
            affected['scale'] = [0. if mask & (1 << i) else v
                                 for i, v in enumerate([-1.2, .7, 1.6])]
        suite['runs'].append(run)

    for mask, role, mode, (op, form) in itertools.product(range(1, 8),
            ['target', 'parent'], MODES, FORMS_ALL):
        add('normal_scale', role, mask, mode, op, form)
    for mask, role, (op, form) in itertools.product(range(1, 8), ['target', 'parent'],
            [x for x in FORMS_ALL if x[0].startswith('snap_selected')]):
        add('mesh_edit', role, mask, 'XYZ', op, form, edit=True)
    for mask, settings, form in itertools.product(range(1, 8), FORMS, FORMS):
        add('origin_children', 'target', mask, 'XYZ', 'snap_selected_to_cursor', form, settings=settings)
    for mask, role, mode, form in itertools.product(range(1, 8), ['target', 'parent'], MODES, FORMS):
        add('delta_scale', role, mask, mode, 'snap_selected_to_cursor', form)
    assert len(suite['runs']) == 1764
    return suite


def effective_suite(suite, run):
    """Use only authored per-case role deltas, never captured state."""
    value = dict(suite)
    value['role_deltas'] = copy.deepcopy(run['role_deltas'])
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x') as output:
        json.dump(author(), output, indent=2, allow_nan=False)
        output.write('\n')

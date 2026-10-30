#!/usr/bin/env python3
"""Author rotation snapping inputs. Never read measured source answers."""
import argparse
import copy
import itertools
import json
import math
from pathlib import Path

from generate_snap_menu_cases import author as snap_inputs

MODES = ['XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX', 'QUATERNION', 'AXIS_ANGLE']
FORMS = list(itertools.product([False, True], repeat=2))


def channels(mode, profile='regular', cursor=False):
    euler = [.2, -.4, .6] if cursor else [.31, -.23, .47]
    quat = [.5, .5, -.5, .5] if cursor else [.5, -.5, .5, .5]
    axis = [.65, 1., -2., 3.] if cursor else [-.45, -2., 1., 3.]
    if profile == 'zero':
        euler, quat, axis = [0., 0., 0.], [1., 0., 0., 0.], [0., 1., 0., 0.]
    elif profile == 'half_turn':
        euler, quat, axis = [math.pi, 0., 0.], [0., 1., 0., 0.], [math.pi, 1., 0., 0.]
    elif profile == 'near_half_turn':
        euler = [math.pi + 2**-22, -math.pi / 2 + 2**-24, 2**-24]
        quat, axis = [2**-24, 1., 0., 0.], [math.pi + 2**-22, 1., 0., 0.]
    elif profile == 'multiple_turns':
        euler, quat, axis = [4*math.pi+.2, -2*math.pi-.3, .4], [-1., 0., 0., 0.], [4*math.pi+.4, 0., 1., 0.]
    elif profile == 'nonunit_axis':
        euler, quat, axis = [-.71, .32, 1.13], [-.5, .5, -.5, -.5], [1.13, -3., 4., -2.]
    else:
        assert profile == 'regular'
    return {'mode': mode, 'euler': euler, 'quaternion_wxyz': quat, 'axis_angle': axis}


def author():
    suite = snap_inputs()
    template = copy.deepcopy(next(r for r in suite['runs'] if r['mode'] == 'OBJECT'))
    parent = {'location': [1.25, -.75, 2.], 'rotation': [.37, -.23, .51], 'scale': [1., 1., 1.]}
    target = {'location': [.25, -.5, .75], 'rotation': [0., 0., 0.], 'scale': [.9, 1.4, .8], 'parent': None}
    profiles = {'unparented': copy.deepcopy(target)}
    for key, scale in [('rotated_parent', [1., 1., 1.]), ('reflected_parent', [-1., 1., 1.]),
                       ('scaled_parent', [1.2, .7, 1.6])]:
        profiles[key] = copy.deepcopy(target)
        profiles[key]['parent'] = copy.deepcopy(parent)
        profiles[key]['parent']['scale'] = scale
    suite['profiles'] = profiles
    suite['runs'] = []
    suite['rotation_modes'] = MODES
    suite['scope'] = '2496 finite direct-snap rotation representation cases; no complete feature acceptance.'
    suite['groups_expected'] = {'cross_modes': 1024, 'locks': 1024, 'boundaries': 320,
                                'cursor_only': 96, 'mesh_edit': 32}

    def add(group, objmode, cursormode, frame, form=(False, True), mask=0, boundary='regular',
            operator='snap_selected_to_cursor', edit=False):
        run = copy.deepcopy(template)
        run.update(id=f'rotation_snap_{len(suite["runs"]):04}', label=group, mode='EDIT_MESH' if edit else 'OBJECT',
                   operator=operator, feature='scene.'+operator,
                   parameters={'use_offset': form[0], 'use_rotation': form[1]} if operator=='snap_selected_to_cursor' else {})
        run['context'].update(profile=frame, grid_spacing=.75, linked_data=True, multi_object=True,
                              lock_rotation=[bool(mask & (1 << i)) for i in range(3)])
        run['rotations'] = {'objects': channels(objmode, boundary), 'cursor': channels(cursormode, boundary, True),
                            'lock_rotation_w': bool(mask & 8), 'lock_rotations_4d': group=='locks'}
        suite['runs'].append(run)

    for objmode, cursormode, frame, form in itertools.product(MODES, MODES, profiles, FORMS):
        add('cross_modes', objmode, cursormode, frame, form)
    for objmode, mask, frame, form in itertools.product(MODES, range(16),
                                                       ['unparented', 'rotated_parent'], FORMS):
        add('locks', objmode, 'XYZ', frame, form, mask)
    for mode, boundary, frame, form in itertools.product(MODES,
            ['zero', 'half_turn', 'near_half_turn', 'multiple_turns', 'nonunit_axis'],
            ['unparented', 'rotated_parent'], FORMS):
        add('boundaries', mode, mode, frame, form, boundary=boundary)
    for mode, operator, frame in itertools.product(MODES,
            ['snap_cursor_to_grid', 'snap_cursor_to_selected', 'snap_cursor_to_active', 'snap_cursor_to_center'],
            ['unparented', 'rotated_parent', 'scaled_parent']):
        add('cursor_only', 'XYZ', mode, frame, operator=operator)
    for mode, form in itertools.product(MODES, FORMS):
        add('mesh_edit', 'XYZ', mode, 'rotated_parent', form, edit=True)
    assert len(suite['runs']) == 2496
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x') as output:
        json.dump(author(), output, indent=2, allow_nan=False)
        output.write('\n')

#!/usr/bin/env python3
"""Author nonidentity delta snapping inputs without measured answers."""
import argparse
import copy
import itertools
import json
from pathlib import Path

from generate_snap_rotation_cases import MODES, FORMS, author as rotation_inputs, channels


def delta(profile):
    value = {'location': [0., 0., 0.], 'euler': [0., 0., 0.],
             'quaternion_wxyz': [1., 0., 0., 0.], 'scale': [1., 1., 1.]}
    if profile in ['translation', 'combined']:
        value['location'] = [.125, -.25, .375]
    if profile in ['rotation', 'combined']:
        value['euler'] = [.17, -.11, .29]
        value['quaternion_wxyz'] = [-1., 1., 1., -1.]
    if profile == 'scale':
        value['scale'] = [-1.1, .8, 1.3]
    elif profile == 'combined':
        value['scale'] = [1.2, .75, 1.1]
    assert profile in ['identity', 'translation', 'rotation', 'scale', 'combined']
    return value


def author():
    suite = rotation_inputs()
    template = copy.deepcopy(suite['runs'][0])
    suite['runs'] = []
    suite['scope'] = '1792 finite nonidentity delta direct-snap source cases; no complete feature acceptance.'
    suite['groups_expected'] = {'delta_profiles': 512, 'locks': 1024, 'cursor_only': 96,
                                'mesh_edit': 32, 'origin_children': 128}
    suite['role_deltas'] = {'parent': delta('translation'), 'child': delta('identity')}
    suite['role_deltas']['child']['location'] = [-.25, .125, .0625]

    def add(group, mode, frame, form=(False, True), profile='combined', mask=0,
            operator='snap_selected_to_cursor', cursor=None, edit=False, settings=(False, False)):
        run = copy.deepcopy(template)
        run.update(id=f'delta_snap_{len(suite["runs"]):04}', label=group,
                   mode='EDIT_MESH' if edit else 'OBJECT', operator=operator, feature='scene.'+operator,
                   parameters={'use_offset': form[0], 'use_rotation': form[1]}
                   if operator == 'snap_selected_to_cursor' else {})
        locks = [bool(mask & (1 << i)) for i in range(3)]
        run['context'].update(profile=frame, lock_rotation=locks, lock_location=locks,
                              origins_only=settings[0], skip_children=settings[1])
        run['rotations'] = {'objects': channels(mode), 'cursor': channels(cursor or mode, cursor=True),
                            'lock_rotation_w': bool(mask & 8), 'lock_rotations_4d': group == 'locks'}
        run['deltas'] = delta(profile)
        run['delta_profile'] = profile
        suite['runs'].append(run)

    for mode, profile, frame, form in itertools.product(MODES,
            ['translation', 'rotation', 'scale', 'combined'], suite['profiles'], FORMS):
        add('delta_profiles', mode, frame, form, profile)
    for mode, mask, frame, form in itertools.product(MODES, range(16),
            ['unparented', 'rotated_parent'], FORMS):
        add('locks', mode, frame, form, mask=mask, cursor='XYZ')
    for cursor, operator, frame in itertools.product(MODES,
            ['snap_cursor_to_grid', 'snap_cursor_to_selected', 'snap_cursor_to_active', 'snap_cursor_to_center'],
            ['unparented', 'rotated_parent', 'scaled_parent']):
        add('cursor_only', 'XYZ', frame, operator=operator, cursor=cursor)
    for cursor, form in itertools.product(MODES, FORMS):
        add('mesh_edit', 'XYZ', 'rotated_parent', form, cursor=cursor, edit=True)
    for mode, settings, form in itertools.product(MODES, FORMS, FORMS):
        add('origin_children', mode, 'scaled_parent', form, settings=settings)
    assert len(suite['runs']) == 1792
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x') as output:
        json.dump(author(), output, indent=2, allow_nan=False)
        output.write('\n')

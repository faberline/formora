#!/usr/bin/env python3
"""Author direct snapping inputs without reading measured reference outputs."""
import argparse
import copy
import itertools
import json
from pathlib import Path

from generate_mesh_transform_cases import author as transform_inputs

OPERATORS = ['snap_selected_to_grid', 'snap_selected_to_cursor', 'snap_selected_to_active',
             'snap_cursor_to_grid', 'snap_cursor_to_selected', 'snap_cursor_to_active',
             'snap_cursor_to_center']
FEATURES = {op: 'scene.' + op for op in OPERATORS}
PIVOTS = ['MEDIAN_POINT', 'BOUNDING_BOX_CENTER', 'CURSOR', 'ACTIVE_ELEMENT', 'INDIVIDUAL_ORIGINS']


def author():
    original = transform_inputs()
    mesh = copy.deepcopy(original['mesh'])
    mesh['vertices'] = [[0.75*x+0.375, 0.75*y-0.625, 0.75*z+0.1875]
                        for x, y, z in mesh['vertices']]
    boundary = len(mesh['vertices'])
    mesh['vertices'] += [[0.5,-0.5,1.5], [-1.5,2.5,-2.5],
                         [0.4999999701976776,-0.5000000596046448,0.5000000596046448],
                         [0.5000000596046448,-0.4999999701976776,0.4999999701976776],
                         [0.5,-0.5,1.5], [0,0,0], [9.375,-8.625,7.875]]
    environment = copy.deepcopy(original['environment'])
    environment['view_perspective'] = 'PERSP'
    selections = {
        'vertices': {'initial_mode':['VERT'], 'seed':{'domain':'VERT','indices':[0,2,8]}},
        'edges': {'initial_mode':['EDGE'], 'seed':{'domain':'EDGE','indices':[0,3]}},
        'faces': {'initial_mode':['FACE'], 'seed':{'domain':'FACE','indices':[0,1]}},
        'combined': {'initial_mode':['VERT','EDGE','FACE'], 'seed':{'domain':'FACE','indices':[0,1]}},
        'empty': {'initial_mode':['VERT'], 'seed':{'domain':'VERT','indices':[]}},
        'hidden_only': {'initial_mode':['VERT'], 'seed':{'domain':'VERT','indices':[0,2]}, 'hide_all':True},
        'boundaries': {'initial_mode':['VERT'], 'seed':{'domain':'VERT','indices':list(range(boundary,boundary+7))}},
    }
    suite = {'schema_version':1, 'reference':original['reference'], 'mesh':mesh,
             'profiles':copy.deepcopy(original['profiles']), 'environment':environment,
             'coordinate_system':{'handedness':'right','up':'Z','source_positions':'raw_scene_units',
                 'physical_metres_factor':'1 for NONE, otherwise unit_scale_length; raw source values are retained'},
             'operators':OPERATORS, 'runs':[],
             'object_inputs':{
                 'secondary':{'location':[-1.25,2.375,-0.75], 'rotation':[-0.2,0.4,-0.1], 'scale':[1.3,0.8,0.65]},
                 'child':{'location':[0.25,-0.75,0.5], 'rotation':[0,0,0], 'scale':[1,1,1]}},
             'comparison':{'positions_absolute_tolerance_metres':1e-6,
                           'normals_absolute_tolerance':1e-6, 'uv_absolute_tolerance':1e-6,
                           'rotation_component_absolute_tolerance':1e-6},
             'scope':'Seven direct snap operators. Finite mesh-edit and object cases. No feature acceptance.'}

    def add(op, profile='identity', selection='vertices', pivot='MEDIAN_POINT',
            grid=1.0, mode='EDIT_MESH', parameters=None, **extra):
        selected = selections[selection]
        context = {'profile':profile, 'pivot':pivot, 'mirror_x':False,
                   'mirror_topology':False, 'correct_face_attributes':False, 'keep_connected':True,
                   'grid_spacing':grid, 'unit_system':'NONE', 'unit_scale_length':1.0,
                   'history':'preserve', 'active_face_override':'preserve',
                   'object_selection':['target'] if mode=='EDIT_MESH' else ['target','secondary'],
                   'active_object':'target', 'multi_object':mode=='OBJECT',
                   'secondary_parent':None, 'linked_data':False,
                   'skip_children':False, 'origins_only':False,
                   'lock_location':[False]*3, 'lock_rotation':[False]*3,
                   'cursor_location':environment['cursor_location'],
                   'cursor_rotation':environment['cursor_rotation']}
        if selected.get('hide_all'):
            context['hide_all'] = True
        context.update(extra)
        run = {'id':f'snap_{len(suite["runs"]):04}', 'label':selection,
               'operator':op, 'feature':FEATURES[op], 'groups':'authored',
               'mode':mode, 'initial_mode':selected['initial_mode'], 'seed':selected['seed'],
               'context':context, 'parameters':parameters or {}, 'repeat_policy':'deterministic'}
        suite['runs'].append(copy.deepcopy(run))

    for profile, selection in itertools.product(suite['profiles'], selections):
        for grid in [0.25,1.0,2.0]:
            add('snap_selected_to_grid', profile, selection, grid=grid)
        for pivot in PIVOTS:
            for offset, rotate in itertools.product([False,True], repeat=2):
                add('snap_selected_to_cursor', profile, selection, pivot,
                    parameters={'use_offset':offset,'use_rotation':rotate})
            add('snap_cursor_to_selected', profile, selection, pivot)
        for op in ['snap_selected_to_active','snap_cursor_to_active']:
            add(op, profile, selection)
    for grid, location in itertools.product([0.25,1.0,2.0],
                                          [[0.5,-0.5,1.5],[-1.5,2.5,-2.5],environment['cursor_location']]):
        add('snap_cursor_to_grid', grid=grid, cursor_location=location)
    for location in [[0,0,0],[0.5,-0.5,1.5],environment['cursor_location']]:
        add('snap_cursor_to_center', cursor_location=location)
    # Active elements are not equivalent to the selected centroid.
    for selection in ['vertices','edges','faces','combined']:
        for op in ['snap_selected_to_active','snap_cursor_to_active','snap_selected_to_cursor']:
            add(op, selection=selection, pivot='ACTIVE_ELEMENT', history='clear',
                active_face_override=None, parameters={'use_offset':True} if op.endswith('to_cursor') else {})
            add(op, selection=selection, pivot='ACTIVE_ELEMENT', history='clear',
                active_face_override=2, parameters={'use_offset':True} if op.endswith('to_cursor') else {})

    variants = [(op,{}) for op in OPERATORS if op != 'snap_selected_to_cursor']
    variants += [('snap_selected_to_cursor',{'use_offset':offset,'use_rotation':rotation})
                 for offset,rotation in itertools.product([False,True], repeat=2)]
    for profile, pivot, (op, parameters) in itertools.product(suite['profiles'],PIVOTS,variants):
        add(op,profile,pivot=pivot,mode='OBJECT',parameters=parameters)
    for mode, (op, parameters) in itertools.product(['EDIT_MESH','OBJECT'],variants):
        choices = [['target'],['secondary'],['target','secondary']] if mode=='EDIT_MESH' else [[],['target'],['secondary'],['target','secondary','child']]
        for selection in choices:
            add(op,mode=mode,parameters=parameters,profile='parent', object_selection=selection,
                active_object=selection[0] if selection else 'target',
                secondary_parent='target', linked_data=False, multi_object=True)
        for linked, skip_children, origins_only in itertools.product([False,True],repeat=3):
            add(op,mode=mode,parameters=parameters,profile='reflected',linked_data=linked,
                skip_children=skip_children,origins_only=origins_only,
                multi_object=True,object_selection=['target','secondary'])
    for (op, parameters), locks in itertools.product(variants,
                [[False,False,False],[True,False,False],[False,True,True],[True,True,True]]):
        add(op,mode='OBJECT',parameters=parameters,profile='parent',
            lock_location=locks,lock_rotation=locks,secondary_parent='target')
    for (op, parameters), active in itertools.product(variants,[None,'secondary','child']):
        add(op,mode='OBJECT',parameters=parameters,active_object=active,
            object_selection=['target'],secondary_parent='target')
    for op in ['snap_selected_to_grid','snap_cursor_to_grid']:
        for system, scale, grid in itertools.product(['NONE','METRIC','IMPERIAL'],[0.25,1.0,2.0],[0.5,2.0]):
            add(op,selection='boundaries',unit_system=system,unit_scale_length=scale,grid=grid)
    return suite


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    suite=author()
    args.output.write_text(json.dumps(suite,indent=2)+'\n')
    print(json.dumps({'runs':len(suite['runs']),'features':len(FEATURES),
                      'modes':sorted({r['mode'] for r in suite['runs']})}))

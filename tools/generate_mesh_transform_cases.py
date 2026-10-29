#!/usr/bin/env python3
"""Author transform inputs. Never read measured reference geometry."""
import argparse
import copy
import itertools
import json
import math
from pathlib import Path

ORIENTATIONS=['GLOBAL','LOCAL','NORMAL','GIMBAL','VIEW','CURSOR','PARENT']
PIVOTS=['MEDIAN_POINT','BOUNDING_BOX_CENTER','CURSOR','ACTIVE_ELEMENT','INDIVIDUAL_ORIGINS']
FALLOFFS=['SMOOTH','SPHERE','ROOT','INVERSE_SQUARE','SHARP','LINEAR','CONSTANT','RANDOM']
OPERATORS=['translate','rotate','resize']
FEATURES=['mesh.transform.'+name for name in ['translate','rotate','resize','orientation','pivot','falloff','connected','projected']]


def author():
    vertices=[[x,y,0.25 if x==0 and y==0 else 0] for y in [-1,0,1] for x in [-1,0,1]]
    vertices += [[2.5,-0.5,0.25],[3.5,-0.5,0.25],[3.5,0.5,0.25],[2.5,0.5,0.25],[-0.5,0,1.5],[0.5,0,1.5],[0,0,2],[-5,0,0],[-4,0,0],[-4,1,0],[-5,1,0]]
    faces=[[0,1,4,3],[1,2,5,4],[3,4,7,6],[4,5,8,7],[9,10,11,12],[16,17,18,19]]
    edges=[]
    for face in faces:
        for a,b in zip(face,face[1:]+face[:1]):
            edge=sorted([a,b])
            if edge not in edges:edges.append(edge)
    edges.append([13,14])
    mesh={'vertices':vertices,'edges':edges,'faces':faces,
          'hidden':{'vertices':[16,17,18,19],'edges':[i for i,e in enumerate(edges) if min(e)>=16],'faces':[5]},
          'material_slots':['TransformMaterial0','TransformMaterial1'],
          'face_materials':[i%2 for i in range(len(faces))],'face_smooth':[bool(i%2) for i in range(len(faces))],
          'edge_seams':[i%3==0 for i in range(len(edges))],
          'uv_layers':[{'name':name,'faces':[[[sign*(i*0.125+j*0.25),0.125+j*0.125] for j in range(len(face))] for i,face in enumerate(faces)]} for name,sign in [('Detail',1),('Layout',-1)]],
          'active_uv_index':1,'group_scenarios':{'authored':{'names':['pin','soft'],'weights':{'v000004':{'pin':1},'v000000':{'soft':0.75},'v000002':{'soft':0.5},'v000011':{'pin':0,'soft':0.25}}}}}
    profiles={
        'identity':{'location':[0,0,0],'rotation':[0,0,0],'scale':[1,1,1],'parent':None},
        'rotated':{'location':[2.25,-1.75,0.625],'rotation':[0.21,-0.31,0.47],'scale':[1.5,0.65,1.2],'parent':None},
        'reflected':{'location':[0.5,-0.75,0.25],'rotation':[0.21,-0.31,0.47],'scale':[-1.25,0.75,1.5],'parent':None},
        'parent':{'location':[-0.7,0.35,0.6],'rotation':[0.13,0.29,-0.41],'scale':[0.9,1.4,0.8],
                  'parent':{'location':[1.25,-0.75,2],'rotation':[0.37,-0.23,0.51],'scale':[1.2,0.7,1.6]}},
        'singular':{'location':[0.25,-0.5,0.75],'rotation':[0.21,-0.31,0.47],'scale':[1,0,1],'parent':None}}
    runs=[]
    values={'translate':[0.375,-0.625,0.25],'rotate':0.61,'resize':[1.25,0.65,1.1]}
    seeds={'VERT':{'domain':'VERT','indices':[0,2]},'EDGE':{'domain':'EDGE','indices':[0,1]},'FACE':{'domain':'FACE','indices':[0,4]}}
    def add(op,label,mode='VERT',profile='identity',pivot='MEDIAN_POINT',parameters=None,seed=None,context=None,tags=()):
        params={'value':copy.deepcopy(values[op]),'orient_type':'GLOBAL','mirror':False,'use_proportional_edit':False,'snap':False}
        params.update(parameters or {})
        run={'id':f'transform_{len(runs):04}','label':label,'operator':op,'feature':'mesh.transform.'+op,
             'features':list(dict.fromkeys(['mesh.transform.'+op,*tags])),
             'groups':'authored','initial_mode':[mode],'seed':copy.deepcopy(seeds[mode] if seed is None else seed),
             'context':{'profile':profile,'pivot':pivot,'mirror_x':False,'mirror_topology':False,'correct_face_attributes':False,'keep_connected':True,**(context or {})},
             'parameters':params,'repeat_policy':'stochastic_path_support' if params.get('proportional_edit_falloff')=='RANDOM' else 'deterministic'}
        runs.append(run)
    for op,orientation,pivot,mode,profile in itertools.product(OPERATORS,ORIENTATIONS,PIVOTS,['VERT','EDGE','FACE'],['identity','parent']):
        mask={'VERT':[True,False,False],'EDGE':[True,True,False],'FACE':[False,False,False]}[mode]
        add(op,'orientation/pivot/domain/frame',mode,profile,pivot,{'orient_type':orientation,'constraint_axis':mask},tags=['mesh.transform.orientation','mesh.transform.pivot'])
    for op,orientation,mask in itertools.product(OPERATORS,ORIENTATIONS,itertools.product([False,True],repeat=3)):
        add(op,'axis mask',profile='rotated',parameters={'orient_type':orientation,'constraint_axis':list(mask)},tags=['mesh.transform.orientation'])
    variants={'translate':[[0,0,0],[1e-7,0,0],[-3,2,-1],[0,0,2]],'rotate':[0,math.pi/2,-math.pi/2,math.tau,-math.tau,1e-6,-0.61,4*math.pi],
              'resize':[[0,0,0],[0,1,1],[-1,1,1],[-1,-1,-1],[1e-6,3,2],[1,1,1]]}
    for op in OPERATORS:
        for value,mode in itertools.product(variants[op],['VERT','EDGE','FACE']):add(op,'value boundary',mode,profile='reflected',parameters={'value':value})
    for op,falloff,connected,projected,profile in itertools.product(OPERATORS,FALLOFFS,[False,True],[False,True],['identity','parent']):
        add(op,'proportional',profile=profile,seed={'domain':'VERT','indices':[4]},parameters={'use_proportional_edit':True,'proportional_edit_falloff':falloff,'proportional_size':2.4,'use_proportional_connected':connected,'use_proportional_projected':projected},tags=['mesh.transform.falloff','mesh.transform.connected','mesh.transform.projected'])
    for op,radius,connected in itertools.product(OPERATORS,[1e-6,0.999999,1,1.000001,2.4,1e12],[False,True]):
        add(op,'proportional radius boundary',seed={'domain':'VERT','indices':[4]},parameters={'use_proportional_edit':True,'proportional_edit_falloff':'LINEAR','proportional_size':radius,'use_proportional_connected':connected},tags=['mesh.transform.falloff','mesh.transform.connected'])
    for op,mode,pivot in itertools.product(['rotate','resize'],['VERT','EDGE','FACE'],PIVOTS):
        add(op,'explicit centre override',mode,pivot=pivot,parameters={'center_override':[0.375,-0.625,0.875]},tags=['mesh.transform.pivot'])
    for op,mirror,topology in itertools.product(OPERATORS,[False,True],[False,True]):
        add(op,'mirror',seed={'domain':'VERT','indices':[0,3]},parameters={'mirror':mirror},context={'mirror_x':True,'mirror_topology':topology})
    for op,accurate in itertools.product(OPERATORS,[False,True]):add(op,'precision option',parameters={'use_accurate':accurate})
    custom=[[0.8,-0.6,0],[0.6,0.8,0],[0,0,1]]
    for op,mode,mask in itertools.product(OPERATORS,['VERT','EDGE','FACE'],[[True,False,False],[False,True,False],[True,True,False]]):
        add(op,'explicit orientation matrix',mode,profile='rotated',parameters={'orient_matrix':custom,'orient_matrix_type':'GLOBAL','constraint_axis':mask},tags=['mesh.transform.orientation'])
    for op in OPERATORS:
        add(op,'empty selection',seed={'domain':'VERT','indices':[]})
        add(op,'hidden-only geometry',seed={'domain':'VERT','indices':[]},context={'hide_all':True})
    for op,orientation in itertools.product(OPERATORS,['GLOBAL','LOCAL','NORMAL','PARENT']):
        add(op,'singular target',profile='singular',parameters={'orient_type':orientation,'constraint_axis':[True,False,False]},tags=['mesh.transform.orientation'])
    for op,keep,mode in itertools.product(OPERATORS,[False,True],['VERT','EDGE','FACE']):
        add(op,'correct face attributes',mode,context={'correct_face_attributes':True,'keep_connected':keep})
    for i,run in enumerate(runs):
        assert run['id']==f'transform_{i:04}'
        assert set(run['features'])<=set(FEATURES)
    return {'schema_version':1,'reference':{'version':[5,2,3],'build_hash':'e13b728c6880'},'comparison':{'positions_absolute_tolerance_metres':1e-6,'normals_absolute_tolerance':1e-6,'uv_absolute_tolerance':1e-6},
            'environment':{'cursor_location':[0.375,-0.625,0.875],'cursor_rotation':[0.2,-0.4,0.6],'view_rotation':[0.35,-0.25,0.6],'view_location':[0.25,-0.5,0.75],'view_distance':8,'view_perspective':'ORTHO'},
            'mesh':mesh,'profiles':profiles,'runs':runs,'product_acceptance':'unrun'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);args=p.parse_args()
    with args.output.open('x') as stream:json.dump(author(),stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'authored_runs':len(author()['runs']),'measured_geometry_inputs':0}))

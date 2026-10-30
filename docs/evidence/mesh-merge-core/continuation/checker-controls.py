"""Reject corrupt real saved results before running the full interface gate."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('merge_pilot',HERE/'pilot-native.py')
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)
raw=pilot.load(HERE/'pilot-02/merge_0000.json.gz')
reference=pilot.load(pilot.ROOT/'docs/evidence/mesh-merge-baseline/native-01/merge_0000.json.gz')['after']['meshes']['target']
base=raw['after'];pilot.compare(reference,base['query'],base['world'])
def position(q,w):q['mesh_asset']['vertices']['v000000'][0]+=0.01
def edge(q,w):q['mesh_asset']['edges']['e000001']=['v000000','v000008']
def uv(q,w):q['mesh_asset']['polygons']['f000000']['uv_layers']['UVMap'][0][0]+=0.01
def integer(q,w):q['mesh_asset']['integer_attributes']['vertices']['capture']['v000000']+=1
def history(q,w):q['mesh_asset']['editing']['history']=[]
def duplicate(q,w):q['mesh_asset']['vertices']['unmapped_duplicate']=q['mesh_asset']['vertices']['v000000'][:]
def normal(q,w):q['normals']['faces'][0]['corner_normals'][0][0]+=0.01
def world(q,w):w['world_vertices']['v000000'][0]+=0.01
def winding(q,w):q['mesh_asset']['polygons']['f000000']['vertices'].reverse()
rows=[]
for mutate in [position,edge,uv,integer,history,duplicate,normal,world,winding]:
    query=copy.deepcopy(base['query']);world_query=copy.deepcopy(base['world']);mutate(query,world_query)
    try:pilot.compare(reference,query,world_query)
    except (AssertionError,ValueError,KeyError) as error:rows.append({'control':mutate.__name__,'rejected':True,'error':str(error)})
    else:raise AssertionError('corruption accepted: '+mutate.__name__)
assert base==raw['after'],'control changed original evidence'
print(json.dumps({'passed':True,'controls':rows,'numeric_limit_changed':False,'source_answers_replaced':False,'product_acceptance':'unrun'},indent=2))

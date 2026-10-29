"""Check frozen native grid inputs and raw channels; no Rust acceptance."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tools'))
from compare_snap_menu_reference import tree, floats
from compare_snap_rotation_reference import matrix, world_point

HERE=Path(__file__).resolve().parent
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
scene=json.loads((HERE/'authored-grid.json').read_text())
authored=json.loads((HERE/'authored-modes.json').read_text())
manifest=json.loads((HERE/'source/manifest.json').read_text())
assert manifest['version']==[5,2,3] and manifest['build_hash']=='e13b728c6880' and manifest['background'] is False
assert manifest['binary_sha256']=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
assert authored['grid_input_sha256']==digest(HERE/'authored-grid.json')
for name,expected in manifest['input_hashes'].items():assert digest(Path(name))==expected,name
assert [r['mode'] for r in manifest['runs']]==[r['object']['mode'] for r in authored['modes']]
records=[]
for row,mode in zip(manifest['runs'],authored['modes']):
    path=HERE/'source'/row['file'];assert digest(path)==row['sha256']
    raw=gzip.decompress(path.read_bytes());assert hashlib.sha256(raw).hexdigest()==row['raw_sha256'] and len(raw)==row['raw_bytes']
    value=json.loads(raw);assert value['authored_rotation']==mode
    assert value['result']=={'status':['FINISHED'],'error':None} and row['status']==['FINISHED']
    assert value['run']['parameters']==authored['parameters']
    before,after=value['before'],value['after']
    old=before['rotation_channels']['target'];expected={**floats(mode['object']),
        'lock_rotation':authored['lock_rotation'],'lock_rotation_w':False,'lock_rotations_4d':True,
        'delta_euler':[0.,0.,0.],'delta_quaternion_wxyz':[1.,0.,0.,0.]}
    tree(expected,old,'authored object channels',0.)
    tree(floats(mode['cursor']),before['cursor_channels'],'authored cursor channels',0.)
    initial=scene['entities']['target']['transform']
    basis=matrix({'location':initial['translation'],'scale':initial['scale']},mode['object'])
    tree(basis,before['objects']['target']['matrix_world'],'authored grid world matrix')
    geometry=before['meshes']['target']['geometry'];asset=scene['mesh_assets']['grid']
    tree(asset['vertices'],geometry['vertices'],'authored grid vertices',0.)
    assert (len(geometry['vertices']),len(geometry['edges']),len(geometry['faces']))==(10201,20200,10000)
    for id,p in asset['vertices'].items():tree(world_point(basis,p),before['meshes']['target']['world_vertices'][id],'authored world vertex')
    tree(before['cursor_channels'],after['cursor_channels'],'unchanged cursor',0.)
    tree(before['objects']['child']['matrix_world'],after['objects']['child']['matrix_world'],'actual child preservation')
    assert before['objects']['child']['matrix_parent_inverse']!=after['objects']['child']['matrix_parent_inverse']
    for key in geometry:
        if key!='vertices':tree(geometry[key],after['meshes']['target']['geometry'][key],'preserved topology/attributes',0.)
    records.append({'mode':row['mode'],'source_case_valid':True})
print(json.dumps({'source_cases_valid':len(records),'source_process_id':manifest['process_id'],
    'product_performance_samples':'unrun','product_acceptance':'unrun','runs':records},indent=2))

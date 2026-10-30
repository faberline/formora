"""Check exact frozen delta grid preparation before any Rust samples pass."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'tools'))
from compare_snap_menu_reference import tree, floats
from compare_snap_rotation_reference import matrix, compose
from compare_snap_delta_reference import delta_matrix, world_point

HERE = Path(__file__).resolve().parent
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

scene = json.loads((HERE/'authored-grid.json').read_text())
authored = json.loads((HERE/'authored-modes.json').read_text())
manifest = json.loads((HERE/'source/manifest.json').read_text())
receipt = json.loads((HERE/'source-terminal.json').read_text())
assert receipt['terminal_exit_code'] == 0 and receipt['process_id'] == manifest['process_id']
assert receipt['manifest_sha256'] == digest(HERE/'source/manifest.json')
assert manifest['version'] == [5,2,3] and manifest['build_hash'] == 'e13b728c6880'
assert manifest['background'] is False
assert manifest['binary_sha256'] == 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
assert authored['grid_input_sha256'] == digest(HERE/'authored-grid.json')
assert (authored['samples_per_mode'], authored['maximum_core_ms'], authored['maximum_pipeline_ms']) == (3,250,2000)
for name, expected in manifest['input_hashes'].items():
    assert digest(Path(name)) == expected, name
assert [r['mode'] for r in manifest['runs']] == [r['object']['mode'] for r in authored['modes']]
records = []
for row, mode in zip(manifest['runs'], authored['modes']):
    path = HERE/'source'/row['file']; assert digest(path) == row['sha256']
    raw = gzip.decompress(path.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes']
    value = json.loads(raw); assert value['authored_rotation'] == mode
    assert value['authored_delta'] == {'target':authored['target_delta'], 'child':authored['child_delta']}
    assert value['result'] == {'status':['FINISHED'], 'error':None} and row['status'] == ['FINISHED']
    assert value['run']['parameters'] == authored['parameters']
    before, after = value['before'], value['after']
    expected = {**floats(mode['object']), 'lock_rotation':authored['lock_rotation'],
        'lock_rotation_w':False, 'lock_rotations_4d':True,
        'delta_euler':floats(authored['target_delta']['euler']),
        'delta_quaternion_wxyz':floats(authored['target_delta']['quaternion_wxyz'])}
    tree(expected, before['rotation_channels']['target'], 'authored target raw channels', 0.)
    tree(floats(mode['cursor']), before['cursor_channels'], 'authored cursor channels', 0.)
    child_rotation = {'mode':'XYZ', 'euler':[0.,0.,0.], 'quaternion_wxyz':[1.,0.,0.,0.], 'axis_angle':[0.,0.,1.,0.]}
    child_channels = {**child_rotation, 'lock_rotation':[False]*3, 'lock_rotation_w':False,
        'lock_rotations_4d':False, 'delta_euler':floats(authored['child_delta']['euler']),
        'delta_quaternion_wxyz':floats(authored['child_delta']['quaternion_wxyz'])}
    tree(child_channels, before['rotation_channels']['child'], 'authored child raw channels', 0.)
    tree({'target':floats(authored['target_delta']), 'child':floats(authored['child_delta'])},
         before['delta_channels'], 'authored deltas', 0.)
    initial = scene['entities']['target']['transform']
    basis = delta_matrix({'location':initial['translation'], 'scale':initial['scale']}, mode['object'], authored['target_delta'])
    for field in ['matrix_basis', 'matrix_local', 'matrix_world']:
        tree(basis, before['objects']['target'][field], 'authored target '+field)
    child = scene['entities']['child']['transform']
    child_basis = delta_matrix({'location':child['translation'], 'scale':child['scale']}, child_rotation, authored['child_delta'])
    tree(child_basis, before['objects']['child']['matrix_basis'], 'authored child basis')
    tree(compose(basis, child_basis), before['objects']['child']['matrix_world'], 'authored child world')
    geometry = before['meshes']['target']['geometry']; asset = scene['mesh_assets']['grid']
    tree(asset['vertices'], geometry['vertices'], 'authored grid vertices', 0.)
    assert (len(geometry['vertices']), len(geometry['edges']), len(geometry['faces'])) == (10201,20200,10000)
    for id, p in asset['vertices'].items():
        tree(world_point(basis,p), before['meshes']['target']['world_vertices'][id], 'authored world vertex')
    tree(before['delta_channels'], after['delta_channels'], 'unchanged deltas', 0.)
    tree(before['cursor_channels'], after['cursor_channels'], 'unchanged cursor', 0.)
    tree(before['objects']['child']['matrix_world'], after['objects']['child']['matrix_world'], 'actual child preservation')
    assert before['objects']['child']['matrix_parent_inverse'] != after['objects']['child']['matrix_parent_inverse']
    for key in geometry:
        if key != 'vertices':
            tree(geometry[key], after['meshes']['target']['geometry'][key], 'preserved topology/attributes', 0.)
    records.append({'mode':row['mode'], 'source_case_valid':True})
print(json.dumps({'source_cases_valid':len(records), 'source_process_id':manifest['process_id'],
    'product_performance_samples':'unrun', 'product_acceptance':'unrun', 'runs':records}, indent=2))

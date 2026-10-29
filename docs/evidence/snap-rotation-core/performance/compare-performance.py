"""Check every saved raw-rotation grid result against its frozen native case."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tools'))
from compare_snap_menu_reference import tree, floats

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['binary','samples','source','controller','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();assert not args.output.exists();binary_sha=sha(args.binary)
    authored=load(Path(__file__).with_name('authored-modes.json'))
    source=load(args.source/'manifest.json');controller=load(args.controller)
    assert source['version']==[5,2,3] and source['build_hash']=='e13b728c6880' and source['background'] is False
    assert source['binary_sha256']=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert source['process_id']==55824 and len(source['runs'])==8
    terminal=load(Path(__file__).with_name('source-terminal.json'))
    assert terminal['terminal_exit_code']==0 and terminal['manifest_sha256']==sha(args.source/'manifest.json')
    assert controller['passed'] and controller['terminal_exit_code']==0 and controller['verification_inputs_unchanged']
    assert controller['binary_sha256']==binary_sha
    for path,digest in controller['input_hashes'].items():assert sha(Path(path))==digest
    for path,digest in source['input_hashes'].items():assert sha(Path(path))==digest
    timing=load(args.samples/'timing-summary.json');assert timing['passed'] and timing['samples']==24 and len(timing['runs'])==24
    assert controller['timing_summary_sha256']==sha(args.samples/'timing-summary.json')
    references={}
    for row in source['runs']:
        path=args.source/row['file'];assert sha(path)==row['sha256'];raw=gzip.decompress(path.read_bytes())
        assert len(raw)==row['raw_bytes'] and hashlib.sha256(raw).hexdigest()==row['raw_sha256']
        value=json.loads(raw);assert value['result']=={'status':['FINISHED'],'error':None}
        assert value['run']['parameters']=={'use_offset':False,'use_rotation':True}
        assert row['mode'] not in references;references[row['mode']]=value
    expected_modes=[r['object']['mode'] for r in authored['modes']]
    assert list(references)==expected_modes
    def query(path,*flags):
        p=subprocess.run([str(args.binary),'scene','inspect','--scene',str(path),*flags],capture_output=True,text=True)
        assert p.returncode==0,(p.returncode,p.stdout,p.stderr)
        return json.loads(p.stdout)
    def compare_state(expected,scene,inspection,worlds,meshes):
        assert expected['sharing']==[['target']] and set(scene['entities'])=={'target','child'}
        for id,entity in scene['entities'].items():
            frame=worlds[id]['object_frames'];transform=entity['transform']
            assert transform['rotation']['kind']=='channels';channels=transform['rotation']['channels']
            actual={'parent':entity['parent'],'location':transform['translation'],'rotation':channels['euler'],
                'rotation_mode':channels['mode'].upper(),'scale':transform['scale'],'matrix_world':worlds[id]['world_matrix'],
                'matrix_basis':frame['matrix_basis'],'matrix_local':frame['matrix_local'],'matrix_parent_inverse':frame['matrix_parent_inverse'],
                'selected':frame['selected'],'mode':'EDIT' if frame['edit_mode'] else 'OBJECT',
                'lock_location':frame['lock_location'],'lock_rotation':frame['lock_rotation']}
            tree({k:expected['objects'][id][k] for k in actual},actual,'frames/'+id)
            raw={**channels,'mode':channels['mode'].upper(),'lock_rotation':frame['lock_rotation'],
                 'lock_rotation_w':frame.get('lock_rotation_w',False),'lock_rotations_4d':frame.get('lock_rotations_4d',False)}
            tree({k:expected['rotation_channels'][id][k] for k in raw},raw,'raw channels/'+id)
        cursor=scene['authoring_context'];raw=cursor['cursor_orientation']
        tree(expected['cursor_channels'],{**raw,'mode':raw['mode'].upper()},'raw cursor')
        tree(expected['cursor']['matrix'],inspection['cursor_matrix'],'actual cursor matrix')
        tree(expected['cursor_metres'],cursor['cursor_location'],'cursor location')
        asset=meshes['grid']['mesh_asset'];assert asset==scene['mesh_assets']['grid']
        native=expected['meshes']['target'];g=native['geometry']
        tree(native['vertices_metres'],asset['vertices'],'grid local geometry')
        tree(native['world_vertices_metres'],worlds['target']['world_vertices'],'grid world geometry')
        assert asset['edges']==g['edges'] and {id:f['vertices'] for id,f in asset['polygons'].items()}==g['faces']
        assert not asset['material_slots'] and not asset.get('uv_layout') and not asset.get('vertex_groups') and not asset.get('vertex_weights')
        assert g['material_slots']==[] and g['uv_layers']=={} and g['uv_layer_order']==[]
        for id,face in asset['polygons'].items():
            assert face['material_slot'] is None and g['face_materials'][id]==0
            assert face['smooth']==g['face_smooth'][id] and not face['uv_layers']
        assert {id:id in asset.get('edge_seams',[]) for id in asset['edges']}==g['edge_seams']
        editing=asset['editing'];assert editing['selected']['vertices']==native['selected']['VERT']
        assert editing['selected']['edges']==native['selected']['EDGE']
        assert [f['id'] for f in editing['selected']['faces']]==native['selected']['FACE']
        normals={'faces':{},'corners':{}}
        for face in meshes['grid']['normals']['faces']:
            assert face['face']['kind']=='polygon';id=face['face']['id'];normals['faces'][id]=face['normal'];normals['corners'][id]=face['corner_normals']
        tree(native['normals'],normals,'resolved grid normals')
    def inspect(path):
        inspection=query(path);scene=inspection['scene']
        return scene,inspection,{id:query(path,'--entity',id,'--world') for id in scene['entities']},
    inputs={}
    for index,mode in enumerate(expected_modes):
        path=args.samples/f'input-{mode}.json';initial=load(path);assert initial['revision']==0
        expected=authored['modes'][index]
        for owner,key in [('target','object')]:
            raw=floats(expected[key]);raw['mode']=raw['mode'].lower()
            assert initial['entities'][owner]['transform']['rotation']=={'kind':'channels','channels':raw}
        cursor=floats(expected['cursor']);cursor['mode']=cursor['mode'].lower()
        assert initial['authoring_context']['cursor_orientation']==cursor
        assert initial['authoring_context']['cursor_rotation']==cursor['euler']
        context=initial['object_context'];assert context['origins_only'] and context['skip_children'] and context['selected']==['target']
        state=context['states']['target'];assert state['lock_rotation']==[True,False,False] and not state.get('lock_rotation_w',False) and state['lock_rotations_4d']
        assert len(initial['mesh_assets'])==1 and len(initial['entities'])==2
        scene,inspection,worlds=inspect(path);meshes={'grid':query(path,'--mesh-asset','grid','--normals')}
        compare_state(references[mode]['before'],scene,inspection,worlds,meshes);inputs[mode]=initial
    records=[];seen=set()
    for row in timing['runs']:
        mode,sample=row['mode'],row['sample'];assert mode in references and sample in [1,2,3] and (mode,sample) not in seen;seen.add((mode,sample))
        assert row['maximum_core_ms']==250. and row['maximum_pipeline_ms']==2000.
        assert row['passed'] and row['core_ms']<=250. and row['operation_save_reload_ms']<=2000.
        for key in ['core_ms','operation_save_reload_ms']:assert math.isfinite(row[key]) and row[key]>=0.
        assert abs(row['core_ms']-(row['core_end_ns']-row['core_start_ns'])/1e6)<1e-9
        assert abs(row['operation_save_reload_ms']-(row['pipeline_end_ns']-row['pipeline_start_ns'])/1e6)<1e-9
        path=args.samples/row['file'];assert path.name==f'{mode}-{sample}.json'
        scene,inspection,worlds=inspect(path);assert scene['revision']==1
        assert scene==load(path) and scene['mesh_assets']['grid']['editing']==inputs[mode]['mesh_assets']['grid']['editing']
        meshes={'grid':query(path,'--mesh-asset','grid','--normals')};compare_state(references[mode]['after'],scene,inspection,worlds,meshes)
        for field in ['materials','doors','annotations','active_camera']:assert scene[field]==inputs[mode][field]
        records.append({'mode':mode,'sample':sample,'passed':True,'source_match':True,'saved_scene_sha256':sha(path),
            'core_ms':row['core_ms'],'pipeline_ms':row['operation_save_reload_ms']})
        print(json.dumps({'compared':len(records),'mode':mode,'sample':sample}),flush=True)
    assert len(records)==24 and sha(args.binary)==binary_sha
    report={'passed':True,'required_full_gate_passed':True,'samples':24,'runs':records,'binary_sha256':binary_sha,
        'source_process_id':source['process_id'],'source_manifest_sha256':sha(args.source/'manifest.json'),
        'controller_sha256':sha(args.controller),'comparison_script_sha256':sha(Path(__file__)),
        'position_normal_matrix_channel_limit':1e-6,'product_acceptance':'unrun'}
    with args.output.open('x') as out:json.dump(report,out,indent=2);out.write('\n')


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Bind all 90 saved outputs to native sources and independent authored input."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tools'))
from compare_snap_menu_reference import tree
from runtime_artifacts import read_json
from scene_snap_runtime_smoke import frame_snapshot
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['binary','samples','source','controller','output']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--diagnostic-failed-timings',action='store_true')
    args=parser.parse_args();assert not args.output.exists()
    source=read_json(args.source/'manifest.json');controller=read_json(args.controller)
    assert source['binary_sha256']=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert source['version']==[5,2,3] and source['build_hash']=='e13b728c6880' and source['background'] is False
    assert source['classes']==3 and source['forms_per_class']==10 and len(source['runs'])==30
    assert type(source['process_id']) is int and source['process_id']>0
    assert controller['samples']==90 and len(controller['groups'])==30
    if not args.diagnostic_failed_timings:assert controller['passed']
    assert controller['verification_inputs_unchanged']
    for path,digest in controller['input_hashes'].items():assert sha(Path(path))==digest
    for path,digest in source['input_hashes'].items():assert sha(Path(path))==digest
    inputs={c:read_json(args.samples/f'input-{c}.json') for c in ['A','B','C']}
    for c in inputs:
        names=[p for p in source['input_hashes'] if p.endswith(f'/input-{c}.json')]
        assert len(names)==1 and source['input_hashes'][names[0]]==sha(args.samples/f'input-{c}.json')
    references={}
    for entry in source['runs']:
        path=args.source/entry['file'];assert sha(path)==entry['sha256'] and entry['status']==['FINISHED']
        key=(entry['class'],entry['form']);assert key not in references
        data=read_json(path);assert data['result']=={'status':['FINISHED'],'error':None}
        initial=inputs[entry['class']];context=initial['object_context'];before=data['before']
        assert before['settings']['grid_spacing']==.75 and before['settings']['pivot']=='MEDIAN_POINT'
        assert before['settings']['origins_only']==context['origins_only'] and before['settings']['skip_children']==context['skip_children']
        assert before['active_object']==context['active']
        for id,entity in initial['entities'].items():
            obj=before['objects'][id];t=entity['transform'];tree(t['translation'],obj['location'],'input location',0.)
            tree(t['rotation']['angles'],obj['rotation'],'input rotation',0.);tree(t['scale'],obj['scale'],'input scale',0.)
            assert obj['parent']==entity['parent'] and obj['selected']==(id in context['selected'])
            assert (obj['mode']=='EDIT')==(id in context['edit_objects'])
        for id,mesh in before['meshes'].items():
            asset=initial['mesh_assets'][initial['entities'][id]['content']['geometry']['id']]
            assert len(asset['vertices'])==10201 and len(asset['edges'])==20200 and len(asset['polygons'])==10000
            tree(asset['vertices'],mesh['vertices_metres'],'input grid positions',0.)
            assert asset['edges']==mesh['geometry']['edges']
            assert {id:p['vertices'] for id,p in asset['polygons'].items()}==mesh['geometry']['faces']
            assert mesh['selected']['VERT']==sorted(asset['vertices'])
            if mesh['data_edit_mode']:assert mesh['history']==[{'domain':'VERT','id':'v010200'}]
        tree(initial['authoring_context']['cursor_location'],before['cursor_metres'],'input cursor',0.)
        references[key]=(entry,data)
    binary_sha=sha(args.binary);records=[]
    def query(path,*flags):
        p=subprocess.run([str(args.binary),'scene','inspect','--scene',str(path),*flags],capture_output=True,text=True)
        assert p.returncode==0,(p.returncode,p.stdout,p.stderr)
        return json.loads(p.stdout)
    for group in controller['groups']:
        assert group['terminal_exit_code'] in [0,1]
        if not args.diagnostic_failed_timings:assert group['passed'] and group['terminal_exit_code']==0
        path=args.samples/group['report'];assert sha(path)==group['report_sha256'];report=read_json(path)
        c,form=group['class'],group['form'];entry,reference=references[(c,form)];initial=inputs[c];expected=reference['after']
        assert len(report['runs'])==3
        if not args.diagnostic_failed_timings:assert report['passed']
        for sample in report['runs']:
            assert sample['class']==c and sample['form']==form and sample['sample'] in [1,2,3]
            assert reference['run']['operator']=='snap_'+sample['action']['kind']
            if sample['action']['kind']=='selected_to_cursor':assert reference['run']['parameters']=={k:sample['action'][k] for k in ['use_offset','use_rotation']}
            for key in ['core_ms','operation_save_reload_ms']:assert math.isfinite(sample[key]) and sample[key]>=0
            assert sample['maximum_core_ms']==(500 if c=='C' else 250)
            assert sample['maximum_pipeline_ms']==(4000 if c=='C' else 2000)
            timing_passed=sample['core_ms']<=sample['maximum_core_ms'] and sample['operation_save_reload_ms']<=sample['maximum_pipeline_ms']
            assert sample['passed']==timing_passed
            if not args.diagnostic_failed_timings:assert timing_passed
            assert abs(sample['core_ms']-(sample['core_end_ns']-sample['core_start_ns'])/1e6)<1e-9
            assert abs(sample['operation_save_reload_ms']-(sample['pipeline_end_ns']-sample['pipeline_start_ns'])/1e6)<1e-9
            saved=args.samples/f'{c}-{form}-{sample["sample"]}.json';actual=read_json(saved)
            assert query(saved)['scene']==actual and actual['revision']==1
            assert actual['materials']==initial['materials'] and actual['doors']==initial['doors'] and actual['annotations']==initial['annotations']
            assert set(actual['entities'])==set(initial['entities']) and set(actual['mesh_assets'])==set(initial['mesh_assets'])
            worlds={id:query(saved,'--entity',id,'--world') for id in actual['entities']}
            for id in actual['entities']:
                frames=frame_snapshot(worlds[id],actual,id)
                tree({k:expected['objects'][id][k] for k in frames},frames,f'{c}/{form}/frames/{id}')
            meshes={id:query(saved,'--mesh-asset',id,'--normals') for id in actual['mesh_assets']}
            for id,source_mesh in expected['meshes'].items():
                asset_id=actual['entities'][id]['content']['geometry']['id'];asset=meshes[asset_id]['mesh_asset'];old=initial['mesh_assets'][asset_id]
                assert asset==actual['mesh_assets'][asset_id]
                tree(source_mesh['vertices_metres'],asset['vertices'],f'{c}/{form}/{id}/local')
                tree(source_mesh['world_vertices_metres'],worlds[id]['world_vertices'],f'{c}/{form}/{id}/world')
                assert asset['edges']==old['edges'] and asset['editing']==old['editing']
                assert asset['material_slots']==old['material_slots'] and asset.get('uv_layout')==old.get('uv_layout')
                assert set(asset['polygons'])==set(old['polygons']) and asset['triangles']==old['triangles']
                for face in old['polygons']:
                    assert {k:v for k,v in asset['polygons'][face].items() if k not in ['normal','corner_normals']}=={k:v for k,v in old['polygons'][face].items() if k not in ['normal','corner_normals']}
                normals={'faces':{},'corners':{}}
                for face in meshes[asset_id]['normals']['faces']:
                    assert face['face']['kind']=='polygon';key=face['face']['id'];normals['faces'][key]=face['normal'];normals['corners'][key]=face['corner_normals']
                tree(source_mesh['normals'],normals,f'{c}/{form}/{id}/normals')
            tree(expected['cursor_metres'],actual['authoring_context']['cursor_location'],f'{c}/{form}/cursor')
            tree(expected['cursor']['rotation'],actual['authoring_context']['cursor_rotation'],f'{c}/{form}/cursor rotation')
            records.append({'class':c,'form':form,'sample':sample['sample'],'passed':timing_passed,'source_match':True,'saved_scene_sha256':sha(saved),'source_sha256':entry['sha256'],'core_ms':sample['core_ms'],'pipeline_ms':sample['operation_save_reload_ms']})
            print(json.dumps({'compared':len(records),'class':c,'form':form,'sample':sample['sample']}),flush=True)
    assert len(records)==90 and len({(r['class'],r['form'],r['sample']) for r in records})==90 and sha(args.binary)==binary_sha
    passed=all(r['passed'] for r in records) and not args.diagnostic_failed_timings
    result={'passed':passed,'required_full_gate_passed':passed,'source_comparisons_passed':True,'diagnostic_failed_timings':args.diagnostic_failed_timings,'samples':90,'binary_sha256':binary_sha,'source_process_id':source['process_id'],'runs':records,
            'positions_absolute_tolerance_metres':1e-6,'normal_absolute_tolerance':1e-6,'matrix_rotation_absolute_tolerance':1e-6,
            'source_manifest_sha256':sha(args.source/'manifest.json'),'controller_sha256':sha(args.controller),'product_acceptance':'unrun','milestone_acceptance':'unrun'}
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':passed,'source_comparisons_passed':True,'samples':90}))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()

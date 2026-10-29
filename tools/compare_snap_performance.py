#!/usr/bin/env python3
"""Check all 30 real saved snap grids against ten fixed native source results."""
import argparse
import json
from pathlib import Path
import subprocess

from compare_snap_menu_reference import digest, load, tree, require

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['binary','samples','source','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'refuse existing performance comparison')
    source=load(args.source/'manifest.json');report=load(args.samples/'report.json');input_scene=load(args.samples/'input.json')
    build=load(ROOT/'baseline/reference/builds/blender-5.2.3/report.json')
    require(source['binary_sha256']==build['files'][build['entry_executable']]['sha256'],'source executable differs')
    require(source['version']==[5,2,3] and source['build_hash']=='e13b728c6880' and source['background'] is False,'source build/context differs')
    require(type(source['process_id']) is int and source['process_id']>0,'source process is missing')
    require(source['forms']==10 and len(source['runs'])==10,'complete source forms required')
    scene_suffix='docs/evidence/mesh-snap-core/performance/samples/input.json'
    scene_inputs=[name for name in source['input_hashes'] if name.endswith('/'+scene_suffix)]
    require(len(scene_inputs)==1,'source authored scene identity differs');original_root=scene_inputs[0][:-len(scene_suffix)]
    for name,sha in source['input_hashes'].items():
        require(name.startswith(original_root),'source input root differs')
        require(digest(ROOT/name[len(original_root):])==sha,'source input content changed')
    require(source['input_hashes'][scene_inputs[0]]==digest(args.samples/'input.json'),'timed input differs from native source input')
    require(report['passed'] and report['profile']=='release' and report['forms']==10 and report['samples_per_form']==3,'fixed release performance failed')
    require((report['vertices'],report['edges'],report['faces'])==(10201,20200,10000) and len(report['runs'])==30,'grid or sample count differs')
    require(len({(r['form'],r['sample']) for r in report['runs']})==30,'duplicate timed sample')
    mesh=input_scene['mesh_assets']['grid'];require(len(mesh['vertices'])==10201 and len(mesh['edges'])==20200 and len(mesh['polygons'])==10000,'authored grid is incomplete')
    references={}
    for entry in source['runs']:
        require(entry['file']==entry['form']+'.json','source path differs');path=args.source/entry['file']
        require(digest(path)==entry['sha256'] and entry['status']==['FINISHED'],'source raw result hash or outcome differs')
        data=load(path);require(data['result']=={'status':['FINISHED'],'error':None},'source action did not finish')
        before=data['before'];g=before['meshes']['target']['geometry']
        tree(mesh['vertices'],g['vertices'],'authored grid positions',0.)
        require(mesh['edges']==g['edges'],'authored grid edges differ')
        require({id:p['vertices'] for id,p in mesh['polygons'].items()}==g['faces'],'authored grid winding differs')
        require(before['meshes']['target']['history']==[{'domain':'VERT','id':'v010200'}],'active grid vertex differs')
        require(before['meshes']['target']['selected']['VERT']==sorted(mesh['vertices']),'grid selection differs')
        require(before['settings']['grid_spacing']==.75 and before['settings']['pivot']=='MEDIAN_POINT','fixed grid/pivot differs')
        tree(input_scene['authoring_context']['cursor_location'],before['cursor_metres'],'authored performance cursor',0.)
        references[entry['form']]=data
    require(set(references)=={r['form'] for r in report['runs']},'timed forms differ from native source')
    records=[];binary_sha=digest(args.binary)
    for sample in report['runs']:
        name=sample['form'];number=sample['sample'];require(number in [1,2,3],'unexpected sample number')
        require(sample['maximum_core_ms']==250 and sample['maximum_pipeline_ms']==2000,'performance limits changed')
        require(sample['core_ms']<=250 and sample['operation_save_reload_ms']<=2000 and sample['passed'],'timing limit failed')
        require(abs(sample['core_ms']-(sample['core_end_ns']-sample['core_start_ns'])/1e6)<1e-9,'core timing record differs')
        require(abs(sample['operation_save_reload_ms']-(sample['pipeline_end_ns']-sample['pipeline_start_ns'])/1e6)<1e-9,'pipeline timing record differs')
        path=args.samples/f'{name}-{number}.json';actual=load(path);source_result=references[name];expected=source_result['after'];expected_mesh=expected['meshes']['target']
        require(source_result['run']['operator']=='snap_'+sample['action']['kind'],'actual source operator differs')
        if sample['action']['kind']=='selected_to_cursor':
            require(source_result['run']['parameters']=={k:sample['action'][k] for k in ['use_offset','use_rotation']},'actual source flags differ')
        q=subprocess.run([str(args.binary),'scene','inspect','--scene',str(path),'--mesh-asset','grid','--normals'],capture_output=True,text=True,check=True)
        query=json.loads(q.stdout);asset=query['mesh_asset'];require(asset==actual['mesh_assets']['grid'],'fresh mesh query differs from saved result')
        tree(expected_mesh['vertices_metres'],asset['vertices'],name+'/local positions')
        w=subprocess.run([str(args.binary),'scene','inspect','--scene',str(path),'--entity','target','--world'],capture_output=True,text=True,check=True)
        world=json.loads(w.stdout);tree(expected_mesh['world_vertices_metres'],world['world_vertices'],name+'/world positions')
        tree(expected['objects']['target']['matrix_world'],world['world_matrix'],name+'/world matrix')
        require(asset['editing']==mesh['editing'] and asset['edges']==mesh['edges'] and actual['entities']==input_scene['entities'],'preserved grid state differs')
        for id,face in mesh['polygons'].items():
            require({k:v for k,v in asset['polygons'][id].items() if k not in ['normal','corner_normals']}==
                    {k:v for k,v in face.items() if k not in ['normal','corner_normals']},'polygon identity or attribute changed')
        normals={'faces':{},'corners':{}}
        for face in query['normals']['faces']:
            require(face['face']['kind']=='polygon','normal face type differs');id=face['face']['id']
            normals['faces'][id]=face['normal'];normals['corners'][id]=face['corner_normals']
        tree(expected_mesh['normals'],normals,name+'/normals')
        tree(expected['cursor_metres'],actual['authoring_context']['cursor_location'],name+'/cursor position')
        tree(expected['cursor']['rotation'],actual['authoring_context']['cursor_rotation'],name+'/cursor rotation')
        maximum=lambda a,b:max(abs(a[id][j]-b[id][j]) for id in a for j in range(3))
        records.append({'form':name,'sample':number,'passed':True,'saved_scene_sha256':digest(path),
            'source_result_sha256':digest(args.source/(name+'.json')),
            'maximum_local_position_error_metres':maximum(expected_mesh['vertices_metres'],asset['vertices']),
            'maximum_world_position_error_metres':maximum(expected_mesh['world_vertices_metres'],world['world_vertices'])})
        print(json.dumps({'compared':len(records),'form':name,'sample':number}),flush=True)
    require(digest(args.binary)==binary_sha,'comparison binary changed')
    result={'passed':True,'samples':30,'forms':10,'source_process_id':source['process_id'],'binary_sha256':binary_sha,
        'positions_absolute_tolerance_metres':1e-6,'normal_absolute_tolerance':1e-6,'runs':records,
        'maximum_core_ms':max(r['core_ms'] for r in report['runs']),
        'maximum_pipeline_ms':max(r['operation_save_reload_ms'] for r in report['runs']),
        'snap_product_acceptance':'unrun','milestone_acceptance':'unrun'}
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='runs'}))


if __name__=='__main__':main()

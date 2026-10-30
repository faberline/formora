"""Compare all thirty saved timed merge results to their frozen native source."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
HERE=ROOT/'docs/evidence/mesh-merge-core/performance'
sys.path.insert(0,str(ROOT/'tools'))
from compare_snap_menu_reference import tree
from runtime_artifacts import read_json, write_json
from selection_runtime_smoke import snapshot as selected_snapshot
from scene_snap_runtime_smoke import frame_snapshot

OUTPUT=Path('/private/tmp/formora-merge-performance-source-02')
SAMPLES=Path('/private/tmp/formora-merge-performance-02/samples')
BINARY=Path('/private/tmp/formora-merge-target-actual185/debug/formora')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
OUTPUT.mkdir(exist_ok=False)
binary_hash=sha(BINARY)
spec=importlib.util.spec_from_file_location('fixed_merge_source',HERE/'check-source.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
resolutions=[]
def relocated_digest(path):
    path=Path(path)
    prefix='/Users/chrischeng/faberlines/formora/'
    if str(path).startswith(prefix):
        relative=str(path)[len(prefix):];actual=ROOT/relative
        if actual.exists():raw=actual.read_bytes();method='same relative file in sparse worktree'
        else:raw=subprocess.check_output(['git','show','98fb2852287dc5f69062ebad65f408b9cf35f741:'+relative],cwd=ROOT);method='identical admitted Git object for omitted sparse path'
        digest=hashlib.sha256(raw).hexdigest();resolutions.append({'captured_path':str(path),'relative_path':relative,'sha256':digest,'resolution':method});return digest
    return sha(path)
checker.digest=relocated_digest
source_report=checker.validate(HERE/'source-02',HERE/'source-02-process/terminal.json')
assert source_report['passed'] and source_report['source_process_id']==76326
source_report['product_code_changed']=True
source_report['scope']='unchanged source checker revalidated after product implementation'
source_report['path_relocations_only']=resolutions
write_json(OUTPUT/'fresh-source-check.json',source_report)
controller=read_json(SAMPLES.parent/'report.json');summary=read_json(SAMPLES/'timing-summary.json')
assert controller['passed'] and controller['terminal_exit_code']==0 and controller['actual_samples']==30 and controller['inputs_unchanged']
assert summary['passed'] and summary['process_id']==controller['native_process_id'] and len(summary['runs'])==30
assert sha(SAMPLES/'authored-grid.json')==sha(HERE/'authored-grid.json')=='e2f1cae31fff704f5730f93a193796bbb3d56832fff3e8c857604823159db97f'
assert sha(SAMPLES/'authored-forms.json')==sha(HERE/'authored-forms.json')
cli_rows=[]
def cli(scene,*flags):
    command=[str(BINARY),'scene','inspect','--scene',str(scene),*flags]
    process=subprocess.run(command,capture_output=True,text=True)
    cli_rows.append({'command':command,'exit':process.returncode,'stdout':process.stdout,'stderr':process.stderr})
    assert process.returncode==0,process.stderr
    return json.loads(process.stdout)
authored=cli(HERE/'authored-grid.json')['scene'];original=authored['mesh_assets']['grid']
source_manifest=read_json(HERE/'source-02/manifest.json');source_rows={row['id']:row for row in source_manifest['runs']}
forms=read_json(HERE/'authored-forms.json')['forms'];records=[]
for form in forms:
    row=source_rows[form['id']];source_path=HERE/'source-02'/row['file'];assert sha(source_path)==row['sha256']
    reference=read_json(source_path)
    for sample in range(1,4):
        stem=f'{form["id"]}-{sample}';path=SAMPLES/(stem+'.json');receipt_path=SAMPLES/(stem+'-receipt.json')
        scene=cli(path)['scene'];assert scene['revision']==1
        assert {key:value for key,value in scene.items() if key not in ['mesh_assets','revision']}=={key:value for key,value in authored.items() if key not in ['mesh_assets','revision']}
        assert set(scene['mesh_assets'])=={'grid'}
        query=cli(path,'--mesh-asset','grid','--normals');asset=query['mesh_asset'];identifier=next(iter(asset['vertices']))
        assert len(asset['vertices'])==1 and not asset.get('edges') and not asset.get('polygons') and not asset['triangles']
        adapted=copy.deepcopy(query);adapted['mesh_asset'].setdefault('edges',{});adapted['mesh_asset'].setdefault('polygons',{})
        selected=selected_snapshot(adapted)
        native_id=next(iter(reference['after']['meshes']['target']['geometry']['vertices']))
        selected['geometry']['vertices']={native_id:asset['vertices'][identifier]}
        selected['groups']['weights']={native_id:asset.get('vertex_weights',{}).get(identifier,{})}
        for field in ['selected','hidden']:selected[field]['VERT']=[native_id if id==identifier else id for id in selected[field]['VERT']]
        selected['history']=[{'domain':entry['domain'],'id':native_id if entry['id']==identifier else entry['id']} for entry in selected['history']]
        attrs=copy.deepcopy(asset['integer_attributes'])
        for values in attrs['vertices'].values():value=values.pop(identifier);values[native_id]=value
        selected['integer_attributes']=attrs
        selected['source_component_ids']={'VERT':attrs['vertices']['formora_v_id'],'EDGE':attrs['edges']['formora_e_id'],'FACE':attrs['polygons']['formora_f_id']}
        selected['normals']={'faces':{},'corners':{}};assert query['normals']['faces']==[]
        selected['active_material_index']=asset.get('active_material_index',0)
        actual_worlds={}
        for id in scene['entities']:
            world=cli(path,'--entity',id,'--world');actual_worlds[id]=world
            frame=frame_snapshot(world,scene,id);tree({key:reference['after']['objects'][id][key] for key in frame},frame,'physical object/'+id)
        for id in ['target','secondary']:
            actual=copy.deepcopy(selected);actual['world_vertices']={native_id:actual_worlds[id]['world_vertices'][identifier]}
            actual['vertices_metres']=actual['geometry']['vertices'];actual['world_vertices_metres']=actual['world_vertices']
            asset_id=scene['entities'][id]['content']['geometry']['id']
            actual['data_edit_mode']=any(scene['entities'][owner]['content'].get('geometry',{}).get('id')==asset_id for owner in scene['object_context']['edit_objects'])
            tree({key:reference['after']['meshes'][id][key] for key in actual},actual,'complete saved merge data/'+id)
        result=read_json(receipt_path);assert result['revision']==1 and len(result['merges'])==1
        receipt=result['merges'][0]
        assert receipt['status']=='finished' and receipt['mesh_asset']=='grid' and receipt['entity']=='target' and receipt['command_index']==0
        assert receipt['method']==form['method'].lower() and receipt['uvs']==form['uvs'] and receipt['shared_instances']==['secondary','target']
        assert receipt['before']=={'vertices':10201,'edges':20200,'faces':10000,'corners':40000}
        assert receipt['after']=={'vertices':1,'edges':0,'faces':0,'corners':0}
        assert set(receipt['removed']['vertices'])==set(original['vertices'])-{identifier} and set(receipt['removed']['edges'])==set(original['edges'])
        assert receipt['removed']['faces']==[{'kind':'polygon','id':id} for id in sorted(original['polygons'])]
        assert not any(receipt['created'].values())
        lineage=receipt['source_to_survivor'];assert lineage['vertices']=={id:identifier for id in original['vertices']} and lineage['edges']=={}
        assert lineage['faces']==[{'source':{'kind':'polygon','id':id},'survivors':[]} for id in sorted(original['polygons'])]
        changed=original['vertices'][identifier]!=asset['vertices'][identifier] or original['vertex_weights'][identifier]!=asset['vertex_weights'][identifier] or any(values[identifier]!=asset['integer_attributes']['vertices'][name][identifier] for name,values in original['integer_attributes']['vertices'].items())
        assert receipt['changed']=={'vertices':[identifier] if changed else [],'edges':[],'faces':[]}
        timed=[r for r in summary['runs'] if r['form']==form['id'] and r['sample']==sample];assert len(timed)==1 and timed[0]['passed']
        records.append({'form':form['id'],'sample':sample,'scene_sha256':sha(path),'receipt_sha256':sha(receipt_path),'source_sha256':sha(source_path),'passed':True})
        write_json(OUTPUT/(stem+'-queries.json'),{'scene':scene,'query':query,'worlds':actual_worlds,'receipt':result})
        print(json.dumps({'form':form['id'],'sample':sample,'source_comparison_passed':True}),flush=True)
assert len(records)==30 and sha(BINARY)==binary_hash
write_json(OUTPUT/'cli-processes.json',cli_rows)
report={'passed':True,'samples':30,'all_30_timing_and_physical_source_results_passed':True,'records':records,'binary_sha256':binary_hash,'source_native_process_id':76326,'source_native_exit':0,'timing_native_process_id':controller['native_process_id'],'timing_native_exit':0,'controller_report_sha256':sha(SAMPLES.parent/'report.json'),'source_check_sha256':sha(OUTPUT/'fresh-source-check.json'),'checker_sha256':sha(Path(__file__)),'limits_changed':False,'retained_177_gate':'unrun','product_acceptance':'unrun','independent_acceptance':'unrun'}
write_json(OUTPUT/'report.json',report);print(json.dumps({key:report[key] for key in ['passed','samples','all_30_timing_and_physical_source_results_passed']}),flush=True)

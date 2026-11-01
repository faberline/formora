#!/usr/bin/env python3
"""Frozen 100k/200k capacity gate, three samples. CI only."""
import json
import os
import platform
import shutil
from pathlib import Path
import sys
import time
from static_usd_runtime import Runner, validate_usd, load, sha, process_usage
from static_usd_pipeline import execute

profile=load(Path(__file__).resolve().parents[1]/'baseline/static-usd-verifier-resources/contract.json')
assert profile['environment']=={'PXR_WORK_THREAD_LIMIT':'1'}
assert 'numpy' not in sys.modules and not any(k=='pxr' or k.startswith('pxr.') for k in sys.modules)
os.environ.update(profile['environment'])

binary=Path(sys.argv[1]).resolve()
if not binary.exists() and binary.with_suffix('.exe').exists(): binary=binary.with_suffix('.exe')
output=Path(sys.argv[2]).resolve(); output.mkdir(parents=True,exist_ok=False)
runner=Runner(output); results=[]
environment={'platform':platform.platform(),'machine':platform.machine(),'cpu_count':os.cpu_count(),'python':sys.version,'binary_sha256':sha(binary),'runner':{k:os.environ.get(k) for k in ['RUNNER_OS','RUNNER_ARCH','ImageOS','ImageVersion']},'verifier_pool_environment':profile['environment'],'disk_bytes':shutil.disk_usage(output)._asdict()}
(output/'environment.json').write_text(json.dumps(environment,indent=2)+'\n')
print(json.dumps({'capacity_environment':environment}),flush=True)
# Fixture construction is outside the clocks. Every point is referenced. Row-valid
# faces span a 1000x100 grid; the 100000th face repeats a valid indexed face with
# a distinct face ID. Exact frozen counts do not depend on exporter output.
for copies in (1,2):
    vertices={f'v{i:06}':[i%1000,i//1000,(i%7)*0.01] for i in range(100000)}
    row_valid=[i for i in range(99000) if i%1000<999]
    # Include the final column/bottom row with alternate triangles so no vertex is isolated.
    candidates=[(i,i+1,i+1000) for i in row_valid]+[(i+1,i+1001,i+1000) for i in row_valid]
    # Spaced sampling of both triangles covers all boundary vertices. Construct
    # the first 50000 cells in two groups, then add unused boundary cells.
    faces=candidates[:99000]
    used={v for f in faces for v in f}
    for f in candidates:
        if any(v not in used for v in f):
            faces.append(f);used.update(f)
    assert len(used)==100000 and len(faces)<=100000
    faces += [candidates[0]]*(100000-len(faces))
    asset={'vertices':vertices,'triangles':{f'f{i:06}':{'vertices':[f'v{v:06}' for v in f],'uv_layers':{},'corner_normals':None,'material_slot':None} for i,f in enumerate(faces)},'material_slots':[]}
    scene={'schema_version':1,'revision':0,'time_seconds':0,'entities':{'root':{'name':'root','parent':None,'transform':{'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]},'content':{'kind':'empty'}}},'mesh_assets':{},'materials':{'stone':{'base_color':[0.3,0.4,0.5,1],'roughness':0.7,'metallic':0}},'doors':{},'annotations':[],'active_camera':None}
    for i in range(copies):
        id=f'mesh_{i}';scene['mesh_assets'][id]=asset
        scene['entities'][id]={'name':id,'parent':'root','transform':{'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]},'content':{'kind':'mesh','geometry':{'kind':'asset','id':id},'material':'stone'}}
    source=output/f'source-{copies}.json';source.write_text(json.dumps(scene,separators=(',',':')))
    for sample in range(3):
        target=output/f'capacity-{copies}-{sample}.usda'
        verify_phases={}
        operation_times={}
        timeline={}
        verifier_pool={}
        def initialize():
            began=time.monotonic_ns()
            from pxr import Usd, UsdGeom, UsdShade, Vt, Work
            import numpy
            # Each sample has a fresh executor worker. Apply the pinned limit
            # in that worker, not only during the first module initialization.
            Work.SetConcurrencyLimit(1)
            verifier_pool.update(effective_limit=Work.GetConcurrencyLimit(),physical_limit=Work.GetPhysicalConcurrencyLimit(),has_concurrency=Work.HasConcurrency())
            assert verifier_pool['effective_limit']==1 and verifier_pool['has_concurrency'] is False,verifier_pool
            operation_times['initialize']=time.monotonic_ns()-began
            timeline['initialize_finished']=time.monotonic_ns()-start
        def export(spawned):
            began=time.monotonic_ns()
            result=runner.run([binary,'scene','export','--scene',source,'--root','root','--format','usda','--output',target],spawned=spawned)
            operation_times['export']=time.monotonic_ns()-began
            timeline['export_finished']=time.monotonic_ns()-start
            return result
        def query(spawned):
            began=time.monotonic_ns()
            reopened=runner.run([binary,'scene','inspect','--scene',source],spawned=spawned)['scene']
            for key,value in scene.items(): assert reopened[key]==value
            # Full equality is complete. Release this large query inside the
            # clock; do not retain it into the next native child process.
            del reopened
            operation_times['reopen_compare']=time.monotonic_ns()-began
            timeline['reopen_finished']=time.monotonic_ns()-start
        def validate():
            began=time.monotonic_ns()
            validate_usd(target,scene,'root',normal_policy='frozen_preview_f32_newell',timings=verify_phases)
            operation_times['usd_compare']=time.monotonic_ns()-began
            timeline['validation_finished']=time.monotonic_ns()-start
        # The clock includes executor/event creation, the first cold module
        # imports, durable export, BOTH complete comparisons and worker joins.
        start=time.monotonic_ns()
        receipt,errors=execute(export,query,initialize,validate)
        verification_error=errors or None
        verifier_usage=process_usage()
        elapsed=time.monotonic_ns()-start
        timeline['all_joined']=elapsed
        item={'copies':copies,'sample':sample,'core_ns':receipt['core_elapsed_ns'],'core_phases_ns':receipt['core_phases_ns'],'pipeline_ns':elapsed,'pipeline_phases_ns':operation_times,'pipeline_timeline_ns':timeline,'source_sha256':sha(source),'usd_sha256':sha(target),'verification_error':verification_error,'normal_policy':'frozen preview f32 sequential Newell, unchanged 1e-6 tolerance'}
        item['passed']=verification_error is None and item['core_ns']<=copies*250000000 and elapsed<=copies*2000000000
        item['verifier_phases_ns']=verify_phases
        item['verifier_usage']=verifier_usage
        item['native_usage']=[x['child_usage'] for x in runner.receipts[-2:]]
        item['verifier_pool']=verifier_pool
        results.append(item)
        (output/'report.json').write_text(json.dumps({'passed':all(x['passed'] for x in results),'samples':results},indent=2)+'\n')
        print(json.dumps(item),flush=True)
assert len(results)==6 and all(x['passed'] for x in results),results

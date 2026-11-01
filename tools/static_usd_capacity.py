#!/usr/bin/env python3
"""Frozen 100k/200k capacity gate, three samples. CI only."""
import json
import os
import platform
from pathlib import Path
import sys
import time
from static_usd_runtime import Runner, validate_usd, load, sha

binary=Path(sys.argv[1]).resolve()
if not binary.exists() and binary.with_suffix('.exe').exists(): binary=binary.with_suffix('.exe')
output=Path(sys.argv[2]).resolve(); output.mkdir(parents=True,exist_ok=False)
runner=Runner(output); results=[]
environment={'platform':platform.platform(),'machine':platform.machine(),'cpu_count':os.cpu_count(),'python':sys.version,'binary_sha256':sha(binary),'runner':{k:os.environ.get(k) for k in ['RUNNER_OS','RUNNER_ARCH','ImageOS','ImageVersion']}}
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
        start=time.monotonic_ns()
        receipt=runner.run([binary,'scene','export','--scene',source,'--root','root','--format','usda','--output',target])
        verification_error=None
        try:
            reopened=runner.run([binary,'scene','inspect','--scene',source])['scene']
            for key,value in scene.items(): assert reopened[key]==value
            validate_usd(target,scene,'root',normal_policy='frozen_preview_f32_newell')
        except (AssertionError,ValueError,KeyError) as problem:
            verification_error=str(problem) or type(problem).__name__
        elapsed=time.monotonic_ns()-start
        item={'copies':copies,'sample':sample,'core_ns':receipt['core_elapsed_ns'],'core_phases_ns':receipt['core_phases_ns'],'pipeline_ns':elapsed,'source_sha256':sha(source),'usd_sha256':sha(target),'verification_error':verification_error,'normal_policy':'frozen preview f32 sequential Newell, unchanged 1e-6 tolerance'}
        item['passed']=verification_error is None and item['core_ns']<=copies*250000000 and elapsed<=copies*2000000000
        results.append(item)
        (output/'report.json').write_text(json.dumps({'passed':all(x['passed'] for x in results),'samples':results},indent=2)+'\n')
        print(json.dumps(item),flush=True)
assert len(results)==6 and all(x['passed'] for x in results),results

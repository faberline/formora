"""Exercise every authored model input with external/file access denied."""
from pathlib import Path
from collections import Counter
import builtins
import io
import json
import math
import subprocess
import sys
from unittest.mock import patch

ROOT=Path('/private/tmp/formora-merge-distance-baseline');sys.path.insert(0,str(ROOT/'tools'))
from generate_merge_distance_complete import complete
from merge_distance_scene_inputs import scene,selection
from merge_distance_parameter_reference import converted
from merge_distance_fan_reference import custom_fans
from merge_distance_cluster_reference import vertex_result

suite=complete();errors=[];normal_assets=0;vertex_models=0;classes=Counter();access=[]
def deny(*args,**kwargs):access.append(str(args[0]));raise AssertionError('model external access')
with patch.object(builtins,'open',deny),patch.object(io,'open',deny),patch.object(subprocess,'Popen',deny):
    for run in suite['runs']:
        try:
            spec=scene(suite,run);conversion=converted(run['parameters']);classes[conversion['classification']]+=1
            for mesh in spec['mesh_assets'].values():
                if mesh.get('custom_corner_normals'):
                    normals=custom_fans(mesh);normal_assets+=1
                    assert all(math.isfinite(x) for face in normals['decoded'].values() for normal in face for x in normal)
            if conversion['classification']!='rejected_no_operation' and conversion.get('native_token')!='nan':
                for owner in spec['object_context']['edit_objects']:
                    mesh=spec['mesh_assets'][spec['data_sharing'][owner]]
                    result=vertex_result(mesh,selection(mesh,spec,True),conversion['parameters']);vertex_models+=1
                    assert all(math.isfinite(x) for point in result['vertices'].values() for x in point)
        except (AssertionError,KeyError,ValueError) as error:
            errors.append({'id':run['id'],'purpose':run['purpose'],'error':str(error)})
result={'input_cases':len(suite['runs']),'model_preflight_passed':not errors,'model_external_access':access,
        'normal_assets':normal_assets,'edited_vertex_models':vertex_models,'argument_classes':dict(classes),
        'errors':errors,'native_execution':'unrun','product_acceptance':'unrun'}
OUT=Path('/private/tmp/formora-distance-complete-model-preflight-25.json')
with OUT.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(result));raise SystemExit(1 if errors else 0)

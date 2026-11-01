#!/usr/bin/env python3
"""Real CLI/MCP authoring and independent OpenUSD validation; run in CI."""
import asyncio
import base64
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('crate', 'rock', 'workbench', 'radio')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    return json.loads(path.read_text())

def near(a, b):
    if isinstance(b, (list, tuple)):
        assert len(a) == len(b), (a, b)
        for x, y in zip(a, b):
            near(x, y)
    else:
        assert math.isfinite(float(a)) and abs(float(a)-float(b)) <= 1e-6, (a, b)

def native_expected(name):
    """Interpret only independently authored explicit setup/edit operations."""
    scene = {'schema_version':1, 'revision':3, 'time_seconds':0.0,
             'entities':{}, 'materials':{}, 'mesh_assets':{}, 'doors':{},
             'active_camera':None, 'annotations':[]}
    b = ROOT/'baseline/static-usd'/name
    for request in (load(b/'create.json'), load(b/'edit.json'), load(ROOT/'baseline/static-usd-pivot'/(name+'.json'))):
        for c in request['commands']:
            op = c['operation']
            if op == 'set_material':
                scene['materials'][c['id']] = copy.deepcopy(c['material'])
            elif op == 'set_mesh_asset':
                scene['mesh_assets'][c['id']] = copy.deepcopy(c['asset'])
            elif op == 'create_entity':
                scene['entities'][c['id']] = copy.deepcopy(c['entity'])
            elif op == 'set_transform':
                scene['entities'][c['id']]['transform']=copy.deepcopy(c['transform'])
            elif op == 'set_mesh_vertices':
                scene['mesh_assets'][c['id']]['vertices'].update(c['positions'])
            else:
                raise AssertionError(op)
    return scene

def prim_id(id):
    return 'id_'+id.encode().hex()

def source_f32_triangle_normals(points):
    """Independent array arithmetic for the frozen preview's flat Newell rule.

    This is input-only f32 arithmetic, not a product-output reference. The
    native preview contract converts positions to f32 before sequential Newell
    accumulation and reciprocal normalization. A f64 cross product defines a
    different rule on translated capacity geometry. Keep both rules distinct.
    """
    import numpy as np
    p=np.asarray(points,dtype=np.float32)
    assert p.ndim==3 and p.shape[1:]==(3,3) and np.isfinite(p).all()
    n=np.zeros((len(p),3),dtype=np.float32)
    for i in range(3):
        a=p[:,(i-1)%3,:];b=p[:,i,:]
        for j in range(3):
            n[:,j]=n[:,j]+(a[:,(j+1)%3]-b[:,(j+1)%3])*(a[:,(j+2)%3]+b[:,(j+2)%3])
    squared=(n[:,0]*n[:,0]+n[:,1]*n[:,1])+n[:,2]*n[:,2]
    assert np.isfinite(squared).all()
    valid=squared>np.float32(1e-35)
    inverse=np.zeros(len(n),dtype=np.float32)
    inverse[valid]=np.float32(1)/np.sqrt(squared[valid])
    n=n*inverse[:,None];n[~valid]=[0,0,1]
    assert np.isfinite(n).all()
    return n

def validate_usd(path, scene, root, normal_policy='independent_f64_cross'):
    from pxr import Usd, UsdGeom, UsdShade
    assert normal_policy in ('independent_f64_cross','frozen_preview_f32_newell')
    stage = Usd.Stage.Open(str(path))
    assert stage and stage.GetDefaultPrim().GetName() == 'Formora'
    assert UsdGeom.GetStageUpAxis(stage) == 'Z'
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1
    expected_nodes = set()
    expected_meshes = set()
    def path_for(id):
        e = scene['entities'][id]
        return (path_for(e['parent']) if e['parent'] else '/Formora')+'/'+prim_id(id)
    for id, e in scene['entities'].items():
        p = stage.GetPrimAtPath(path_for(id)); assert p, id
        expected_nodes.add(str(p.GetPath()))
        assert p.GetAttribute('formora:sourceId').Get() == id
        assert p.GetAttribute('formora:name').Get() == e['name']
        assert p.GetParent().GetPath() == (path_for(e['parent']) if e['parent'] else '/Formora')
        t = e['transform']; assert t['rotation'] == [0,0,0,1] and t['scale'] == [1,1,1]
        m = UsdGeom.Xformable(p).GetLocalTransformation()
        near([list(row) for row in m], [[1,0,0,0],[0,1,0,0],[0,0,1,0],t['translation']+[1]])
        if e['content']['kind'] == 'empty':
            continue
        mesh = UsdGeom.Mesh(stage.GetPrimAtPath(path_for(id)+'/Geometry'))
        assert mesh
        expected_meshes.add(str(mesh.GetPath()))
        a = scene['mesh_assets'][e['content']['geometry']['id']]
        assert mesh.GetPrim().GetAttribute('formora:meshId').Get() == e['content']['geometry']['id']
        ids = sorted(a['vertices']); faces = sorted(a['triangles'])
        assert list(mesh.GetPrim().GetAttribute('formora:vertexIds').Get()) == ids
        assert list(mesh.GetPrim().GetAttribute('formora:faceIds').Get()) == faces
        assert list(mesh.GetPrim().GetAttribute('formora:faceKinds').Get()) == ['triangle']*len(faces)
        near(list(mesh.GetPointsAttr().Get()), [a['vertices'][v] for v in ids])
        index_by_id={v:i for i,v in enumerate(ids)}
        indices = [index_by_id[v] for f in faces for v in a['triangles'][f]['vertices']]
        assert list(mesh.GetFaceVertexCountsAttr().Get()) == [3]*len(faces)
        assert list(mesh.GetFaceVertexIndicesAttr().Get()) == indices
        assert mesh.GetSubdivisionSchemeAttr().Get() == 'none'
        assert mesh.GetOrientationAttr().Get() == 'rightHanded'
        assert mesh.GetDoubleSidedAttr().Get() is False
        assert mesh.GetNormalsInterpolation() == 'faceVarying'
        normals = list(mesh.GetNormalsAttr().Get()); assert len(normals) == len(indices)
        if normal_policy=='frozen_preview_f32_newell':
            import numpy as np
            input_points=np.array([[a['vertices'][v] for v in a['triangles'][f]['vertices']] for f in faces],dtype=np.float32)
            expected_normals=source_f32_triangle_normals(input_points)
            actual_normals=np.asarray(normals,dtype=np.float64).reshape(len(faces),3,3)
            delta=np.abs(actual_normals-expected_normals[:,None,:])
            assert np.isfinite(actual_normals).all() and (delta<=1e-6).all(),('f32 Newell normal mismatch',float(delta.max()))
        else:
            for i, f in enumerate(faces):
                points = [a['vertices'][v] for v in a['triangles'][f]['vertices']]
                ab = [points[1][j]-points[0][j] for j in range(3)]
                ac = [points[2][j]-points[0][j] for j in range(3)]
                n = [ab[(j+1)%3]*ac[(j+2)%3]-ab[(j+2)%3]*ac[(j+1)%3] for j in range(3)]
                length = math.sqrt(sum(v*v for v in n)); n = [v/length for v in n]
                for k in range(3): near(normals[3*i+k], n)
        material, _ = UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial()
        mat_id = e['content']['material']
        assert material and material.GetPrim().GetAttribute('formora:sourceId').Get() == mat_id
        surface = UsdShade.Shader(material.GetPrim().GetChild('Surface'))
        expected = scene['materials'][mat_id]
        assert surface.GetIdAttr().Get() == 'UsdPreviewSurface'
        near(surface.GetInput('diffuseColor').Get(), expected['base_color'][:3])
        for key, value in [('roughness',expected['roughness']),('metallic',expected['metallic']),('opacity',expected['base_color'][3])]:
            near(surface.GetInput(key).Get(), value)
    assert {str(p.GetPath()) for p in stage.Traverse() if p.GetAttribute('formora:sourceId') and p.IsA(UsdGeom.Xform)} == expected_nodes
    assert {str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)} == expected_meshes
    return {'meshes':len(expected_meshes),'entities':len(expected_nodes)}

def verify_mcp_receipt(receipt,binary,scene):
    assert isinstance(receipt,dict),'missing actual process receipt'
    assert type(receipt.get('pid')) is int and receipt['pid']>0
    assert receipt.get('waited') is True and type(receipt.get('exit_code')) is int and receipt['exit_code']==0
    assert receipt.get('command')==[str(binary),'mcp','--scene',str(scene)]
    assert receipt.get('binary_sha256')==sha(binary)
    assert type(receipt.get('elapsed_ns')) is int and receipt['elapsed_ns']>=0

def process_controls(actual,binary,scene):
    verify_mcp_receipt(actual,binary,scene)
    for bad in (None,{}, {**actual,'exit_code':1},{**actual,'waited':False},
                {**actual,'exit_code':False},{**actual,'pid':0},{**actual,'binary_sha256':'0'*64},
                {**actual,'command':['echo','pretend']},{**actual,'elapsed_ns':None}):
        try:verify_mcp_receipt(bad,binary,scene)
        except AssertionError:pass
        else:raise AssertionError('accepted failed/missing/foreign process receipt')

class Runner:
    def __init__(self, output):
        self.output = output
        self.receipts = []
    def run(self, args, stdin=None, fail=False):
        start = time.monotonic_ns()
        p = subprocess.Popen([str(x) for x in args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        timed_out=False
        try:
            stdout, stderr = p.communicate(None if stdin is None else json.dumps(stdin), timeout=120)
        except subprocess.TimeoutExpired:
            timed_out=True
            p.terminate()
            try:
                stdout,stderr=p.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                stdout,stderr=p.communicate(timeout=10)
        receipt = {'command':[str(x) for x in args], 'pid':p.pid, 'waited':True, 'exit_code':p.returncode,
                   'elapsed_ns':time.monotonic_ns()-start, 'timed_out':timed_out,'stdout':stdout, 'stderr':stderr}
        # Large actual query results stay complete in separate files, with hashes
        # in the process ledger. Rewriting all prior 40 MiB query strings for each
        # process would measure ledger amplification rather than the fixed pipeline.
        for stream in ('stdout','stderr'):
            raw=receipt[stream].encode()
            file=self.output/('process-'+str(len(self.receipts))+'-'+stream+'.txt')
            file.write_bytes(raw)
            receipt[stream+'_file']=file.name
            receipt[stream+'_sha256']=hashlib.sha256(raw).hexdigest()
            if len(raw)>32768:receipt[stream]='[complete bytes in '+file.name+']'
        self.receipts.append(receipt)
        (self.output/'processes.json').write_text(json.dumps(self.receipts,indent=2)+'\n')
        assert not timed_out and p.returncode==(1 if fail else 0), receipt
        return json.loads(stdout)

async def run(binary, output):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from jsonschema import Draft202012Validator
    output.mkdir(parents=True, exist_ok=False)
    runner = Runner(output)
    results = []
    bundle = {}
    for name in MODELS:
        expected = native_expected(name)
        reference = load(ROOT/'baseline/static-usd'/name/'expected.json')
        previous_usd = None
        for interface in ('cli','official_mcp_sdk'):
            folder = output/(interface+'-'+name); folder.mkdir()
            scene = folder/'scene.json'; usd = folder/(name+'.usda')
            def cli(action,*args,**kwargs):
                return runner.run([binary,'scene',action,'--scene',scene,*args],**kwargs)
            cli('init')
            if interface == 'cli':
                for step in ('create','edit'):
                    cli('apply','--request',ROOT/'baseline/static-usd'/name/(step+'.json'))
                cli('apply','--request',ROOT/'baseline/static-usd-pivot'/(name+'.json'))
                before = scene.read_bytes()
                receipt = cli('export','--root',name,'--format','usda','--output',usd)
                transfer={'scene':json.loads(before),'scene_utf8':before.decode('utf8'),'usda':usd.read_text(),'reference':reference,'export_receipt':receipt}
                packed=gzip.compress(json.dumps(transfer,sort_keys=True).encode(),mtime=0)
                print('FORMORA_STATIC_ASSET_'+name.upper()+'='+base64.b64encode(packed).decode(),flush=True)
                cli('export','--root',name,'--format','usda','--output',usd,fail=True)
                cli('export','--root',name,'--format','glb','--output',folder/'no.glb',fail=True)
                cli('export','--root',name,'--format','usda','--output',folder/'missing'/'no.usda',fail=True)
                assert not (folder/'no.glb').exists() and not (folder/'missing'/'no.usda').exists()
            else:
                process_receipt=folder/'mcp-process.json'
                params = StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools/mcp_process_receipt.py'),str(process_receipt),str(binary),'mcp','--scene',str(scene)])
                async with stdio_client(params) as (reader, writer):
                    async with ClientSession(reader,writer,read_timeout_seconds=60) as client:
                        await client.initialize()
                        tools = await client.list_tools()
                        schema = next(t.input_schema for t in tools.tools if t.name == 'scene_export')
                        Draft202012Validator.check_schema(schema)
                        for step in ('create','edit'):
                            result = await client.call_tool('scene_apply',load(ROOT/'baseline/static-usd'/name/(step+'.json')))
                            assert not result.is_error, result
                        pivot=await client.call_tool('scene_apply',load(ROOT/'baseline/static-usd-pivot'/(name+'.json')))
                        assert not pivot.is_error,pivot
                        before = scene.read_bytes()
                        args = {'root':name,'format':'usda','output':str(usd)}
                        Draft202012Validator(schema).validate(args)
                        result = await client.call_tool('scene_export',args)
                        assert not result.is_error, result
                        receipt = result.structured_content
                        again = await client.call_tool('scene_export',args); assert again.is_error
                        invalid = await client.call_tool('scene_export',{**args,'format':'usdz','output':str(folder/'no.usdz')}); assert invalid.is_error
                receipt_record=load(process_receipt)
                process_controls(receipt_record,binary,scene)
                # stdio context has awaited the actual server process. The new
                # CLI below must acquire its writer lock again, not merely inspect.
                cli('apply','--request','-',stdin={'expected_revision':3,'commands':[]},fail=True)
            assert scene.read_bytes() == before and sha(usd) == receipt['sha256']
            actual = cli('inspect')['scene']; assert actual == expected, (name,actual)
            assert actual['mesh_assets'][reference['edited_mesh_id']]['vertices']['v0'] == reference['edited_vertex']
            assert actual['materials'][reference['edited_material_id']] == reference['edited_material']
            assert receipt['revision']==actual['revision']==3
            counts = validate_usd(usd,expected,name)
            editable_scene=folder/'editable-reopen.json';editable_scene.write_bytes(before)
            editable=copy.deepcopy(expected);editable['revision']=4
            mesh_id=reference['edited_mesh_id'];material_id=reference['edited_material_id']
            moved=list(editable['mesh_assets'][mesh_id]['vertices']['v0']);moved[0]+=.005
            editable['mesh_assets'][mesh_id]['vertices']['v0']=moved
            editable['materials'][material_id]['roughness']=.68
            third={'expected_revision':3,'commands':[
                {'operation':'set_mesh_vertices','id':mesh_id,'positions':{'v0':moved}},
                {'operation':'set_material','id':material_id,'material':editable['materials'][material_id]}]}
            runner.run([binary,'scene','apply','--scene',editable_scene,'--request','-'],stdin=third)
            assert runner.run([binary,'scene','inspect','--scene',editable_scene])['scene']==editable
            if previous_usd is not None: assert usd.read_bytes() == previous_usd
            previous_usd = usd.read_bytes()
            results.append({'model':name,'interface':interface,'scene_sha256':sha(scene),'usd_sha256':sha(usd),**counts})
            if interface == 'cli':
                bundle[name] = {'scene':json.loads(before),'scene_utf8':before.decode('utf8'),'usda':usd.read_text(),'reference':reference}
        # Semantic corruption controls. No candidate-generated reference answers.
        from pxr import Usd, UsdGeom, UsdShade, Sdf
        for kind in ('axis','unit','material','geometry','hierarchy'):
            path = output/(name+'-wrong-'+kind+'.usda'); path.write_bytes(previous_usd)
            stage = Usd.Stage.Open(str(path)); child=next(id for id,e in expected['entities'].items() if e['content']['kind']=='mesh')
            base='/Formora/'+prim_id(name)+'/'+prim_id(child)
            if kind == 'axis': UsdGeom.SetStageUpAxis(stage,'Y')
            if kind == 'unit': UsdGeom.SetStageMetersPerUnit(stage,.01)
            if kind == 'geometry': stage.RemovePrim(base+'/Geometry')
            if kind == 'material':
                mat = expected['entities'][child]['content']['material']
                UsdShade.Shader(stage.GetPrimAtPath('/Formora/Materials/'+prim_id(mat)+'/Surface')).GetInput('roughness').Set(.123)
            if kind == 'hierarchy':
                edit = Sdf.BatchNamespaceEdit(); edit.Add(base,'/Formora/'+prim_id(child)); assert stage.GetRootLayer().Apply(edit)
            stage.GetRootLayer().Save(); del stage
            try: validate_usd(path,expected,name)
            except AssertionError: pass
            else: raise AssertionError('missed corruption: '+kind)
    manifest={'passed':True,'binary_sha256':sha(binary),'results':results,'required_capacity':'unrun','native_gpu':'unrun','apple_loader':'unrun','full_gate_passed':False}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Small complete transfer bundle lives in logs, without a paid artifact store.
    packed=gzip.compress(json.dumps(bundle,sort_keys=True).encode(),mtime=0)
    print('FORMORA_STATIC_BUNDLE_SHA256='+hashlib.sha256(packed).hexdigest(),flush=True)
    print('FORMORA_STATIC_BUNDLE_BASE64='+base64.b64encode(packed).decode(),flush=True)
    print(json.dumps(manifest),flush=True)

if __name__ == '__main__':
    binary = Path(sys.argv[1]).resolve()
    if not binary.exists() and binary.with_suffix('.exe').exists(): binary=binary.with_suffix('.exe')
    asyncio.run(run(binary,Path(sys.argv[2]).resolve()))

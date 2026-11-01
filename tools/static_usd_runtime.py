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
    if isinstance(a, (list, tuple)) or hasattr(a, '__iter__') and not isinstance(a, (str, dict)):
        assert len(a) == len(b), (a, b)
        for x, y in zip(a, b):
            near(x, y)
    else:
        assert math.isfinite(float(a)) and abs(float(a)-float(b)) <= 1e-6, (a, b)

def native_expected(name):
    """Interpret only independently authored explicit setup/edit operations."""
    scene = {'schema_version':1, 'revision':2, 'time_seconds':0.0,
             'entities':{}, 'materials':{}, 'mesh_assets':{}, 'doors':{},
             'active_camera':None, 'annotations':[]}
    b = ROOT/'baseline/static-usd'/name
    for request in (load(b/'create.json'), load(b/'edit.json')):
        for c in request['commands']:
            op = c['operation']
            if op == 'set_material':
                scene['materials'][c['id']] = copy.deepcopy(c['material'])
            elif op == 'set_mesh_asset':
                scene['mesh_assets'][c['id']] = copy.deepcopy(c['asset'])
            elif op == 'create_entity':
                scene['entities'][c['id']] = copy.deepcopy(c['entity'])
            elif op == 'set_mesh_vertices':
                scene['mesh_assets'][c['id']]['vertices'].update(c['positions'])
            else:
                raise AssertionError(op)
    return scene

def prim_id(id):
    return 'id_'+id.encode().hex()

def validate_usd(path, scene, root):
    from pxr import Usd, UsdGeom, UsdShade
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
        indices = [ids.index(v) for f in faces for v in a['triangles'][f]['vertices']]
        assert list(mesh.GetFaceVertexCountsAttr().Get()) == [3]*len(faces)
        assert list(mesh.GetFaceVertexIndicesAttr().Get()) == indices
        assert mesh.GetSubdivisionSchemeAttr().Get() == 'none'
        assert mesh.GetOrientationAttr().Get() == 'rightHanded'
        assert mesh.GetDoubleSidedAttr().Get() is False
        assert mesh.GetNormalsInterpolation() == 'faceVarying'
        normals = list(mesh.GetNormalsAttr().Get()); assert len(normals) == len(indices)
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

class Runner:
    def __init__(self, output):
        self.output = output
        self.receipts = []
    def run(self, args, stdin=None, fail=False):
        start = time.monotonic_ns()
        p = subprocess.Popen([str(x) for x in args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = p.communicate(None if stdin is None else json.dumps(stdin), timeout=120)
        receipt = {'command':[str(x) for x in args], 'pid':p.pid, 'waited':True, 'exit_code':p.returncode,
                   'elapsed_ns':time.monotonic_ns()-start, 'stdout':stdout, 'stderr':stderr}
        self.receipts.append(receipt)
        (self.output/'processes.json').write_text(json.dumps(self.receipts,indent=2)+'\n')
        assert bool(p.returncode) == fail, receipt
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
                before = scene.read_bytes()
                receipt = cli('export','--root',name,'--format','usda','--output',usd)
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
                        before = scene.read_bytes()
                        args = {'root':name,'format':'usda','output':str(usd)}
                        Draft202012Validator(schema).validate(args)
                        result = await client.call_tool('scene_export',args)
                        assert not result.is_error, result
                        receipt = result.structured_content
                        again = await client.call_tool('scene_export',args); assert again.is_error
                        invalid = await client.call_tool('scene_export',{**args,'format':'usdz','output':str(folder/'no.usdz')}); assert invalid.is_error
                receipt_record=load(process_receipt)
                assert receipt_record['pid']>0 and receipt_record['waited'] is True and receipt_record['exit_code']==0, receipt_record
                # stdio context has awaited the actual server process. The new
                # CLI below must acquire its writer lock again, not merely inspect.
                cli('apply','--request','-',stdin={'expected_revision':2,'commands':[]},fail=True)
            assert scene.read_bytes() == before and sha(usd) == receipt['sha256']
            actual = cli('inspect')['scene']; assert actual == expected, (name,actual)
            assert actual['mesh_assets'][reference['edited_mesh_id']]['vertices']['v0'] == reference['edited_vertex']
            assert actual['materials'][reference['edited_material_id']] == reference['edited_material']
            counts = validate_usd(usd,expected,name)
            if previous_usd is not None: assert usd.read_bytes() == previous_usd
            previous_usd = usd.read_bytes()
            results.append({'model':name,'interface':interface,'scene_sha256':sha(scene),'usd_sha256':sha(usd),**counts})
            if interface == 'cli':
                bundle[name] = {'scene':json.loads(before),'usda':usd.read_text(),'reference':reference}
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

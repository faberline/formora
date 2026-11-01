#!/usr/bin/env python3
"""Independent old triangle fixture: UVs, normals, face bindings and signed transform."""
import asyncio
import json
import math
from pathlib import Path
import sys
from static_usd_runtime import Runner, load, near, prim_id, sha, process_controls

ROOT=Path(__file__).resolve().parents[1]
async def run(binary,output):
    from pxr import Usd,UsdGeom,UsdShade,Gf
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    output.mkdir(parents=True,exist_ok=False);runner=Runner(output)
    asset=load(ROOT/'tests/fixtures/triangle-asset.json')
    identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
    transform={'translation':[.125,-.25,.5],'rotation':[0,0,math.sqrt(.5),math.sqrt(.5)],'scale':[-1,2,.5]}
    request={'expected_revision':0,'commands':[
        {'operation':'set_material','id':'red','material':{'base_color':[1,0,0,1],'roughness':.25,'metallic':0}},
        {'operation':'set_material','id':'fallback','material':{'base_color':[.1,.2,.3,1],'roughness':.75,'metallic':.5}},
        {'operation':'set_mesh_asset','id':'fixture','asset':asset},
        {'operation':'create_entity','id':'root','entity':{'name':'Root \\"','parent':None,'transform':identity,'content':{'kind':'empty'}}},
        {'operation':'create_entity','id':'child','entity':{'name':'child','parent':'root','transform':transform,'content':{'kind':'mesh','geometry':{'kind':'asset','id':'fixture'},'material':'fallback'}}}]}
    for interface in ('cli','official_mcp_sdk'):
        folder=output/interface;folder.mkdir();scene=folder/'scene.json';usd=folder/'attribute.usda'
        runner.run([binary,'scene','init','--scene',scene])
        if interface=='cli':
            runner.run([binary,'scene','apply','--scene',scene,'--request','-'],stdin=request)
            before=scene.read_bytes()
            receipt=runner.run([binary,'scene','export','--scene',scene,'--root','root','--format','usda','--output',usd])
        else:
            record=folder/'mcp-process.json';params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools/mcp_process_receipt.py'),str(record),str(binary),'mcp','--scene',str(scene)])
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer) as client:
                    await client.initialize();applied=await client.call_tool('scene_apply',request);assert not applied.is_error
                    before=scene.read_bytes();result=await client.call_tool('scene_export',{'root':'root','format':'usda','output':str(usd)});assert not result.is_error;receipt=result.structured_content
            process_controls(load(record),binary,scene)
        assert scene.read_bytes()==before and sha(usd)==receipt['sha256']
        stage=Usd.Stage.Open(str(usd));base='/Formora/'+prim_id('root')+'/'+prim_id('child');mesh=UsdGeom.Mesh(stage.GetPrimAtPath(base+'/Geometry'));assert mesh
        ids=sorted(asset['vertices']);faces=sorted(asset['triangles'])
        near(list(mesh.GetPointsAttr().Get()),[asset['vertices'][v] for v in ids])
        assert list(mesh.GetFaceVertexCountsAttr().Get())==[3,3,3]
        assert list(mesh.GetFaceVertexIndicesAttr().Get())==[ids.index(v) for f in faces for v in asset['triangles'][f]['vertices']]
        near(list(mesh.GetNormalsAttr().Get()),[[0,0,1]]*9)
        for layer in ('Detail','UVMap'):
            name='st' if layer=='Detail' else prim_id(layer)
            attribute=UsdGeom.PrimvarsAPI(mesh).GetPrimvar(name)
            assert attribute.GetInterpolation()=='faceVarying'
            near(list(attribute.Get()),[uv for f in faces for uv in asset['triangles'][f]['uv_layers'][layer]])
        actual_world=UsdGeom.XformCache().GetLocalToWorldTransform(mesh.GetPrim())
        for p in asset['vertices'].values():near(list(actual_world.Transform(Gf.Vec3d(*p))),[-2*p[1]+.125,-p[0]-.25,.5*p[2]+.5])
        bindings={}
        for subset in UsdShade.MaterialBindingAPI(mesh).GetMaterialBindSubsets():
            material,_=UsdShade.MaterialBindingAPI(subset).ComputeBoundMaterial();mid=material.GetPrim().GetAttribute('formora:sourceId').Get()
            for index in subset.GetIndicesAttr().Get():assert index not in bindings;bindings[index]=mid
        assert bindings=={0:'red',1:'fallback',2:'fallback'},bindings
    print(json.dumps({'passed':True,'interfaces':2,'scope':'frozen triangle UV/normal/material-slot fixture and independently specified signed affine transform'}),flush=True)
if __name__=='__main__':
    binary=Path(sys.argv[1]).resolve()
    if not binary.exists() and binary.with_suffix('.exe').exists():binary=binary.with_suffix('.exe')
    asyncio.run(run(binary,Path(sys.argv[2]).resolve()))

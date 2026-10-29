#!/usr/bin/env python3
"""Capture eight frozen raw-rotation grid cases before Rust implementation."""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

import bpy

ROOT=Path(__file__).resolve().parents[4]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
GRID_PATH=ROOT/'docs/evidence/scene-snap-core/performance/blender-grid-reference.py'
ROTATION_PATH=ROOT/'tools/blender_snap_rotation_reference.py'
grid=module('fixed_grid',GRID_PATH);rotation=module('fixed_rotation',ROTATION_PATH)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture(args):
    assert not bpy.app.background and list(bpy.app.version)==[5,2,3] and bpy.app.build_hash.decode()=='e13b728c6880'
    assert digest(bpy.app.binary_path)=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert not args.output.exists()
    stage=args.output.with_name(args.output.name+'.staging');assert not stage.exists()
    here=Path(__file__).resolve().parent
    paths=[here/'authored-grid.json',here/'authored-modes.json',Path(__file__),GRID_PATH,ROTATION_PATH,
           grid.ADAPTER,grid.snap.ADAPTER,grid.snap.transform.BASE_PATH,
           ROOT/'docs/contracts/snap-rotation-core.md',ROOT/'baseline/fixtures/snap-menu.json',
           ROOT/'tools/generate_snap_rotation_cases.py']
    hashes={str(p.resolve()):digest(p) for p in paths}
    scene=json.loads((here/'authored-grid.json').read_text());modes=json.loads((here/'authored-modes.json').read_text())
    assert modes['grid_input_sha256']==digest(here/'authored-grid.json')
    assert len(modes['modes'])==8 and modes['samples_per_mode']==3
    assert (modes['maximum_core_ms'],modes['maximum_pipeline_ms'])==(250,2000)
    suite=json.loads((ROOT/'baseline/fixtures/snap-menu.json').read_text())
    suite['mesh']=grid.mesh_input(scene['mesh_assets']['grid'])
    stage.mkdir(parents=True);records=[]
    for authored in modes['modes']:
        mode=authored['object']['mode'];assert authored['cursor']['mode']==mode
        run=copy.deepcopy(suite['runs'][0]);run.update(id=mode,operator=modes['operation'],parameters=modes['parameters'],
            feature='scene.snap_selected_to_cursor',label='fixed raw rotation grid',mode='OBJECT')
        run['seed']['indices']=list(range(10201));run['context'].update(grid_spacing=.75,unit_system='NONE',unit_scale_length=1.,
            lock_rotation=modes['lock_rotation'],origins_only=True,skip_children=True)
        objects,area,region=grid.create(suite,run,scene)
        assert set(objects)=={'target','child'}
        rotation.assign(objects['target'],authored['object'])
        rotation.assign(objects['child'],{'mode':'XYZ','euler':[0.,0.,0.],
            'quaternion_wxyz':[1.,0.,0.,0.],'axis_angle':[0.,0.,1.,0.]})
        objects['target'].lock_rotation=modes['lock_rotation']
        objects['target'].lock_rotation_w=modes['lock_rotation_w']
        objects['target'].lock_rotations_4d=modes['lock_rotations_4d']
        rotation.assign(bpy.context.scene.cursor,authored['cursor']);bpy.context.view_layer.update()
        before=rotation.snapshot(objects,area,run)
        with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):
            op=getattr(bpy.ops.view3d,run['operator']);assert op.poll()
            try:result={'status':sorted(op(**copy.deepcopy(run['parameters']))),'error':None}
            except RuntimeError as error:result={'status':['ERROR'],'error':str(error)}
        bpy.context.view_layer.update();after=rotation.snapshot(objects,area,run)
        value={'authored_rotation':authored,'run':run,'before':before,'after':after,'result':result}
        raw=(json.dumps(value,allow_nan=False,separators=(',',':'))+'\n').encode();payload=gzip.compress(raw,mtime=0)
        assert gzip.decompress(payload)==raw
        file=mode+'.json.gz'
        with (stage/file).open('xb') as out:out.write(payload)
        records.append({'mode':mode,'file':file,'sha256':digest(stage/file),'raw_sha256':hashlib.sha256(raw).hexdigest(),
                        'raw_bytes':len(raw),'status':result['status']})
        print(json.dumps({'captured_mode':mode,'status':result['status']}),flush=True)
    assert all(r['status']==['FINISHED'] for r in records),'required source case did not finish'
    assert hashes=={str(p.resolve()):digest(p) for p in paths},'authored capture input changed'
    with (stage/'manifest.json').open('x') as out:
        json.dump({'version':list(bpy.app.version),'build_hash':bpy.app.build_hash.decode(),
            'binary_sha256':digest(bpy.app.binary_path),'process_id':os.getpid(),'background':bpy.app.background,
            'command_line':sys.argv,'input_hashes':hashes,'runs':records,'product_acceptance':'unrun'},out,indent=2);out.write('\n')
    stage.rename(args.output)
    print(json.dumps({'captured_modes':8,'required_product_samples':24,'product_acceptance':'unrun'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    def start():
        try:capture(args)
        except BaseException:
            traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
        sys.stdout.flush();sys.stderr.flush();os._exit(0)
    bpy.app.timers.register(start,first_interval=.5)

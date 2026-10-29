#!/usr/bin/env python3
"""Capture authored rotation snap cases in a fixed native viewport process."""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import traceback

import bpy

ADAPTER = Path(__file__).with_name('blender_snap_menu_reference.py')
spec = importlib.util.spec_from_file_location('snap_reference', ADAPTER)
snap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snap)
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    with path.open('xb') as output:
        output.write(raw)


def assign(item, authored):
    # Set mode first: its RNA setter can convert existing channels. Then set
    # every channel explicitly. No previous case can supply inactive data.
    item.rotation_mode = authored['mode']
    item.rotation_quaternion = authored['quaternion_wxyz']
    item.rotation_axis_angle = authored['axis_angle']
    item.rotation_euler = authored['euler']


def rotation(item, locks=False):
    value = {'mode': item.rotation_mode, 'euler': list(item.rotation_euler),
             'quaternion_wxyz': list(item.rotation_quaternion), 'axis_angle': list(item.rotation_axis_angle)}
    if locks:
        value.update(lock_rotation=list(item.lock_rotation), lock_rotation_w=item.lock_rotation_w,
                     lock_rotations_4d=item.lock_rotations_4d,
                     delta_quaternion_wxyz=list(item.delta_rotation_quaternion),
                     delta_euler=list(item.delta_rotation_euler))
    return value


def create(suite, run):
    objects, area, region = snap.create(suite, run)
    for name, item in objects.items():
        if name in ['target', 'secondary']:
            assign(item, run['rotations']['objects'])
            item.lock_rotation = run['context']['lock_rotation']
            item.lock_rotation_w = run['rotations']['lock_rotation_w']
            item.lock_rotations_4d = run['rotations']['lock_rotations_4d']
        else:
            angles = suite['object_inputs']['child']['rotation'] if name=='child' else suite['profiles'][run['context']['profile']]['parent']['rotation']
            assign(item, {'mode': 'XYZ', 'euler': angles, 'quaternion_wxyz': [1.,0.,0.,0.], 'axis_angle': [0.,0.,1.,0.]})
            item.lock_rotation = [False]*3
            item.lock_rotation_w = False
            item.lock_rotations_4d = False
        item.delta_location = [0.,0.,0.]
        item.delta_rotation_euler = [0.,0.,0.]
        item.delta_rotation_quaternion = [1.,0.,0.,0.]
        item.delta_scale = [1.,1.,1.]
    assign(bpy.context.scene.cursor, run['rotations']['cursor'])
    bpy.context.view_layer.update()
    return objects, area, region


def snapshot(objects, area, run):
    state = snap.snapshot(objects, area, run)
    state['rotation_channels'] = {name: rotation(item, True) for name,item in sorted(objects.items())}
    state['cursor_channels'] = rotation(bpy.context.scene.cursor)
    return state


def rotation_properties():
    result = {}
    for name, item in [('object', bpy.types.Object), ('cursor', bpy.types.View3DCursor)]:
        fields = {}
        for p in item.bl_rna.properties:
            if not p.identifier.startswith(('rotation_', 'lock_rotation', 'delta_rotation')):
                continue
            meta = {'type': p.type, 'description': p.description}
            for key in ['array_length', 'hard_min', 'hard_max', 'is_enum_flag']:
                if hasattr(p,key):meta[key] = getattr(p,key)
            if p.type=='ENUM':meta['enum']=[v.identifier for v in p.enum_items]
            if getattr(p,'array_length',0):meta['default']=list(p.default_array)
            elif hasattr(p,'default'):meta['default']=p.default
            fields[p.identifier] = meta
        result[name] = fields
    return result


def capture(args):
    suite = json.loads(args.suite.read_text())
    assert len(suite['runs'])==2496 and list(bpy.app.version)==suite['reference']['version']
    assert not bpy.app.background and bpy.app.build_hash.decode()==suite['reference']['build_hash']
    assert digest(bpy.app.binary_path)=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    stage = args.output.with_name(args.output.name+'.staging')
    assert not args.output.exists() and not stage.exists(), 'refuse existing output or staging'
    paths = [args.suite, Path(__file__), ADAPTER, snap.ADAPTER, snap.transform.BASE_PATH,
             ROOT/'tools/generate_snap_rotation_cases.py', ROOT/'tools/generate_snap_menu_cases.py',
             ROOT/'tools/generate_mesh_transform_cases.py', ROOT/'docs/contracts/snap-rotation-baseline.md',
             ROOT/'baseline/lock.json', ROOT/'baseline/sources/snap-rotation/manifest.json']
    source_manifest = json.loads((ROOT/'baseline/sources/snap-rotation/manifest.json').read_text())
    for name in source_manifest['reused_source_manifests']:
        paths.append(ROOT/name)
        for row in json.loads((ROOT/name).read_text())['files']:
            p=(ROOT/name).parent/row['file'];assert digest(p)==row['sha256'];paths.append(p)
    for row in source_manifest['files']:
        p=ROOT/'baseline/sources/snap-rotation'/row['file'];assert digest(p)==row['sha256'];paths.append(p)
    inputs={str(p.resolve()):digest(p) for p in paths}
    runs=suite['runs']
    if args.case_ids:
        assert set(args.case_ids)<={r['id'] for r in runs}
        runs=[r for r in runs if r['id'] in args.case_ids]
    stage.mkdir(parents=True)
    write(stage/'operator-properties.json', {'operators':snap.properties(),'rotation':rotation_properties()})
    records=[]
    for index,run in enumerate(runs):
        objects,area,region=create(suite,run)
        before=snapshot(objects,area,run)
        op=getattr(bpy.ops.view3d,run['operator'])
        with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):
            assert op.poll(),('invalid source setup',run['id'])
            try:result={'status':sorted(op(**copy.deepcopy(run['parameters']))),'error':None}
            except RuntimeError as error:result={'status':['ERROR'],'error':str(error)}
        bpy.context.view_layer.update()
        after=snapshot(objects,area,run)
        raw=(json.dumps({'run':run,'before':before,'after':after,'result':result},indent=2,allow_nan=False)+'\n').encode()
        path=stage/(run['id']+'.json.gz')
        with path.open('xb') as output:
            with gzip.GzipFile(filename='',fileobj=output,mode='wb',mtime=0) as compressed:compressed.write(raw)
        assert gzip.decompress(path.read_bytes())==raw
        records.append({'id':run['id'],'file':path.name,'sha256':digest(path),
                        'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':len(raw),'status':result['status']})
        if (index+1)%100==0:print(json.dumps({'captured':index+1,'total':len(runs)}),flush=True)
    assert inputs=={str(p.resolve()):digest(p) for p in paths},'capture input changed'
    write(stage/'manifest.json',{'schema_version':1,'product':'blender','version':list(bpy.app.version),
        'build_hash':bpy.app.build_hash.decode(),'process_id':os.getpid(),'binary_sha256':digest(bpy.app.binary_path),
        'scope':'focused_diagnostic' if args.case_ids else 'complete_2496_authored_snap_rotation_cases',
        'captured_utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),
        'command_line':sys.argv,'background':bpy.app.background,'input_hashes':inputs,
        'operator_properties_sha256':digest(stage/'operator-properties.json'),'runs':records,
        'product_acceptance':'unrun'})
    stage.rename(args.output)
    print(json.dumps({'captured':len(records),'product_acceptance':'unrun'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',action='append',default=[],dest='case_ids')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    def start():
        try:capture(args)
        except BaseException:
            traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
        sys.stdout.flush();sys.stderr.flush();os._exit(0)
    bpy.app.timers.register(start,first_interval=.5)

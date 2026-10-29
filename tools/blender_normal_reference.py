#!/usr/bin/env python3
"""Record CPU automatic normals from the fixed Blender executable."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

import bpy


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':'))+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);suite=json.loads(args.suite.read_bytes())
    build=bpy.app.build_hash.decode();assert list(bpy.app.version)==suite['reference']['version']
    assert build==suite['reference']['build_hash'];assert suite['normal_absolute_tolerance']==1e-6
    assert not args.output.exists();args.output.parent.mkdir(parents=True,exist_ok=True)
    started=datetime.now(timezone.utc).isoformat();records=[]
    with tempfile.TemporaryDirectory(prefix='.normal-capture-',dir=args.output.parent) as temporary:
        stage=Path(temporary)/'capture';stage.mkdir()
        for case in suite['cases']:
            mesh=bpy.data.meshes.new('AutomaticNormalFixture')
            try:
                mesh.from_pydata(case['vertices'],case['edges'],case['faces'])
                for face, smooth in zip(mesh.polygons,case['smooth']):face.use_smooth=smooth
                for index in case['seams']:mesh.edges[index].use_seam=True
                mesh.update();mesh.calc_loop_triangles();corners=mesh.corner_normals
                result={'id':case['id'],'vertices':[list(v.co) for v in mesh.vertices],
                        'faces':[list(f.vertices) for f in mesh.polygons],
                        'smooth':[f.use_smooth for f in mesh.polygons],
                        'normals':[{'normal':list(f.normal),'corner_normals':[list(corners[i].vector) for i in f.loop_indices]} for f in mesh.polygons]}
                file=stage/(case['id']+'.json');write(file,result)
                records.append({'id':case['id'],'file':file.name,'sha256':sha(file)})
            finally:bpy.data.meshes.remove(mesh)
        write(stage/'manifest.json',{'complete':True,'cases':len(records),'records':records,
                'version':list(bpy.app.version),'build_hash':build,'binary_sha256':sha(bpy.app.binary_path),
                'suite_sha256':sha(args.suite),'adapter_sha256':sha(__file__),'platform':platform.platform(),
                'process_id':os.getpid(),'background':bpy.app.background,'started_utc':started,'command_line':sys.argv})
        stage.replace(args.output)
    print(json.dumps({'captured':len(records),'output':str(args.output)}),flush=True)


if __name__=='__main__':main()

#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,tempfile
parser=argparse.ArgumentParser(description="Verify runtime generation with all source repository reads denied on macOS")
parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
workspace=tempfile.TemporaryDirectory(prefix='formora-independent-generation-')
runtime=Path(workspace.name)
binary=runtime/'formora';shutil.copyfile(args.binary.resolve(),binary);binary.chmod(0o755)
policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))'
prefix=['/usr/bin/sandbox-exec','-p',policy]
control=subprocess.run([*prefix,'/bin/cat',str(root/'baseline/fixtures/mesh-primitives.json')],capture_output=True,text=True,cwd=runtime)
assert (root/'baseline/fixtures/mesh-primitives.json').is_file()
assert control.returncode!=0 and not control.stdout and ('Operation not permitted' in control.stderr or 'Permission denied' in control.stderr),control
scene=runtime/'scene.json'
def run(*args,request=None):
 p=subprocess.run([*prefix,str(binary),*map(str,args)],input=None if request is None else json.dumps(request),capture_output=True,text=True,cwd=runtime,check=True)
 return json.loads(p.stdout)
run('scene','init','--scene',scene)
primitives=[{'kind':'plane','size':3.25},{'kind':'cube','size':5.125},{'kind':'grid','size':4.125,'x_subdivisions':17,'y_subdivisions':19},{'kind':'circle','radius':0.875,'vertices':37,'fill_type':'trifan'}, {'kind':'uv_sphere','radius':0.875,'segments':23,'ring_count':11}, {'kind':'cylinder','radius':0.875,'depth':1.75,'vertices':19,'end_fill_type':'trifan'}, {'kind':'cone','radius1':0.875,'radius2':0.375,'vertices':13}, {'kind':'torus','major_segments':17,'minor_segments':9,'major_radius':1.125,'minor_radius':0.375}, {'kind':'ico_sphere','subdivisions':4,'radius':0.875}, {'kind':'monkey','size':1.75}]
run('scene','apply','--scene',scene,'--request','-',request={'expected_revision':0,'commands':[{'operation':'create_mesh_primitive','id':p['kind'],'primitive':p} for p in primitives]})
expected={'plane':(4,4,1),'cube':(8,12,6),'grid':(360,682,323),'circle':(38,74,37),'uv_sphere':(232,483,253),'cylinder':(40,95,57),'cone':(26,39,15),'torus':(153,306,153)}
expected.update({'ico_sphere':(642,1920,1280),'monkey':(507,1005,500)})
results=[]
for primitive in primitives:
 value=run('scene','inspect','--scene',scene,'--mesh-asset',primitive['kind']);asset=value['mesh_asset'];counts=(len(asset['vertices']),len(asset['edges']),len(asset['polygons']))
 assert counts==expected[primitive['kind']]
 assert asset['recipe']['primitive']['kind']==primitive['kind']
 file=primitive['kind']+'-query.json';(output/file).write_text(json.dumps(value,allow_nan=False)+'\n')
 results.append({'kind':primitive['kind'],'counts':counts,'recipe':asset['recipe'],'file':file,'sha256':hashlib.sha256((output/file).read_bytes()).hexdigest()})
report={'source_repository_reads':'denied by macOS sandbox','repository_path':str(root),'policy':policy,'denial_control_exit_code':control.returncode,'denial_control_stderr':control.stderr,'copied_binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'cwd':str(runtime),'inputs':primitives,'results':results,'passed':True,'full_feature_acceptance':'unrun'}
(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'runtime_has_no_repository_access':True,'unseen_parameter_samples':len(primitives),'passed':True}))

workspace.cleanup()

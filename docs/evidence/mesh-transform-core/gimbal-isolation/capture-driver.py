from pathlib import Path
import hashlib,json,math,shutil,struct,subprocess,tempfile
root=Path('/Users/chrischeng/faberlines/formora');source_binary=Path('/private/tmp/formora-target-actual185/debug/formora');output=root/'docs/evidence/mesh-transform-core/gimbal-isolation';output.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();f32=lambda v:struct.unpack('<f',struct.pack('<f',v))[0];calls=[]
def vector(m,p):return [sum(m[i][j]*p[j] for j in range(3)) for i in range(3)]
def multiply(a,b):return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def transpose(m):return list(map(list,zip(*m)))
def inverse(m):
 adj=[[(m[(j+1)%3][(i+1)%3]*m[(j+2)%3][(i+2)%3]-m[(j+1)%3][(i+2)%3]*m[(j+2)%3][(i+1)%3]) for j in range(3)] for i in range(3)]
 det=sum(m[0][j]*adj[j][0] for j in range(3));assert abs(det)>0.1
 return [[v/det for v in row] for row in adj]
def rotate_axis(p,axis,radians):
 p=list(p);s,c=math.sin(radians),math.cos(radians);j,k=(axis+1)%3,(axis+2)%3;a,b=p[j],p[k];p[j],p[k]=c*a-s*b,s*a+c*b;return p
def matrix(angles,order):
 columns=[]
 for axis in range(3):
  p=[float(axis==j) for j in range(3)]
  for k in order:p=rotate_axis(p,k,angles[k])
  columns.append(p)
 return transpose(columns)
def gimbal(angles,order):
 angles=[f32(v) for v in angles];first,second,last=order;columns=[[0.0]*3 for _ in range(3)]
 columns[first]=[float(first==j) for j in range(3)]
 for k in order:columns[first]=rotate_axis(columns[first],k,angles[k])
 columns[second]=rotate_axis([float(second==j) for j in range(3)],last,angles[last]);columns[last][last]=1
 return transpose(columns)
angles=[0.273,-0.419,0.657];parent_angles=[0.17,-0.23,0.41]
parent=matrix(parent_angles,[1,2,0]);parent=[[(-v if j==0 else v) for j,v in enumerate(row)] for row in parent]
obj=multiply(parent,matrix(angles,[2,0,1]));obj_inverse=transpose(obj);basis=multiply(parent,gimbal(angles,[2,0,1]))
original={'apricot':[0.17,-0.29,0.31],'birch':[1.37,0.09,-0.11],'cedar':[0.97,1.81,0.11],'dogwood':[-0.23,1.43,0.53],'apart':[0.17,-0.29,0.31],'hidden':[0.2,0.2,0.2]};selected=['apricot','birch','cedar','dogwood']
asset={'vertices':original,'edges':{'ab':['apricot','birch'],'bc':['birch','cedar'],'cd':['cedar','dogwood'],'da':['dogwood','apricot']},'triangles':{},'polygons':{'surface':{'vertices':selected,'uv_layers':{'Detail':[[0.031,0.9],[0.83,0.71],[0.97,0.16],[0.13,0.21]]},'normal':None,'corner_normals':None,'smooth':False,'material_slot':None}},'uv_layout':{'layers':['Detail'],'active':'Detail'},'material_slots':[],'vertex_groups':['keep'],'vertex_weights':{'birch':{'keep':0.375}}}
identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]};target_rotation={'kind':'euler','angles':angles,'order':'zxy'}
def entity(id,position):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':'parent' if id=='target' else None,'transform':{**identity,'translation':position,'rotation':target_rotation if id=='target' else [0,0,0,1]},'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}}}
def check(actual,expected):
 for id,p in expected.items():
  for a,e in zip(actual[id],p):assert math.isfinite(a) and abs(a-e)<=1e-6,(id,actual[id],p)
def expected_for(move):return {id:move(p) if id in selected else list(p) for id,p in original.items()}
with tempfile.TemporaryDirectory(prefix='formora-gimbal-independent-') as temporary:
 runtime=Path(temporary);binary=runtime/'formora';shutil.copyfile(source_binary,binary);binary.chmod(0o755);policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))';prefix=['/usr/bin/sandbox-exec','-p',policy]
 denial=subprocess.run([*prefix,'/bin/cat',str(root/'Cargo.toml')],cwd=runtime,capture_output=True,text=True);assert denial.returncode!=0 and not denial.stdout and ('Operation not permitted' in denial.stderr or 'Permission denied' in denial.stderr)
 scene=runtime/'scene.json';initialized=subprocess.run([*prefix,str(binary),'scene','init','--scene',str(scene)],cwd=runtime,capture_output=True,text=True);assert initialized.returncode==0,initialized.stdout+initialized.stderr
 process=subprocess.Popen([*prefix,str(binary),'scene','serve','--scene',str(scene)],cwd=runtime,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);sequence=0
 def call(name,arguments):
  global sequence
  sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':arguments})+'\n');process.stdin.flush();response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok'],response;calls.append({'name':name,'arguments':arguments,'response':response});return response['result']
 def apply(revision,commands):return call('scene_apply',{'expected_revision':revision,'commands':commands})
 editing={'selected':{'vertices':selected},'hidden':{'vertices':['hidden']},'preview':False}
 parent_command={'operation':'create_entity','id':'parent','entity':{'name':'Parent','parent':None,'transform':{'translation':[0,0,0],'rotation':{'kind':'euler','angles':parent_angles,'order':'yzx'},'scale':[-1,1,1]},'content':{'kind':'empty'}}}
 setup=[{'operation':'set_mesh_asset','id':'mesh','asset':asset},{'operation':'set_mesh_editing','id':'mesh','editing':editing},parent_command,entity('target',[0,0,0]),entity('other',[-2.4,1.8,0.9])];apply(0,setup);before=call('scene_inspect',{})['scene'];assert before['entities']['target']['transform']['rotation']==target_rotation
 def transform(revision,change,**extra):
  receipt=apply(revision,[{'operation':'transform_mesh','transform':{'entity':'target','change':change,'orientation':{'kind':'gimbal'},'center_override':[0,0,0],**extra}}]);assert receipt['transforms'][0]['shared_instances']==['other','target']
  for actual,expected in zip(receipt['transforms'][0]['basis_world'],basis):
   for a,e in zip(actual,expected):assert abs(a-e)<=1e-6,(actual,expected)
  return receipt,call('scene_inspect',{})['scene']
 delta=[0.217,-0.439,0.713];receipt,after=transform(1,{'kind':'translate','value':delta});local=vector(obj_inverse,vector(basis,delta));check(after['mesh_assets']['mesh']['vertices'],expected_for(lambda p:[p[j]+local[j] for j in range(3)]));assert before['entities']==after['entities']
 call('scene_undo',{'expected_revision':2});assert call('scene_inspect',{})['scene']['mesh_assets']==before['mesh_assets']
 angle=f32(0.37);c,s=math.cos(angle),math.sin(angle);axis=[basis[i][1] for i in range(3)]
 def rotate(p):
  p=vector(obj,p);cross=[axis[(j+1)%3]*p[(j+2)%3]-axis[(j+2)%3]*p[(j+1)%3] for j in range(3)];dot=sum(axis[j]*p[j] for j in range(3));return vector(obj_inverse,[c*p[j]+s*cross[j]+(1-c)*axis[j]*dot for j in range(3)])
 rotated_receipt,rotated=transform(3,{'kind':'rotate','radians':0.37,'axis':'y'},constraint_axis=[False,True,False]);check(rotated['mesh_assets']['mesh']['vertices'],expected_for(rotate))
 call('scene_undo',{'expected_revision':4});assert call('scene_inspect',{})['scene']['mesh_assets']==before['mesh_assets']
 resize=multiply(obj_inverse,multiply(multiply(basis,multiply([[-0.83,0,0],[0,1.23,0],[0,0,0.67]],inverse(basis))),obj))
 resized_receipt,final=transform(5,{'kind':'resize','value':[-0.83,1.23,0.67]});check(final['mesh_assets']['mesh']['vertices'],expected_for(lambda p:vector(resize,p)))
 assert final['entities']==before['entities'];assert final['mesh_assets']['mesh']['polygons']['surface']['uv_layers']==asset['polygons']['surface']['uv_layers'];assert final['mesh_assets']['mesh']['vertex_weights']==asset['vertex_weights']
 normals=call('scene_inspect',{'mesh_asset':'mesh','normals':True});assert len(normals['normals']['faces'])==1
 process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();process.stdout.close();process.stderr.close();assert process.returncode==0,stderr
 reopened=subprocess.run([*prefix,str(binary),'scene','inspect','--scene',str(scene)],cwd=runtime,capture_output=True,text=True);assert reopened.returncode==0,reopened.stdout+reopened.stderr;assert json.loads(reopened.stdout)['scene']==final
 for name,data in [('before',before),('translated',after),('rotated',rotated),('final',final),('normals',normals),('translate-receipt',receipt),('rotate-receipt',rotated_receipt),('resize-receipt',resized_receipt)]: (output/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
 report={'passed':True,'scope':'unseen ZXY gimbal translation, rotation and reflected resize under a reflected YZX parent with source repository reads denied','binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),'policy':policy,'denial_control_exit_code':denial.returncode,'denial_control_stderr':denial.stderr,'commands':calls,'fresh_reload_equal':True,'undo_checked':True,'all_initial_points_and_euler_angles_authored_in_driver':True,'normal_payloads_in_input':False,'source_files':{str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},'artifacts':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'issue_acceptance':'unrun','milestone_acceptance':'unrun'};(output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'repository_reads':'denied','unseen_zxy_gimbal_transforms':True,'reflected_yzx_parent':True,'fresh_reload_equal':True}))

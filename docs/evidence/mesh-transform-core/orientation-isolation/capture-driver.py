from pathlib import Path
import hashlib,json,math,shutil,struct,subprocess,tempfile
root=Path('/Users/chrischeng/faberlines/formora');source_binary=Path('/private/tmp/formora-target-actual185/debug/formora')
output=root/'docs/evidence/mesh-transform-core/orientation-isolation';output.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();f32=lambda v:struct.unpack('<f',struct.pack('<f',v))[0];calls=[]
o=[0.17,-0.29,0.31];u=[0.8,0.6,0];v=[-0.3,0.4,math.sqrt(0.75)];n=[u[1]*v[2],-u[0]*v[2],0.5]
corners=[(0,0),(1.37,0),(1.37,0.73),(0,0.73)];selected=['apricot','birch','cedar','dogwood']
original={id:[o[j]+a*u[j]+b*v[j] for j in range(3)] for id,(a,b) in zip(selected,corners)};original['apart']=list(o);original['hidden']=[0.2,0.2,0.2]
asset={'vertices':original,'edges':{'ab':['apricot','birch'],'bc':['birch','cedar'],'cd':['cedar','dogwood'],'da':['dogwood','apricot']},'triangles':{},'polygons':{'surface':{'vertices':selected,'uv_layers':{'Detail':[[0.031,0.9],[0.83,0.71],[0.97,0.16],[0.13,0.21]]},'normal':None,'corner_normals':None,'smooth':False,'material_slot':None}},'uv_layout':{'layers':['Detail'],'active':'Detail'},'material_slots':[],'vertex_groups':['keep'],'vertex_weights':{'birch':{'keep':0.375}}}
identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
def entity(id,position):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':None,'transform':{**identity,'translation':position},'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}}}
def check(actual,expected):
 for id,p in expected.items():
  for a,e in zip(actual[id],p):assert math.isfinite(a) and abs(a-e)<=1e-6,(id,actual[id],p)
def expected_for(move):
 result={id:list(p) for id,p in original.items()}
 for id in selected:result[id]=move(original[id])
 return result
with tempfile.TemporaryDirectory(prefix='formora-normal-independent-') as temporary:
 runtime=Path(temporary);binary=runtime/'formora';shutil.copyfile(source_binary,binary);binary.chmod(0o755)
 policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))';prefix=['/usr/bin/sandbox-exec','-p',policy]
 denial=subprocess.run([*prefix,'/bin/cat',str(root/'Cargo.toml')],cwd=runtime,capture_output=True,text=True);assert denial.returncode!=0 and not denial.stdout and ('Operation not permitted' in denial.stderr or 'Permission denied' in denial.stderr)
 scene=runtime/'scene.json';initialized=subprocess.run([*prefix,str(binary),'scene','init','--scene',str(scene)],cwd=runtime,capture_output=True,text=True);assert initialized.returncode==0,initialized.stdout+initialized.stderr
 process=subprocess.Popen([*prefix,str(binary),'scene','serve','--scene',str(scene)],cwd=runtime,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);sequence=0
 def call(name,arguments):
  global sequence
  sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':arguments})+'\n');process.stdin.flush();response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok'],response;calls.append({'name':name,'arguments':arguments,'response':response});return response['result']
 def apply(revision,commands):return call('scene_apply',{'expected_revision':revision,'commands':commands})
 face={'kind':'polygon','id':'surface'};editing={'mode':['face'],'selected':{'faces':[face]},'history':[{'domain':'face','face':face}],'active_face':face,'hidden':{'vertices':['hidden']},'preview':False}
 setup=[{'operation':'set_mesh_asset','id':'mesh','asset':asset},{'operation':'set_mesh_editing','id':'mesh','editing':editing},entity('target',[0,0,0]),entity('other',[-2.4,1.8,0.9])];apply(0,setup);before=call('scene_inspect',{})['scene']
 def transform(revision,change,pivot='median',**extra):
  receipt=apply(revision,[{'operation':'transform_mesh','transform':{'entity':'target','change':change,'orientation':{'kind':'normal'},'pivot':pivot,**extra}}]);assert receipt['transforms'][0]['shared_instances']==['other','target'];return receipt,call('scene_inspect',{})['scene']
 delta=[0.217,-0.439,0.713];receipt,after=transform(1,{'kind':'translate','value':delta})
 expected=expected_for(lambda p:[p[j]-delta[0]*v[j]+delta[1]*u[j]+delta[2]*n[j] for j in range(3)])
 check(after['mesh_assets']['mesh']['vertices'],expected);assert before['entities']==after['entities']
 call('scene_undo',{'expected_revision':2});assert call('scene_inspect',{})['scene']['mesh_assets']==before['mesh_assets']
 centre=[o[j]+0.685*u[j]+0.365*v[j] for j in range(3)];angle=f32(0.37);c,s=math.cos(angle),math.sin(angle)
 def rotate(p):
  d=[p[j]-centre[j] for j in range(3)];cross=[n[(j+1)%3]*d[(j+2)%3]-n[(j+2)%3]*d[(j+1)%3] for j in range(3)];dot=sum(n[j]*d[j] for j in range(3))
  return [centre[j]+c*d[j]+s*cross[j]+(1-c)*n[j]*dot for j in range(3)]
 rotated_receipt,rotated=transform(3,{'kind':'rotate','radians':0.37,'axis':'z'},constraint_axis=[False,False,True]);check(rotated['mesh_assets']['mesh']['vertices'],expected_for(rotate))
 call('scene_undo',{'expected_revision':4});assert call('scene_inspect',{})['scene']['mesh_assets']==before['mesh_assets']
 def resize(p):
  d=[p[j]-centre[j] for j in range(3)];a=sum(d[j]*u[j] for j in range(3));b=sum(d[j]*v[j] for j in range(3));h=sum(d[j]*n[j] for j in range(3))
  return [centre[j]+a*1.23*u[j]+b*(-0.83)*v[j]+h*0.67*n[j] for j in range(3)]
 resized_receipt,final=transform(5,{'kind':'resize','value':[-0.83,1.23,0.67]},pivot='individual');check(final['mesh_assets']['mesh']['vertices'],expected_for(resize))
 assert set(resized_receipt['transforms'][0]['component_basis_local'])==set(selected)
 assert final['entities']==before['entities'];assert final['mesh_assets']['mesh']['polygons']['surface']['uv_layers']==asset['polygons']['surface']['uv_layers'];assert final['mesh_assets']['mesh']['vertex_weights']==asset['vertex_weights']
 normals=call('scene_inspect',{'mesh_asset':'mesh','normals':True});assert len(normals['normals']['faces'])==1
 process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();process.stdout.close();process.stderr.close();assert process.returncode==0,stderr
 reopened=subprocess.run([*prefix,str(binary),'scene','inspect','--scene',str(scene)],cwd=runtime,capture_output=True,text=True);assert reopened.returncode==0,reopened.stdout+reopened.stderr;assert json.loads(reopened.stdout)['scene']==final
 for name,data in [('before',before),('translated',after),('rotated',rotated),('final',final),('normals',normals),('translate-receipt',receipt),('rotate-receipt',rotated_receipt),('resize-receipt',resized_receipt)]: (output/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
 report={'passed':True,'scope':'unseen geometric normal translate, constrained rotate and individual reflected resize with source repository reads denied','binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),'policy':policy,'denial_control_exit_code':denial.returncode,'denial_control_stderr':denial.stderr,'commands':calls,'fresh_reload_equal':True,'undo_checked':True,'all_initial_points_authored_in_driver':True,'normal_payloads_in_input':False,'source_files':{str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},'artifacts':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'issue_acceptance':'unrun','milestone_acceptance':'unrun'};(output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'repository_reads':'denied','unseen_normal_translate_rotate_resize':True,'fresh_reload_equal':True}))

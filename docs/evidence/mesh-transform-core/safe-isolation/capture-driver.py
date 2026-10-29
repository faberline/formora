from pathlib import Path
import hashlib,json,math,shutil,struct,subprocess,tempfile
root=Path('/Users/chrischeng/faberlines/formora');source_binary=Path('/private/tmp/formora-target-actual185/debug/formora');output=root/'docs/evidence/mesh-transform-core/safe-isolation';output.mkdir(parents=True,exist_ok=False);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();f32=lambda v:struct.unpack('<f',struct.pack('<f',v))[0];calls=[]
original={'apricot':[0.17,-0.29,0.31],'birch':[1.37,0.09,-0.11],'cedar':[0.97,1.81,0.11],'dogwood':[-0.23,1.43,0.53],'apart':[0.17,-0.29,0.31],'hidden':[0.2,0.2,0.2]};selected=['apricot','birch','cedar','dogwood']
asset={'vertices':original,'edges':{'ab':['apricot','birch'],'bc':['birch','cedar'],'cd':['cedar','dogwood'],'da':['dogwood','apricot']},'triangles':{},'polygons':{'surface':{'vertices':selected,'uv_layers':{'Detail':[[0.031,0.9],[0.83,0.71],[0.97,0.16],[0.13,0.21]]},'normal':None,'corner_normals':None,'smooth':False,'material_slot':None}},'uv_layout':{'layers':['Detail'],'active':'Detail'},'material_slots':[],'vertex_groups':['keep'],'vertex_weights':{'birch':{'keep':0.375}}}
identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
def entity(id,position):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':None,'transform':{**identity,'translation':position,'scale':[-1.3,0,0.7] if id=='target' else [1,1,1]},'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}}}
def check(actual,expected):
 for id,p in expected.items():
  assert len(actual[id])==3
  for a,e in zip(actual[id],p):assert math.isfinite(a) and abs(a-e)<=1e-6,(id,actual[id],p)
with tempfile.TemporaryDirectory(prefix='formora-safe-independent-') as temporary:
 runtime=Path(temporary);binary=runtime/'formora';shutil.copyfile(source_binary,binary);binary.chmod(0o755);policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))';prefix=['/usr/bin/sandbox-exec','-p',policy]
 denial=subprocess.run([*prefix,'/bin/cat',str(root/'Cargo.toml')],cwd=runtime,capture_output=True,text=True);assert denial.returncode!=0 and not denial.stdout and ('Operation not permitted' in denial.stderr or 'Permission denied' in denial.stderr)
 scene=runtime/'scene.json';initialized=subprocess.run([*prefix,str(binary),'scene','init','--scene',str(scene)],cwd=runtime,capture_output=True,text=True);assert initialized.returncode==0,initialized.stdout+initialized.stderr
 process=subprocess.Popen([*prefix,str(binary),'scene','serve','--scene',str(scene)],cwd=runtime,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);sequence=0
 def call(name,arguments):
  global sequence
  sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':arguments})+'\n');process.stdin.flush();response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok'],response;calls.append({'name':name,'arguments':arguments,'response':response});return response['result']
 def apply(revision,commands):return call('scene_apply',{'expected_revision':revision,'commands':commands})
 editing={'selected':{'vertices':selected},'hidden':{'vertices':['hidden']},'preview':False}
 setup=[{'operation':'set_mesh_asset','id':'mesh','asset':asset},{'operation':'set_mesh_editing','id':'mesh','editing':editing},entity('target',[0,0,0]),entity('other',[-2.4,1.8,0.9])];apply(0,setup);before=call('scene_inspect',{})['scene']
 centre=[0.31,-0.19,0.23];local_centre=[centre[0]/(-1.3),centre[1],centre[2]]
 delta=[0.217,-0.439,0.713];transform={'operation':'transform_mesh','transform':{'entity':'target','change':{'kind':'translate','value':delta},'center_override':centre}}
 receipt=apply(1,[transform]);after=call('scene_inspect',{})['scene'];assert receipt['transforms'][0]['shared_instances']==['other','target']
 expected={id:list(p) for id,p in original.items()}
 for id in selected:
  expected[id]=[original[id][0]+delta[0]/(-1.3),original[id][1],original[id][2]+delta[2]/0.7]
  assert all(abs(a-e)<=1e-6 for a,e in zip(receipt['transforms'][0]['centres_local'][id],local_centre))
 check(after['mesh_assets']['mesh']['vertices'],expected);assert before['entities']==after['entities']
 call('scene_undo',{'expected_revision':2});restored=call('scene_inspect',{})['scene'];assert restored['mesh_assets']==before['mesh_assets']
 angle=f32(0.37);c,s=math.cos(angle),math.sin(angle);editing['selected']['vertices']=selected
 rotate={'operation':'transform_mesh','transform':{'entity':'target','change':{'kind':'rotate','radians':0.37,'axis':'z'},'center_override':centre}}
 rotated_receipt=apply(3,[{'operation':'set_mesh_editing','id':'mesh','editing':editing},rotate]);assert rotated_receipt['transforms'][0]['command_index']==1;rotated=call('scene_inspect',{})['scene'];expected={id:list(p) for id,p in original.items()}
 for id in selected:
  expected[id]=[local_centre[0]+c*(original[id][0]-local_centre[0]),local_centre[1],original[id][2]]
 check(rotated['mesh_assets']['mesh']['vertices'],expected)
 resize={'operation':'transform_mesh','transform':{'entity':'target','change':{'kind':'resize','value':[-0.83,1.23,0.67]},'center_override':centre}};resized_receipt=apply(4,[resize]);final=call('scene_inspect',{})['scene']
 for id in selected:expected[id]=[local_centre[0]+(expected[id][0]-local_centre[0])*(-0.83),local_centre[1],local_centre[2]+(expected[id][2]-local_centre[2])*0.67]
 check(final['mesh_assets']['mesh']['vertices'],expected);assert final['entities']==before['entities'];assert final['mesh_assets']['mesh']['polygons']['surface']['uv_layers']==asset['polygons']['surface']['uv_layers'];assert final['mesh_assets']['mesh']['vertex_weights']==asset['vertex_weights']
 normals=call('scene_inspect',{'mesh_asset':'mesh','normals':True});assert len(normals['normals']['faces'])==1
 process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();process.stdout.close();process.stderr.close();assert process.returncode==0,stderr
 reopened=subprocess.run([*prefix,str(binary),'scene','inspect','--scene',str(scene)],cwd=runtime,capture_output=True,text=True);assert reopened.returncode==0,reopened.stdout+reopened.stderr;assert json.loads(reopened.stdout)['scene']==final
 for name,data in [('before',before),('translated',after),('rotated',rotated),('final',final),('normals',normals),('translate-receipt',receipt),('rotate-receipt',rotated_receipt),('resize-receipt',resized_receipt)]: (output/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
 report={'passed':True,'scope':'unseen singular translation, rotation and reflected resize with distinct affine pivot with source repository reads denied','binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),'policy':policy,'denial_control_exit_code':denial.returncode,'denial_control_stderr':denial.stderr,'commands':calls,'fresh_reload_equal':True,'undo_checked':True,'all_initial_points_authored_in_driver':True,'normal_payloads_in_input':False,'source_files':{str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},'artifacts':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'issue_acceptance':'unrun','milestone_acceptance':'unrun'};(output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'repository_reads':'denied','unseen_singular_translate_rotate_resize':True,'fresh_reload_equal':True}))

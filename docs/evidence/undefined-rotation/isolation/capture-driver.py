from pathlib import Path
import hashlib,json,math,shutil,struct,subprocess,tempfile
root=Path('/Users/chrischeng/faberlines/formora');source_binary=Path('/private/tmp/formora-target-actual185/debug/formora');output=Path('/private/tmp/formora-undefined-isolation');output.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();calls=[]
vertices={'apricot':[0.31,1.17,0.2],'birch':[1.61,1.17,0.2],'cedar':[1.61,2.37,0.2],'dogwood':[0.31,2.37,0.2],'umber':[0.31,-1.17,0.2],'violet':[0.31,-2.37,0.2],'willow':[1.61,-2.37,0.2],'xenia':[1.61,-1.17,0.2],'plane':[2.13,0.000007,0.2],'apart':[0.31,1.17,0.2],'hidden':[2.31,-2.11,0.4]}
polygons={};pairs=set()
for name,ids,uv in [('upper',['apricot','birch','cedar','dogwood'],[[0,0],[1.3,0],[1.3,1.2],[0,1.2]]),('lower',['umber','violet','willow','xenia'],[[0,0],[0,1.2],[1.3,1.2],[1.3,0]])]:
 polygons[name]={'vertices':ids,'uv_layers':{'UV':uv,'Ribbon':[[0.37+2*x,-0.19+3*y] for x,y in uv]},'normal':None,'corner_normals':None,'smooth':False,'material_slot':None}
 for i in range(4):pairs.add(tuple(sorted([ids[i-1],ids[i]])))
asset={'vertices':vertices,'edges':{f'edge{i}':list(p) for i,p in enumerate(sorted(pairs))},'polygons':polygons,'triangles':{},'uv_layout':{'layers':['Ribbon','UV'],'active':'UV'},'material_slots':[],'vertex_groups':['keep'],'vertex_weights':{'birch':{'keep':0.375}}}
identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
def entity(id,scale):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':None,'transform':{**identity,'translation':[0.41,-0.73,0.29] if id=='target' else [3.17,0.12,0.63],'scale':scale,**({'precision':'f32'} if id=='target' else {})},'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}}}
def near(a,b):
 assert len(a)==len(b)
 for x,y in zip(a,b):assert math.isfinite(x) and abs(x-y)<=1e-6,(a,b)
with tempfile.TemporaryDirectory(prefix='formora-uv-mirror-independent-') as temporary:
 runtime=Path(temporary);binary=runtime/'formora';shutil.copyfile(source_binary,binary);binary.chmod(0o755)
 policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))';prefix=['/usr/bin/sandbox-exec','-p',policy]
 denial=subprocess.run([*prefix,'/bin/cat',str(root/'Cargo.toml')],cwd=runtime,capture_output=True,text=True);assert denial.returncode!=0 and not denial.stdout and ('Operation not permitted' in denial.stderr or 'Permission denied' in denial.stderr)
 scene=runtime/'scene.json';initialized=subprocess.run([*prefix,str(binary),'scene','init','--scene',str(scene)],cwd=runtime,capture_output=True,text=True);assert initialized.returncode==0,initialized.stdout+initialized.stderr
 process=subprocess.Popen([*prefix,str(binary),'scene','serve','--scene',str(scene)],cwd=runtime,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);sequence=0
 def call(name,arguments,ok=True):
  global sequence
  sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':arguments})+'\n');process.stdin.flush();response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok']==ok,response;calls.append({'name':name,'arguments':arguments,'response':response});return response.get('result')
 def apply(revision,commands,ok=True):return call('scene_apply',{'expected_revision':revision,'commands':commands},ok)
 editing={'selected':{'vertices':['apricot','plane']},'hidden':{'vertices':['hidden']},'preview':False}
 apply(0,[{'operation':'set_mesh_asset','id':'mesh','asset':asset},{'operation':'set_mesh_editing','id':'mesh','editing':editing},entity('target',[-1.7,1.2,0.8]),entity('other',[1,1,1])]);before=call('scene_inspect',{})['scene']
 delta=[0.173,-0.219,0.137];local_delta=[delta[0]/1.7,delta[1]/1.2,delta[2]/0.8]
 command={'operation':'transform_mesh','transform':{'entity':'target','change':{'kind':'translate','value':delta},'orientation':{'kind':'local'},'mirror':{'axis':'y'},'correct_face_attributes':True}}
 receipt=apply(1,[command]);after=call('scene_inspect',{})['scene'];mesh=after['mesh_assets']['mesh'];r=receipt['transforms'][0]
 near(mesh['vertices']['apricot'],[x+d for x,d in zip(vertices['apricot'],local_delta)]);p=mesh['vertices']['apricot'];near(mesh['vertices']['umber'],[p[0],-p[1],p[2]])
 near(mesh['vertices']['plane'],[vertices['plane'][0]+local_delta[0],0,vertices['plane'][2]+local_delta[2]])
 assert r['mirror_sources']=={'umber':'apricot'} and r['mirror_plane_vertices']==['plane'] and r['shared_instances']==['other','target']
 for face in ['upper','lower']:
  near(mesh['polygons'][face]['uv_layers']['UV'][0],local_delta[:2]);near(mesh['polygons'][face]['uv_layers']['Ribbon'][0],[0.37+2*local_delta[0],-0.19+3*local_delta[1]])
  for layer in ['UV','Ribbon']:assert mesh['polygons'][face]['uv_layers'][layer][1:]==asset['polygons'][face]['uv_layers'][layer][1:]
 assert r['attribute_faces']==[{'kind':'polygon','id':'lower'},{'kind':'polygon','id':'upper'}]
 for id in set(vertices)-{'apricot','umber','plane'}:assert mesh['vertices'][id]==vertices[id],id
 for key in ['editing','vertex_groups','vertex_weights','uv_layout','edges']:assert mesh[key]==before['mesh_assets']['mesh'][key],key
 world_query=call('scene_inspect',{'entity':'target','world':True});assert world_query['entity']==after['entities']['target'];assert world_query['world_matrix'][0][0]==float(struct.unpack('<f',struct.pack('<f',-1.7))[0]);assert set(world_query['world_vertices'])==set(vertices);assert after['entities']==before['entities'];saved=scene.read_bytes();apply(1,[command],False);apply(2,[command,{'operation':'delete_entity','id':'missing'}],False);assert scene.read_bytes()==saved
 call('scene_undo',{'expected_revision':2});restored=call('scene_inspect',{})['scene'];assert restored['mesh_assets']==before['mesh_assets'];apply(3,[command]);final=call('scene_inspect',{})['scene'];assert final['mesh_assets']==after['mesh_assets']
 random_command={'operation':'transform_mesh','transform':{'entity':'target','change':{'kind':'translate','value':[0,0,0.1875]},'proportional':{'radius':4,'falloff':'random','seed':4275878552,'random_algorithm':'blender_5_2'}}}
 base_random=final
 random_result=apply(4,[random_command]);r_random=random_result['transforms'][0];assert r_random['random_algorithm']=='blender_5_2' and r_random['random_seed']==4275878552 and len(r_random['changed']['vertices'])>2
 random_after=call('scene_inspect',{})['scene'];assert random_after['mesh_assets']!=base_random['mesh_assets'];assert random_after['entities']==base_random['entities']
 call('scene_undo',{'expected_revision':5});assert call('scene_inspect',{})['scene']['mesh_assets']==base_random['mesh_assets']
 repeated=apply(6,[random_command]);assert repeated['transforms']==random_result['transforms'];final=call('scene_inspect',{})['scene'];assert final['mesh_assets']==random_after['mesh_assets']
 saved_rejection=scene.read_bytes();before_rejection=final
 invalid_rotation={'operation':'transform_mesh','transform':{'entity':'target','change':{'kind':'rotate','radians':0.173,'axis':'x'},'constraint_axis':[True,True,True]}}
 expected_error='mesh transform rotation cannot constrain all three axes: undefined Blender 5.2.3 source behavior'
 for commands in [[invalid_rotation],[random_command,invalid_rotation]]:
  apply(7,commands,False);assert calls[-1]['response']['error']==expected_error;assert scene.read_bytes()==saved_rejection;assert call('scene_inspect',{})['scene']==before_rejection
 call('scene_undo',{'expected_revision':7});assert call('scene_inspect',{})['scene']['mesh_assets']==base_random['mesh_assets']
 assert apply(8,[random_command])['transforms']==random_result['transforms'];final=call('scene_inspect',{})['scene'];assert final['mesh_assets']==random_after['mesh_assets']


 process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();process.stdout.close();process.stderr.close();assert process.returncode==0,stderr
 reopened=subprocess.run([*prefix,str(binary),'scene','inspect','--scene',str(scene)],cwd=runtime,capture_output=True,text=True);assert reopened.returncode==0,reopened.stdout+reopened.stderr;assert json.loads(reopened.stdout)['scene']==final
 for name,data in [('before',before),('after',after),('final',final),('receipt',receipt)]: (output/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
 report={'passed':True,'new_rotation_rejection_checked':True,'new_source_rng_undo_replay_checked':True,'scope':'unseen local-Y mirror with reflected nonuniform object scale, two affine UV layers, plane clamp, distinct coincident ID and hidden vertex; source repository reads denied','binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),'policy':policy,'denial_control_exit_code':denial.returncode,'denial_control_stderr':denial.stderr,'commands':calls,'fresh_reload_equal':True,'undo_checked':True,'stale_and_batch_rollback_checked':True,'all_initial_points_authored_in_driver':True,'normal_payloads_in_input':False,'source_files':{str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},'artifacts':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'issue_acceptance':'unrun','milestone_acceptance':'unrun'};(output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'repository_reads':'denied','unseen_f32_mirror_uvs_and_world_query':True,'fresh_reload_equal':True}))

#!/usr/bin/env python3
"""Execute unseen selection inputs while the Rust runtime cannot read the repository."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False);records=[]
    with tempfile.TemporaryDirectory(prefix='formora-selection-independent-') as temporary:
        folder=Path(temporary);binary=folder/'formora';shutil.copyfile(args.binary.resolve(),binary);binary.chmod(0o755)
        policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))'
        prefix=['/usr/bin/sandbox-exec','-p',policy]
        control=subprocess.run([*prefix,'/bin/cat',str(root/'baseline/fixtures/mesh-selection.json')],cwd=folder,capture_output=True,text=True)
        assert control.returncode!=0 and not control.stdout and 'not permitted' in control.stderr,control
        scene=folder/'scene.json';calls=[]
        def call(*arguments,request=None):
            result=subprocess.run([*prefix,str(binary),*map(str,arguments),'--scene',str(scene)],cwd=folder,capture_output=True,text=True,
                                  input=None if request is None else json.dumps(request),check=True)
            value=json.loads(result.stdout);calls.append({'arguments':list(map(str,arguments)),'request':request,'response':value});return value
        call('scene','init')
        asset={'vertices':{'a':[0,0,0],'b':[1.7,0,0],'c':[0.2,1.3,0.5],'wire_a':[2.1,0.7,0],
                           'wire_b':[2.9,0.8,0],'island':[0,0,0]},'edges':{'wire':['wire_a','wire_b']},
               'triangles':{'t':{'vertices':['a','b','c'],'uv_layers':{},'corner_normals':None,'material_slot':None}},
               'material_slots':[],'vertex_groups':['Keep'],'vertex_weights':{'a':{'Keep':0},'b':{'Keep':1}}}
        call('scene','apply','--request','-',request={'expected_revision':0,'commands':[{'operation':'set_mesh_asset','id':'mesh','asset':asset}]})
        topology=call('scene','inspect','--mesh-asset','mesh','--selection-topology')['selection_topology']
        assert len(topology['edges'])==4 and len(topology['faces'])==1
        boundary={id for id,pair in topology['edges'].items() if set(pair)<=set('abc')};assert len(boundary)==3
        assert {tuple(sorted(pair)) for id,pair in topology['edges'].items() if id in boundary}=={('a','b'),('a','c'),('b','c')}
        face={'kind':'triangle','id':'t'}
        cases=[
            ('non_manifold',{'kind':'non_manifold','extend':False,'wire':True,'boundary':False,'multiple_faces':False,'non_contiguous':False,'vertices':False},'vertex',[],[],['wire_a','wire_b'],['wire'],[],['vertex']),
            ('loose',{'kind':'loose'},'vertex',[],[],['island'],[],[],['vertex']),
            ('interior',{'kind':'interior_faces'},'face',[],[],[],[],[],['face']),
            ('sides',{'kind':'faces_by_sides','count':3,'extend':False},'face',[],[],list('abc'),boundary,[face],['face']),
            ('poles',{'kind':'poles','count':1,'comparison':'equal','exclude_nonmanifold':False},'vertex',[],[],['wire_a','wire_b'],['wire'],[],['vertex']),
            ('ungrouped',{'kind':'ungrouped'},'vertex',[],[],['c','island','wire_a','wire_b'],['wire'],[],['vertex']),
            ('mode',{'kind':'mode','domain':'face'},'vertex',['a'],[],[],[],[],['face']),
            ('expand',{'kind':'mode','domain':'face','expand':True},'vertex',['a'],[],list('abc'),boundary,[face],['face']),
            ('contract',{'kind':'mode','domain':'vertex','expand':True},'face',[],[face],list('abc'),boundary,[face],['vertex']),
            ('combined',{'kind':'mode','domain':'edge','action':'enable','extend':True},'vertex',['a'],[],['a'],[],[],['vertex','edge']),
        ]
        revision=1
        for name,selector,mode,seed_v,seed_f,expected_v,expected_e,expected_f,expected_mode in cases:
            editing={'mode':[mode],'selected':{'vertices':seed_v,'faces':seed_f},'hidden':{},'history':[],'active_face':None}
            call('scene','apply','--request','-',request={'expected_revision':revision,'commands':[{'operation':'set_mesh_editing','id':'mesh','editing':editing}]});revision+=1
            receipt=call('scene','apply','--request','-',request={'expected_revision':revision,'commands':[{'operation':'select_mesh','id':'mesh','selector':selector}]});revision+=1
            query=call('scene','inspect','--mesh-asset','mesh');actual=query['mesh_asset'];state=actual['editing']
            assert receipt['selection'][0]['outcome']=='completed'
            assert state['selected']=={'vertices':sorted(expected_v),'edges':sorted(expected_e),'faces':expected_f},(name,state)
            assert state['mode']==expected_mode,(name,state)
            assert {key:value for key,value in actual.items() if key!='editing'}==asset
            records.append({'case':name,'passed':True,'editing':state})
        report={'passed':True,'source_repository_reads':'denied by macOS sandbox','policy':policy,
                'denial_control_exit_code':control.returncode,'denial_control_stderr':control.stderr,'runs':records,
                'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'requests_and_responses':calls,'full_feature_acceptance':'unrun'}
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'passed':True,'unseen_selection_cases':len(records),'source_repository_reads':'denied'}))


if __name__=='__main__':main()

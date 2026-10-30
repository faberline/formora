import argparse,gzip,json,traceback
from pathlib import Path
from compare_multi_mesh_merge_reference import validate_run,load_capture
parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
s_path=Path.cwd()/'baseline/fixtures/mesh-merge-multi-data.json';s=json.loads(s_path.read_text());folder=args.folder.resolve();ids=json.loads((folder.parent/'pilot-cases-02.json').read_text())['cases'];runs=[r for r in s['runs'] if r['id'] in ids]
rows=[]
try:load_capture(folder,s_path,runs,True);header={'passed':True}
except Exception as e:header={'passed':False,'error':str(e),'traceback':traceback.format_exc()}
for p in sorted(folder.glob('*.json.gz')):
 data=json.loads(gzip.decompress(p.read_bytes()))
 try:outcome=validate_run(s,data['run'],data);rows.append({'id':data['run']['id'],'passed':True,'outcome':outcome})
 except Exception as e:rows.append({'id':data['run']['id'],'passed':False,'error':str(e),'traceback':traceback.format_exc()})
result={'scope':'focused_diagnostic_only','total':len(rows),'passed':sum(r['passed'] for r in rows),'header':header,'rows':rows}
with (folder.parent/(folder.name+'-initial-check.json')).open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'total':len(rows),'passed':result['passed'],'header':header,'first_failure':next((r for r in rows if not r['passed']),None),'failure_types':sorted(set(r['error'] for r in rows if not r['passed']))[:10]}))
raise SystemExit(0 if header['passed'] and result['passed']==len(rows) else 1)

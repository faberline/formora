"""Author multiple-data merge contexts without reading any measured output."""
from itertools import product
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
contexts=[{'id':'active_a','active':'a','order':['parent','a','b','alias','untouched']},{'id':'active_alias','active':'alias','order':['parent','b','a','alias','untouched']},{'id':'active_b_a_first','active':'b','order':['parent','a','alias','b','untouched']},{'id':'active_b_alias_first','active':'b','order':['parent','alias','a','b','untouched']}]
modes=[['VERT'],['EDGE'],['FACE'],['VERT','EDGE'],['VERT','FACE'],['EDGE','FACE'],['VERT','EDGE','FACE']]
selections=['both','active_empty','other_empty','neither'];histories=['both_vertex','active_first_only','active_last_only','active_none','other_none','both_reverse'];methods=['CENTER','CURSOR','COLLAPSE','FIRST','LAST']
runs=[]
for context,selection,history,method,uvs,mode,frame in product(contexts,selections,histories,methods,[False,True],modes,['identity','noncommuting']):
 available=method not in ['FIRST','LAST'] or ('VERT' in mode and selection in ['both','other_empty'] and history!='active_none' and not (method=='FIRST' and history=='active_last_only') and not (method=='LAST' and history=='active_first_only'))
 runs.append({'id':f'multi_merge_{len(runs):05}','context':context['id'],'selection':selection,'history':history,'parameters':{'type':method,'uvs':uvs},'mode':mode,'frame':frame,'expected_enum_unavailable':not available})
assert len(runs)==13440 and len({r['id'] for r in runs})==13440
assert sum(r['expected_enum_unavailable'] for r in runs)==4352
suite={'schema_version':1,'scope':'authored multi-independent-data merge contexts; native execution unrun','source_commit':'e13b728c6880d3084d9d57c30031ed5df8b39dee','contexts':contexts,'data_sharing':{'a':'mesh_a','alias':'mesh_a','b':'mesh_b','untouched':'mesh_outside'},'active_edit_data':['mesh_a','mesh_b'],'outside_edit_data':['mesh_outside'],'selection_rule':'select the whole data mesh or none; flush by the declared mask; empty selection has empty history','history_rule':'use selected vertex/edge/face endpoints; vertex endpoints permit FIRST/LAST only when VERT mode is enabled; opposite endpoint uses a selected edge for first-only/last-only; other_none affects only the other data mesh','comparison':{'positions_metres':1e-6,'normals':1e-6,'matrices':1e-6,'uv':1e-6,'weights':1e-6,'discrete':'exact'},'expected_cases':13440,'expected_enum_unavailable':4352,'expected_operator_finished':9088,'product_acceptance':'unrun','native_execution':'unrun','runs':runs}
raw=(json.dumps(suite,indent=2)+'\n').encode();path=HERE/'authored-context-cases.json';assert not path.exists();path.write_bytes(raw)
print(json.dumps({'authored_cases':len(runs),'expected_enum_rejections':4352,'native_execution':'unrun','suite_sha256':hashlib.sha256(raw).hexdigest(),'measured_outputs_read':False}))

"""Corrupt real MCP evidence and require each false claim to be rejected."""
import copy
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('merge_api',HERE/'runtime-cli-mcp.py')
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
raw=api.pilot.load(Path('/private/tmp/formora-merge-api-pilot-01/official_mcp_sdk-merge_0000.json.gz'))
case=raw['case'];references=[api.pilot.load(api.ROOT/'docs/evidence/mesh-merge-baseline'/name/(case['id']+'.json.gz')) for name in ['native-01','native-02']]
api.check_record(case,references,raw)
def count(record):record['result']['merges'][0]['after']['vertices']+=1
def changed(record):record['result']['merges'][0]['changed']['edges']=[]
def lineage(record):record['result']['merges'][0]['source_to_survivor']['vertices']['v000002']='v000000'
def shared(record):record['result']['merges'][0]['shared_instances']=[]
def receipt(record):record['result']['merges']=[]
def reload(record):record['saved_scene']['revision']+=1
def raw_result(record):record['mcp_responses'][2]['response']['structured_content']['revision']+=1
def missing_response(record):record['mcp_responses'].pop()
def duplicate_response(record):record['mcp_responses'].append(copy.deepcopy(record['mcp_responses'][-1]))
def request(record):record['mcp_responses'][0]['arguments']['expected_revision']=7
def native_exit(record):record['cli_processes'][-1]['exit']=1
rows=[]
for mutate in [count,changed,lineage,shared,receipt,reload,raw_result,missing_response,duplicate_response,request,native_exit]:
    record=copy.deepcopy(raw);mutate(record)
    if mutate in [count,changed,lineage,shared,receipt]:
        response=next(row['response'] for row in record['mcp_responses'] if row['tool']=='scene_apply' and row['arguments']['expected_revision']==1)
        response['structured_content']=copy.deepcopy(record['result'])
    try:api.check_record(case,references,record)
    except (AssertionError,ValueError,KeyError) as error:rows.append({'control':mutate.__name__,'rejected':True,'error':str(error)})
    else:raise AssertionError('false evidence accepted: '+mutate.__name__)
assert raw==api.pilot.load(Path('/private/tmp/formora-merge-api-pilot-01/official_mcp_sdk-merge_0000.json.gz'))
print(json.dumps({'passed':True,'controls':rows,'original_evidence_unchanged':True,'limits_unchanged':True,'product_acceptance':'unrun'},indent=2))

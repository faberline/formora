"""Use the public official file API and retain unsuccessful raw-URL attempts."""
from pathlib import Path
import base64
import gzip
import hashlib
import json
import urllib.request

ROOT=Path('/private/tmp/formora-merge-distance-baseline');INPUT=Path('/private/tmp/formora-distance-manual-retrieval-06')
OUT=ROOT/'baseline/sources/mesh-merge-distance';API='https://projects.blender.org/api/v1/repos/blender/blender-manual'
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Formora-source-baseline/1.0'}),timeout=20).read()
reply=get(API+'/branches/blender-v5.2-release');branch=json.loads(reply);commit=branch['commit']['id']
assert len(commit)==40 and all(x in '0123456789abcdef' for x in commit)
relative='manual/modeling/meshes/editing/mesh/merge.rst'
api_url=API+'/contents/'+relative+'?ref='+commit
file_reply=get(api_url);item=json.loads(file_reply)
assert item['encoding']=='base64' and item['path']==relative
raw=base64.b64decode(item['content'])
assert raw==(INPUT/'response-1.bin').read_bytes(), 'manual changed during retrieval'
blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();assert blob==item['sha']
sha=lambda b:hashlib.sha256(b).hexdigest()
html=(INPUT/'response-0.bin').read_bytes();compressed=gzip.compress(html,mtime=0)
for name,data in [('merge.rst',raw),('merge.html.gz',compressed),('manual-branch-response.json',reply),('manual-file-api-response.json',file_reply)]:
    with (OUT/name).open('xb') as stream:stream.write(data)
result={'manual_repository':'https://projects.blender.org/blender/blender-manual','branch':'blender-v5.2-release',
        'manual_commit':commit,'source_path':relative,'immutable_source_api':api_url,'git_blob':blob,
        'manual_page':'https://docs.blender.org/manual/en/5.2/modeling/meshes/editing/mesh/merge.html',
        'source_sha256':sha(raw),'html_sha256':sha(html),'stored_html_sha256':sha(compressed),
        'branch_response_sha256':sha(reply),'file_api_response_sha256':sha(file_reply),'branch_and_immutable_bytes_equal':True,
        'content_reviewed':True,'review_scope':'distance merge subsection only; full page also describes mesh.merge',
        'documented_options':['Merge Distance','Centroid Merge','Unselected','Sharp Edges'],
        'numeric_boundary_authority':'fixed native source and independently authored next-f32 diagnostics; prose says closer than',
        'failed_raw_commit_requests':{'count':2,'http_status':403,'retained_logs':str(INPUT)},
        'all_manual_function_contracts_accepted':False,'full_source_gate':'unrun','product_acceptance':'unrun'}
with (OUT/'manual-manifest-09.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps({'manual_commit':commit,'source_bytes':len(raw),'html_bytes':len(html),'content_reviewed':True,'full_source_gate':'unrun'}))

"""Bind retrieved manual source bytes to an immutable official Git commit."""
from pathlib import Path
import gzip
import hashlib
import json
import urllib.request

ROOT=Path('/private/tmp/formora-merge-distance-baseline')
INPUT=Path('/private/tmp/formora-distance-manual-retrieval-06')
OUT=ROOT/'baseline/sources/mesh-merge-distance'
url='https://projects.blender.org/api/v1/repos/blender/blender-manual/branches/blender-v5.2-release'
reply=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Formora-source-baseline/1.0"}),timeout=20).read()
branch=json.loads(reply);commit=branch['commit']['id']
assert len(commit)==40 and all(x in '0123456789abcdef' for x in commit)
relative='manual/modeling/meshes/editing/mesh/merge.rst'
raw_url='https://projects.blender.org/blender/blender-manual/raw/commit/'+commit+'/'+relative
raw=urllib.request.urlopen(urllib.request.Request(raw_url,headers={"User-Agent":"Formora-source-baseline/1.0"}),timeout=20).read()
assert raw==(INPUT/'response-1.bin').read_bytes(), 'manual changed during retrieval'
with (OUT/'merge.rst').open('xb') as stream:stream.write(raw)
html=(INPUT/'response-0.bin').read_bytes();compressed=gzip.compress(html,mtime=0)
with (OUT/'merge.html.gz').open('xb') as stream:stream.write(compressed)
with (OUT/'manual-branch-response.json').open('xb') as stream:stream.write(reply)
sha=lambda b:hashlib.sha256(b).hexdigest()
result={'manual_repository':'https://projects.blender.org/blender/blender-manual','branch':'blender-v5.2-release',
        'manual_commit':commit,'source_path':relative,'immutable_source_url':raw_url,
        'manual_page':'https://docs.blender.org/manual/en/5.2/modeling/meshes/editing/mesh/merge.html',
        'source_sha256':sha(raw),'html_sha256':sha(html),'stored_html_sha256':sha(compressed),
        'branch_response_sha256':sha(reply),'branch_and_immutable_bytes_equal':True,
        'content_reviewed':True,'review_scope':'distance merge subsection only; full page also describes mesh.merge',
        'documented_options':['Merge Distance','Centroid Merge','Unselected','Sharp Edges'],
        'numeric_boundary_authority':'fixed native source and independently authored next-f32 diagnostics; prose says closer than',
        'all_manual_function_contracts_accepted':False,'full_source_gate':'unrun','product_acceptance':'unrun'}
with (OUT/'manual-manifest-07.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps({'manual_commit':commit,'source_bytes':len(raw),'html_bytes':len(html),'content_reviewed':True,'full_source_gate':'unrun'}))

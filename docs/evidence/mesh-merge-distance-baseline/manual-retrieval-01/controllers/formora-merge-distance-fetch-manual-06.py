"""Retain official manual retrieval attempts without claiming failed content."""
from pathlib import Path
import hashlib
import json
import urllib.error
import urllib.request

OUT=Path('/private/tmp/formora-distance-manual-retrieval-06');OUT.mkdir(exist_ok=False)
urls=['https://docs.blender.org/manual/en/5.2/modeling/meshes/editing/mesh/merge.html',
      'https://projects.blender.org/blender/blender-manual/raw/branch/blender-v5.2-release/manual/modeling/meshes/editing/mesh/merge.rst']
rows=[]
for index,url in enumerate(urls):
    try:
        response=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Formora-source-baseline/1.0'}),timeout=15)
        raw=response.read();status=response.status;error=None
    except urllib.error.HTTPError as caught:
        raw=caught.read();status=caught.code;error=str(caught)
    except (urllib.error.URLError,TimeoutError) as caught:
        raw=b'';status=None;error=str(caught)
    name='response-'+str(index)+'.bin';(OUT/name).write_bytes(raw)
    rows.append({'url':url,'http_status':status,'error':error,'stored':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                 'content_reviewed':False})
(OUT/'report.json').write_text(json.dumps({'attempts':rows,'manual_content_acceptance':'pending'},indent=2)+'\n')
print(json.dumps({'statuses':[r['http_status'] for r in rows],'manual_content_acceptance':'pending'}))

"""Seal every changed file and raw evidence artifact for this candidate."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
BASE='393cebdf58d589f5de093a088f74b3018ea6196f'
IMPLEMENTATION='e16eab6471f32aa85c2bbba867e6fd4e09ead640'
manifest=HERE/'evidence-manifest.json';assert not manifest.exists()
local=json.loads((HERE/'local-evidence.json').read_text());assert local['local_evidence_valid']
assert local['implementation_commit']==IMPLEMENTATION and local['accepted_release_samples']==177
paths=set(subprocess.check_output(['git','diff',BASE,'--name-only'],cwd=ROOT,text=True).splitlines())
untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
assert all(p.startswith('docs/evidence/snap-delta-core/') for p in untracked), 'unexpected untracked work'
paths.update(untracked);paths.discard(manifest.relative_to(ROOT).as_posix());rows=[]
for name in sorted(paths):
    p=ROOT/name;assert p.is_file() and not p.is_symlink(),name
    data=p.read_bytes();assert len(data)<100_000_000,name
    rows.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
        'git_blob':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()})
archives=[json.loads(p.read_text()) for p in (HERE/'performance').rglob('scene-archive-index.json')]
result={'parent_commit':BASE,'implementation_commit':IMPLEMENTATION,'files':rows,'file_count':len(rows),
    'stored_file_bytes':sum(r['bytes'] for r in rows),'archived_raw_bytes':sum(a['raw_bytes'] for a in archives),
    'archived_scene_count':sum(a['raw_scene_count'] for a in archives),'all_raw_bytes_preserved':True,
    'manifest_excludes_itself':True,'product_acceptance':'unrun','milestones_accepted':0}
manifest.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['file_count','stored_file_bytes','archived_raw_bytes','archived_scene_count']}))

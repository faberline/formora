"""Retry the immutable manual request with the same declared user agent."""
from pathlib import Path
import json
import subprocess

original=Path('/private/tmp/formora-merge-distance-pin-manual-07.py')
retry=Path('/private/tmp/formora-merge-distance-pin-manual-08.py')
raw=original.read_text().replace('urllib.request.urlopen(url,timeout=20)',
    'urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Formora-source-baseline/1.0"}),timeout=20)').replace(
    'urllib.request.urlopen(raw_url,timeout=20)',
    'urllib.request.urlopen(urllib.request.Request(raw_url,headers={"User-Agent":"Formora-source-baseline/1.0"}),timeout=20)')
with retry.open('x') as stream:stream.write(raw)
result=subprocess.run(['/Users/chrischeng/.pyenv/versions/3.12.11/bin/python3',str(retry)],capture_output=True,text=True)
out=Path('/private/tmp/formora-distance-manual-retrieval-06')
(out/'immutable-retry-08-stdout').write_text(result.stdout)
(out/'immutable-retry-08-stderr').write_text(result.stderr)
(out/'immutable-retry-08-terminal.json').write_text(json.dumps({'terminal_exit_code':result.returncode,
    'first_immutable_request_exit':1,'first_error':'HTTP Error 403: Forbidden','retry_change':'same explicit user-agent as successful branch retrieval'},indent=2)+'\n')
print(result.stdout,end='');print(result.stderr,end='')
raise SystemExit(result.returncode)

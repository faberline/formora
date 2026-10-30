"""Record actual native repository-read denial and unrepaired UV failures."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
OUTPUT=Path('/private/tmp/formora-merge-unseen-after-01')
BINARY=Path('/private/tmp/formora-merge-unseen-core-after-01')
OUTPUT.mkdir(exist_ok=False)
profile='(version 1) (allow default) (deny file-read* (subpath "/Users/chrischeng/faberlines/formora") (subpath "/private/tmp/formora-mesh-merge-sparse") (regex #"^/(private/)?tmp/formora-merge-(api|pilot|performance)"))'
(OUTPUT/'profile.sb').write_text(profile+'\n')
rows=[]
for root in [ROOT,Path('/Users/chrischeng/faberlines/formora')]:
    command=['/usr/bin/sandbox-exec','-p',profile,'/bin/cat',str(root/'Cargo.toml')]
    process=subprocess.run(command,capture_output=True,text=True,cwd='/private/tmp')
    rows.append({'command':command,'exit':process.returncode,'stdout':process.stdout,'stderr':process.stderr})
    assert process.returncode==1 and not process.stdout and 'Cargo.toml' in process.stderr and ('Operation not permitted' in process.stderr or 'Permission denied' in process.stderr),'native denial control did not prove the intended file read was denied'
command=['/usr/bin/sandbox-exec','-p',profile,str(BINARY),'--nocapture']
process=subprocess.run(command,capture_output=True,text=True,cwd='/private/tmp')
(OUTPUT/'stdout').write_text(process.stdout);(OUTPUT/'stderr').write_text(process.stderr)
report={'repository_reads_denied':True,'denial_controls':rows,'native_command':command,'native_terminal_exit':process.returncode,
    'native_executable_sha256':hashlib.sha256(BINARY.read_bytes()).hexdigest(),'product_library_sha256':'86ad80551979b51ac339b83b2733455f589abdb486448afa19cd204d50e654ea',
    'product_implementation':'224a4360276511f48d023a2f6f39190010dae731','interface':'native Rust API; separate from the CLI/MCP gate',
    'all_functional_controls_passed':process.returncode==0,'product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUTPUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:report[key] for key in ['repository_reads_denied','native_terminal_exit','all_functional_controls_passed']}),flush=True)
raise SystemExit(0 if process.returncode==0 else 1)

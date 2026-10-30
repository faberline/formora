"""Build five unchanged retained timing drivers against the current Rust library."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[4]
OUT=Path('/private/tmp/formora-merge-retained-compile-01');OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
lib=Path('/private/tmp/formora-merge-target-actual185/release/libformora.rlib')
assert sha(lib)=='86ad80551979b51ac339b83b2733455f589abdb486448afa19cd204d50e654ea'
rows=json.loads(Path(__file__).with_name('retained-compile-config-01.json').read_text())
for row in rows:
 command=row['command'];source=Path(command[5]);assert sha(source)==row['driver_source_sha256']
 with (OUT/(row['name']+'.stdout')).open('xb') as stdout,(OUT/(row['name']+'.stderr')).open('xb') as stderr:
  child=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr);code=child.wait()
 row.update(terminal_exit_code=code,native_process_id=child.pid)
 if code==0:row['driver_sha256']=sha(Path(command[7]))
 (OUT/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
 print(json.dumps({'name':row['name'],'terminal_exit_code':code}),flush=True)
assert sha(lib)=='86ad80551979b51ac339b83b2733455f589abdb486448afa19cd204d50e654ea'
report={'passed':all(r['terminal_exit_code']==0 for r in rows),'drivers':rows,'library_sha256':sha(lib),'implementation_commit':'224a4360276511f48d023a2f6f39190010dae731','source_drivers_changed':False}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)

import hashlib,json,os,subprocess,time,sys
from pathlib import Path

root=Path('/Users/chrischeng/faberlines/formora');binary=Path('/private/tmp/formora-target-actual185/debug/formora')
out=root/'docs/evidence/snap-rotation-core/retained';out.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
binary_sha=sha(binary);source={p.relative_to(root).as_posix():sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])};records=[]
commands=[
 ('primitive','tools/primitive_reference_smoke.py',162),('scale','tools/remaining_scale_regression.py',8),
 ('selection','tools/selection_runtime_smoke.py',1060),('creation','tools/creation_context_runtime.py',262),
 ('payload','tools/polygon_reference_smoke.py',57),('normal','tools/normal_runtime_smoke.py',42),
 ('rng','tools/random_falloff_runtime.py',96),('mcp','tools/mcp_smoke.py',None)]
for name,tool,count in commands:
 command=[sys.executable,tool,str(binary)]
 if name!='mcp':command.append(str(out/name))
 start=time.monotonic_ns();result=subprocess.run(command,cwd=root,capture_output=True,text=True,env=os.environ);end=time.monotonic_ns()
 (out/(name+'.stdout')).write_text(result.stdout);(out/(name+'.stderr')).write_text(result.stderr)
 passed=result.returncode==0;report=None;actual=None
 if name!='mcp' and passed:
  path=out/name/('manifest.json' if name=='normal' else 'report.json');report=json.loads(path.read_text());passed &= report['passed'] is True
  actual=report.get('checks',report.get('cases',len(report.get('runs',[]))));passed &= actual==count
 record={'name':name,'command':command,'exit_code':result.returncode,'passed':passed,'expected_checks':count,'actual_checks':actual,'start_ns':start,'end_ns':end};records.append(record);print(json.dumps(record),flush=True)
unchanged=sha(binary)==binary_sha and source=={p.relative_to(root).as_posix():sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])}
report={'passed':unchanged and all(r['passed'] for r in records),'binary_sha256':binary_sha,'implementation_commit':'c67d2370c00d2031adb7d896c978b25ffdd3d885','driver_sha256':sha(Path(__file__)),'source_hashes':source,'verification_inputs_unchanged':unchanged,'checks':records,'product_acceptance':'unrun'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(0 if report['passed'] else 1)

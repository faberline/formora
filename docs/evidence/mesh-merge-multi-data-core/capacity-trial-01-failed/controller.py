from pathlib import Path
import hashlib,json,subprocess,time
root=Path.cwd();out=Path('/private/tmp/formora-multi-data-capacity-product-01');out.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();build=json.loads(Path('/private/tmp/formora-multi-merge-build-01/build-bindings.json').read_text());assert build['implementation_commit']=='9a0919e4899a6376bac2b03df0d45d22115d224d';lib=Path(build['artifacts']['release-lib']['path']);assert sha(lib)==build['artifacts']['release-lib']['sha256'];source=root/'docs/evidence/mesh-merge-multi-data-core/capacity-driver.rs';inputs=root/'docs/evidence/mesh-merge-multi-data-core/capacity-authored-inputs';binary=out/'capacity-driver';deps=lib.parent/'deps';serde=next(deps.glob('libserde_json-*.rlib'));hashes={str(p):sha(p) for p in [source,lib,serde,inputs/'authored-grid.json',inputs/'authored-forms.json']}
command=['/private/tmp/formora-rustup-cache/toolchains/1.85.0-aarch64-apple-darwin/bin/rustc','--edition','2024','-C','opt-level=3',str(source),'--extern','formora='+str(lib),'--extern','serde_json='+str(serde),'-L','dependency='+str(deps),'-o',str(binary)]
with (out/'compile.stdout').open('x') as so,(out/'compile.stderr').open('x') as se:code=subprocess.call(command,stdout=so,stderr=se)
report={'implementation_commit':build['implementation_commit'],'compile_command':command,'compile_exit_code':code,'input_hashes':hashes,'product_timing_passed':False,'product_acceptance':'unrun'}
if code==0:
 command=[str(binary),str(inputs),str(out/'samples')];started=time.monotonic()
 with (out/'timing.stdout').open('x') as so,(out/'timing.stderr').open('x') as se:process=subprocess.Popen(command,stdout=so,stderr=se);report['process_id']=process.pid;code=process.wait()
 report.update(command=command,actual_exit_code=code,elapsed_seconds=time.monotonic()-started,test_binary_sha256=sha(binary))
 if (out/'samples/timing-summary.json').exists():
  data=json.loads((out/'samples/timing-summary.json').read_text());report.update(samples=data['samples'],maximum_core_ms=max(r['core_ms'] for r in data['runs']),maximum_pipeline_ms=max(r['operation_save_reload_ms'] for r in data['runs']),failed_samples=sum(not r['passed'] for r in data['runs']));report['product_timing_passed']=code==0 and data['passed'] and data['samples']==30
report['inputs_unchanged']=hashes=={p:sha(p) for p in hashes};report['product_timing_passed'] &= report['inputs_unchanged'];(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True);raise SystemExit(0 if report['product_timing_passed'] else 1)

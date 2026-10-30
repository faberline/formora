from pathlib import Path
import hashlib,json,subprocess,re,time
root=Path.cwd();out=Path('/private/tmp/formora-multi-data-before-code-01');out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
lib=Path('/private/tmp/formora-merge-regen-target-actual185/release/libformora.rlib');serde=Path('/private/tmp/formora-merge-regen-target-actual185/release/deps/libserde_json-7ab9b385339e8dcd.rlib');test=root/'tests/mesh_merge_multi_data.rs';contract=root/'docs/contracts/mesh-merge-multi-data-core.md';inputs={str(p):sha(p) for p in [lib,serde,test,contract]}
rustc=Path('/private/tmp/formora-rustup-cache/toolchains/1.85.0-aarch64-apple-darwin/bin/rustc');binary=out/'multi-data-before-code-tests'
command=[str(rustc),'--edition','2024','--test','-C','opt-level=3',str(test),'--extern','formora='+str(lib),'--extern','serde_json='+str(serde),'-L','dependency='+str(serde.parent),'-o',str(binary)]
with (out/'compile.stdout').open('x') as so,(out/'compile.stderr').open('x') as se:code=subprocess.call(command,stdout=so,stderr=se)
report={'issue':79,'product_implementation_changed':False,'compile_command':command,'compile_exit_code':code,'input_hashes':inputs,'before_code_behavior_gate':False,'product_acceptance':'unrun'}
if code==0:
 with (out/'tests.stdout').open('x') as so,(out/'tests.stderr').open('x') as se:code=subprocess.call([str(binary),'--test-threads=1','--nocapture'],stdout=so,stderr=se)
 report.update(test_command=[str(binary),'--test-threads=1','--nocapture'],test_exit_code=code,test_binary_sha256=sha(binary))
 text=(out/'tests.stdout').read_text();match=re.search(r'test result: FAILED\. (\d+) passed; (\d+) failed; (\d+) ignored;',text)
 if match:report.update(passed=int(match[1]),failed=int(match[2]),ignored=int(match[3]))
 errors=(out/'tests.stderr').read_text();report['new_operation_rejected_as_unknown']=errors.count('unknown variant `merge_edit_meshes`')
 report['before_code_behavior_gate']=(code==101 and match is not None and tuple(map(int,match.groups()))==(1,7,0) and 'legacy_entity_merge_still_only_changes_its_explicit_asset ... ok' in text and report['new_operation_rejected_as_unknown']==7)
report['inputs_unchanged']=inputs=={p:sha(p) for p in inputs};report['before_code_behavior_gate'] &= report['inputs_unchanged']
with (out/'report.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report),flush=True)
raise SystemExit(0 if report['before_code_behavior_gate'] else 1)

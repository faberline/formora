from pathlib import Path
import subprocess,os,json,hashlib
root=Path.cwd();out=Path('/private/tmp/formora-multi-merge-build-02');target=Path('/private/tmp/formora-multi-merge-target-actual185');environment=os.environ.copy();environment.update(PATH='/private/tmp/formora-rustup-cache/toolchains/1.85.0-aarch64-apple-darwin/bin:/usr/bin:/bin:/usr/sbin:/sbin',RUSTUP_HOME='/private/tmp/formora-rustup-cache',CARGO_HOME='/private/tmp/formora-cargo-cache',CARGO_TARGET_DIR=str(target),RUSTC='/private/tmp/formora-rustup-cache/toolchains/1.85.0-aarch64-apple-darwin/bin/rustc',RUSTDOC='/private/tmp/formora-rustup-cache/toolchains/1.85.0-aarch64-apple-darwin/bin/rustdoc')
report={'implementation_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'commands':[],'artifacts':{}}
steps=[('preview',['cargo','build','--offline','--features','preview','--bin','formora'],target/'debug/formora',out/'formora-preview'),('default',['cargo','build','--offline','--bin','formora'],target/'debug/formora',None),('release-lib',['cargo','build','--offline','--release','--lib'],target/'release/libformora.rlib',None)]
for name,command,artifact,copy in steps:
 with (out/(name+'-build.stdout')).open('x') as so,(out/(name+'-build.stderr')).open('x') as se:code=subprocess.call(command,env=environment,stdout=so,stderr=se)
 report['commands'].append({'name':name,'command':command,'exit_code':code});assert code==0,(name,code)
 if copy is not None:
  copy.write_bytes(artifact.read_bytes());copy.chmod(0o755);artifact=copy
 report['artifacts'][name]={'path':str(artifact),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
 print(json.dumps({'built':name,'exit_code':code,'sha256':report['artifacts'][name]['sha256']}),flush=True)
(out/'build-bindings.json').write_text(json.dumps(report,indent=2)+'\n')

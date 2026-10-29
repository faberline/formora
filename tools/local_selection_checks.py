#!/usr/bin/env python3
"""Pin actual compiler child paths and retain full local selection check logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time


def main(expected_rust_tests=101, expected_python_tests=47, extra_examples=(), extra_source_directories=()):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('toolchain_bin',type=Path);parser.add_argument('target',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();toolchain=args.toolchain_bin.resolve();target=args.target.resolve();output=args.output.resolve()
    root=Path(__file__).resolve().parents[1];output.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'PATH':str(toolchain)+os.pathsep+os.environ['PATH'],'RUSTC':str(toolchain/'rustc'),
         'RUSTDOC':str(toolchain/'rustdoc'),'CARGO_TARGET_DIR':str(target)}
    cargo=str(toolchain/'cargo');versions={}
    for name,arguments in [('rustc',[str(toolchain/'rustc'),'--version']),('cargo',[cargo,'--version']),
                           ('clippy',[cargo,'clippy','--version']),('rustfmt',[cargo,'fmt','--version'])]:
        versions[name]=subprocess.check_output(arguments,cwd=root,env=env,text=True).strip()
    assert versions['rustc'].startswith('rustc 1.85.0 '),versions
    assert versions['cargo'].startswith('cargo 1.85.0 '),versions
    assert versions['clippy'].startswith('clippy 0.1.85 '),versions
    assert versions['rustfmt'].startswith('rustfmt 1.8.0-stable '),versions
    def input_files():
        return [root/'Cargo.toml',root/'Cargo.lock',root/'.gitattributes',root/'.github/workflows/contracts.yml',
                *[p for directory in ['src','tests','examples','tools','docs/contracts','docs/evidence/remaining-primitives/source',*extra_source_directories]
                  for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']]
    files=input_files()
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    snapshot={str(p.relative_to(root)):sha(p) for p in sorted(files)}
    binary=target/'debug/formora';records=[]
    commands=[('format',[cargo,'fmt','--all','--check'],0),
              ('clippy',[cargo,'clippy','--locked','--all-features','--all-targets','--','-D','warnings'],0),
              ('rust-tests',[cargo,'test','--locked','--all-features','--all-targets'],0),
              ('python-tests',['python3','-m','unittest','discover','-s','tools/tests','-v'],0),
              ('build',[cargo,'build','--locked','--all-features'],0),
              ('mcp-regression',['python3','tools/mcp_smoke.py',str(binary)],0),
              ('strict-baseline',[str(binary),'baseline','check','--root','.', '--strict'],2),
              *[(name,[cargo,'run','--locked','--release','--example',example],0) for name,example in [
                  ('triangle-performance','mesh_asset_bench'),('polygon-performance','polygon_asset_bench'),
                  ('primitive-performance','primitive_generation_bench')]],
              *[(example,[cargo,'run','--locked','--release','--example',example],0) for example in extra_examples]]
    for name,command,expected in commands:
        start=time.monotonic_ns();result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True);end=time.monotonic_ns()
        (output/(name+'.stdout')).write_text(result.stdout);(output/(name+'.stderr')).write_text(result.stderr)
        records.append({'name':name,'command':command,'exit_code':result.returncode,'expected_exit_code':expected,
                        'passed':result.returncode==expected,'start_ns':start,'end_ns':end})
        print(json.dumps(records[-1]),flush=True)
        assert result.returncode==expected,(name,result.stderr)
        if name=='rust-tests':
            totals=re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',result.stdout)
            records[-1]['tests_passed']=sum(map(int,totals));assert records[-1]['tests_passed']==expected_rust_tests
        if name=='python-tests':
            totals=re.findall(r'Ran (\d+) tests? in ',result.stderr);assert totals
            records[-1]['tests_passed']=int(totals[-1]);assert records[-1]['tests_passed']==expected_python_tests
    assert snapshot=={str(p.relative_to(root)):sha(p) for p in sorted(input_files())},'source changed during checks'
    rust_info=json.loads((target/'.rustc_info.json').read_text())
    outputs=[value.get('stdout','') for value in rust_info['outputs'].values()]
    assert any(value.startswith('rustc 1.85.0 ') for value in outputs),rust_info
    (output/'rustc-info.json').write_text(json.dumps(rust_info,indent=2)+'\n')
    manifest={'passed':True,'versions':versions,'platform':platform.platform(),'binary_sha256':sha(binary),
              'compiler_sha256':sha(toolchain/'rustc'),'source_test_tool_contract_hashes':snapshot,'checks':records,
              'artifacts':{p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()},
              'strict_baseline_ready':False,'product_acceptance':'unrun','three_platform_acceptance':'unrun'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()

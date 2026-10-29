#!/usr/bin/env python3
"""Run the baseline issue gates with actual Rust 1.85 child tools and full logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('toolchain_bin',type=Path);parser.add_argument('target',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];bin=args.toolchain_bin.resolve();target=args.target.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'PATH':str(bin)+os.pathsep+os.environ['PATH'],'RUSTC':str(bin/'rustc'),'RUSTDOC':str(bin/'rustdoc'),'CARGO_TARGET_DIR':str(target)}
    cargo=str(bin/'cargo');versions={}
    for name,command in [('rustc',[str(bin/'rustc'),'--version']),('cargo',[cargo,'--version']),('clippy',[cargo,'clippy','--version']),('rustfmt',[cargo,'fmt','--version'])]:versions[name]=subprocess.check_output(command,cwd=root,env=env,text=True).strip()
    for name,prefix in [('rustc','rustc 1.85.0 '),('cargo','cargo 1.85.0 '),('clippy','clippy 0.1.85 '),('rustfmt','rustfmt 1.8.0-stable ')]:assert versions[name].startswith(prefix),versions
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    def inputs():
        return sorted([root/'Cargo.toml',root/'Cargo.lock',root/'.github/workflows/contracts.yml',*[p for directory in ['src','tests','tools','baseline','docs/contracts'] for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']])
    snapshot={str(p.relative_to(root)):sha(p) for p in inputs()};binary=target/'debug/formora';checks=[]
    commands=[('format',[cargo,'fmt','--all','--check'],0),('clippy',[cargo,'clippy','--locked','--all-features','--all-targets','--','-D','warnings'],0),
              ('rust-tests',[cargo,'test','--locked','--all-features','--all-targets'],0),('python-tests',['python3','-m','unittest','discover','-s','tools/tests','-v'],0),
              ('build',[cargo,'build','--locked','--all-features'],0),('baseline-metadata',[str(binary),'baseline','check','--root','.'],0),('strict-baseline',[str(binary),'baseline','check','--root','.', '--strict'],2),
              ('transform-reference',['python3','tools/compare_transform_reference.py','baseline/fixtures/mesh-transform.json','baseline/reference/blender-5.2.3/mesh-transform','baseline/reference/blender-5.2.3/mesh-transform-repeat',str(output/'transform-reference.json')],0),
              ('selection-reference',['python3','tools/compare_selection_reference.py','--suite','baseline/fixtures/mesh-selection.json','--reference','baseline/reference/blender-5.2.3/mesh-selection','--repeat','baseline/reference/blender-5.2.3/mesh-selection-repeat','--output',str(output/'selection-reference.json')],0),
              ('mcp-regression',['python3','tools/mcp_smoke.py',str(binary)],0)]
    for name,command,expected in commands:
        start=time.monotonic_ns();result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True);end=time.monotonic_ns()
        (output/(name+'.stdout')).write_text(result.stdout);(output/(name+'.stderr')).write_text(result.stderr)
        record={'name':name,'command':command,'exit_code':result.returncode,'expected_exit_code':expected,'passed':result.returncode==expected,'start_ns':start,'end_ns':end};checks.append(record);print(json.dumps(record),flush=True)
        assert result.returncode==expected,(name,result.stderr)
        if name=='rust-tests':
            record['tests_passed']=sum(map(int,re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',result.stdout)));assert record['tests_passed']==116
        if name=='python-tests':
            record['tests_passed']=int(re.findall(r'Ran (\d+) tests? in ',result.stderr)[-1]);assert record['tests_passed']==64 and re.search(r'\nOK\s*$',result.stderr)
        if name in ['baseline-metadata','strict-baseline']:
            report=json.loads(result.stdout);assert report['structurally_valid'] and not report['baseline_ready'] and report['problems']==[]
            assert (report['sources'],report['features'],report['pending_sources'],report['pending_features'])==(9047,31,9003,31)
    assert snapshot=={str(p.relative_to(root)):sha(p) for p in inputs()},'verification inputs changed during checks'
    rust_info=json.loads((target/'.rustc_info.json').read_text());assert any(value.get('stdout','').startswith('rustc 1.85.0 ') for value in rust_info['outputs'].values()),rust_info
    (output/'rustc-info.json').write_text(json.dumps(rust_info,indent=2)+'\n')
    (output/'manifest.json').write_text(json.dumps({'passed':True,'scope':'baseline reference checks; no new Rust product transforms','versions':versions,'platform':platform.platform(),'binary_sha256':sha(binary),
        'source_test_tool_baseline_hashes':snapshot,'checks':checks,'artifacts':{p.name:sha(p) for p in output.iterdir() if p.is_file()},
        'strict_baseline_ready':False,'product_acceptance':'unrun','three_platform_ci':'unrun','integrated_acceptance':'unrun'},indent=2)+'\n')


if __name__=='__main__':main()

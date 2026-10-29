#!/usr/bin/env python3
"""Recheck exact dependency commits with real Rust 1.85 child tools."""
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('toolchain',type=Path)
    parser.add_argument('target',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--pr',type=int,required=True);parser.add_argument('--head',required=True)
    args=parser.parse_args();root=args.root.resolve();toolchain=args.toolchain.resolve()
    target=args.target.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    git=lambda *words:subprocess.check_output(['git',*words],cwd=root,text=True).strip()
    assert git('rev-parse','HEAD')==args.head
    assert not git('status','--porcelain'),'worktree is not clean'
    expected={33:(79,32),35:(85,33),37:(90,33),39:(71,46)}[args.pr]
    env={**os.environ,'PATH':str(toolchain)+os.pathsep+os.environ['PATH'],'RUSTC':str(toolchain/'rustc'),
         'RUSTDOC':str(toolchain/'rustdoc'),'CARGO_TARGET_DIR':str(target)}
    cargo=str(toolchain/'cargo');binary=target/'debug/formora'
    versions={}
    for name,command,prefix in [('rustc',[str(toolchain/'rustc'),'--version'],'rustc 1.85.0 '),
            ('cargo',[cargo,'--version'],'cargo 1.85.0 '),('clippy',[cargo,'clippy','--version'],'clippy 0.1.85 '),
            ('rustfmt',[cargo,'fmt','--version'],'rustfmt 1.8.0-stable ')]:
        versions[name]=subprocess.check_output(command,cwd=root,env=env,text=True).strip()
        assert versions[name].startswith(prefix),versions
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    paths=git('ls-files','Cargo.toml','Cargo.lock','src','tests','examples','tools','baseline','.github','docs/contracts').splitlines()
    snapshot={path:sha(root/path) for path in paths}
    commands=[('format',[cargo,'fmt','--all','--check'],0),
              ('clippy',[cargo,'clippy','--locked','--all-features','--all-targets','--','-D','warnings'],0),
              ('rust-tests',[cargo,'test','--locked','--all-features','--all-targets'],0),
              ('python-tests',['python3','-m','unittest','discover','-s','tools/tests','-v'],0),
              ('build',[cargo,'build','--locked','--all-features'],0),
              ('mcp',['python3','tools/mcp_smoke.py',str(binary)],0),
              ('strict-baseline',[str(binary),'baseline','check','--root','.', '--strict'],2)]
    if args.pr in [33,35,37]:
        commands.append(('polygon-payload',['python3','tools/polygon_reference_smoke.py',str(binary),str(output/'polygon-payload')],0))
        commands.extend((name,[cargo,'run','--locked','--release','--example',example],0)
                        for name,example in [('triangle-performance','mesh_asset_bench'),('polygon-performance','polygon_asset_bench')])
    if args.pr in [35,37]:
        commands.append(('primitive-comparison',['python3','tools/primitive_reference_smoke.py',str(binary),str(output/'primitive-comparison')],0))
        commands.append(('primitive-performance',[cargo,'run','--locked','--release','--example','primitive_generation_bench'],0))
    if args.pr==39:
        commands.append(('selection-reference',['python3','tools/compare_selection_reference.py','--suite','baseline/fixtures/mesh-selection.json',
            '--reference','baseline/reference/blender-5.2.3/mesh-selection','--repeat','baseline/reference/blender-5.2.3/mesh-selection-repeat',
            '--output',str(output/'selection-reference.json')],0))
    records=[]
    for name,command,expected_exit in commands:
        start=time.monotonic_ns();result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True);end=time.monotonic_ns()
        (output/(name+'.stdout')).write_text(result.stdout);(output/(name+'.stderr')).write_text(result.stderr)
        record={'name':name,'command':command,'exit_code':result.returncode,'expected_exit_code':expected_exit,
                'command_contract_met':result.returncode==expected_exit,'start_ns':start,'end_ns':end}
        if name=='rust-tests':
            record['tests_passed']=sum(map(int,re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',result.stdout)))
            assert record['tests_passed']==expected[0],record
        if name=='python-tests':
            found=re.findall(r'Ran (\d+) tests? in ',result.stderr);assert found
            record['tests_passed']=int(found[-1]);assert record['tests_passed']==expected[1],record
        records.append(record);print(json.dumps(record),flush=True)
        (output/'progress.json').write_text(json.dumps(records,indent=2)+'\n')
        assert result.returncode==expected_exit,(name,result.stderr)
    assert git('rev-parse','HEAD')==args.head and not git('status','--porcelain')
    assert snapshot=={path:sha(root/path) for path in paths},'tracked input changed'
    rust_info=json.loads((target/'.rustc_info.json').read_text())
    assert any(value.get('stdout','').startswith('rustc 1.85.0 ') for value in rust_info['outputs'].values())
    (output/'rustc-info.json').write_text(json.dumps(rust_info,indent=2)+'\n')
    manifest={'local_command_contracts_met':True,'pr':args.pr,'commit':args.head,'versions':versions,
              'platform':platform.platform(),'binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),
              'tracked_inputs_sha256':snapshot,'checks':records,
              'artifact_hashes':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and not p.name.endswith('.formora.lock')},
              'strict_baseline_ready':False,'required_three_platform_ci':'unrun','integrated_independent_acceptance':'unrun','milestone_acceptance':'unrun'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()

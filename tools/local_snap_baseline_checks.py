#!/usr/bin/env python3
"""Run unchanged product regressions plus the finite snapping source gates."""
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
    for name in ['toolchain-bin','target','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    bin=args.toolchain_bin.resolve();target=args.target.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'PATH':str(bin)+os.pathsep+os.environ['PATH'],'RUSTC':str(bin/'rustc'),'RUSTDOC':str(bin/'rustdoc'),'CARGO_TARGET_DIR':str(target)}
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    def inputs():
        return sorted([root/'Cargo.toml',root/'Cargo.lock',root/'.github/workflows/contracts.yml',
            *[p for directory in ['src','tests','tools','baseline','docs/contracts'] for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']])
    initial={p.relative_to(root).as_posix():sha(p) for p in inputs()};versions={}
    cargo=str(bin/'cargo');binary=target/'debug/formora'
    for name,command in [('rustc',[str(bin/'rustc'),'--version']),('cargo',[cargo,'--version']),('clippy',[cargo,'clippy','--version']),('rustfmt',[cargo,'fmt','--version'])]:versions[name]=subprocess.check_output(command,cwd=root,env=env,text=True).strip()
    for name,prefix in [('rustc','rustc 1.85.0 '),('cargo','cargo 1.85.0 '),('clippy','clippy 0.1.85 '),('rustfmt','rustfmt 1.8.0-stable ')]:assert versions[name].startswith(prefix),versions
    commands=[('format',[cargo,'fmt','--all','--check'],0),
        ('clippy',[cargo,'clippy','--locked','--all-features','--all-targets','--','-D','warnings'],0),
        ('rust-tests',[cargo,'test','--locked','--all-features','--all-targets'],0),
        ('python-tests',['python3','-m','unittest','discover','-s','tools/tests','-v'],0),
        ('build',[cargo,'build','--locked','--all-features'],0),
        ('baseline-metadata',[str(binary),'baseline','check','--root','.'],0),
        ('strict-baseline',[str(binary),'baseline','check','--root','.','--strict'],2),
        ('mcp-regression',['python3','tools/mcp_smoke.py',str(binary)],0)]
    checks=[]
    for name,command,expected in commands:
        start=time.monotonic_ns();p=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True);end=time.monotonic_ns()
        (out/(name+'.stdout')).write_text(p.stdout);(out/(name+'.stderr')).write_text(p.stderr)
        record={'name':name,'command':command,'exit_code':p.returncode,'expected_exit_code':expected,
                'passed':p.returncode==expected,'start_ns':start,'end_ns':end}
        if name=='rust-tests':
            record['tests_passed']=sum(map(int,re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',p.stdout)))
            record['passed'] &= record['tests_passed']==229
        if name=='python-tests':
            counts=re.findall(r'Ran (\d+) tests? in ',p.stderr);record['tests_passed']=int(counts[-1]) if counts else 0
            record['passed'] &= record['tests_passed']==100 and bool(re.search(r'\nOK\s*$',p.stderr))
        if name in ['baseline-metadata','strict-baseline']:
            try:
                report=json.loads(p.stdout)
                record['passed'] &= report['structurally_valid'] and not report['baseline_ready'] and report['problems']==[]
                record['passed'] &= (report['sources'],report['features'],report['pending_sources'],report['pending_features'])==(9047,38,8994,38)
            except (ValueError,KeyError):record['passed']=False
        checks.append(record);print(json.dumps(record),flush=True)
    unchanged=initial=={p.relative_to(root).as_posix():sha(p) for p in inputs()}
    report={'passed':all(c['passed'] for c in checks) and unchanged,'scope':'finite source baseline and retained product regressions',
        'versions':versions,'platform':platform.platform(),'checks':checks,'verification_inputs_unchanged':unchanged,
        'input_hashes':initial,'binary_sha256':sha(binary),'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'source_comparison_report':'baseline/reference/blender-5.2.3/snap-menu-reproduction.json',
        'source_comparison_sha256':sha(root/'baseline/reference/blender-5.2.3/snap-menu-reproduction.json'),
        'strict_baseline_ready':False,'snap_product_acceptance':'unrun','three_platform_ci':'unrun','integrated_acceptance':'unrun'}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()

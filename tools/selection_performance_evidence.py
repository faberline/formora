#!/usr/bin/env python3
"""Retain native release measurements without storing thirty large scratch scenes."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('benchmark',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();binary=args.benchmark.resolve();output=args.output.resolve()
    assert platform.system()=='Darwin'
    hardware=subprocess.check_output(['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
    assert hardware=='Apple M1 Max',hardware
    output.mkdir(parents=True,exist_ok=False);root=Path(__file__).resolve().parents[1]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sources=[root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]]
    before={str(p.relative_to(root)):sha(p) for p in sorted(sources)}
    with tempfile.TemporaryDirectory(prefix='formora-selection-performance-') as folder:
        destination=Path(folder)/'scenes'
        result=subprocess.run([str(binary),str(destination)],capture_output=True,text=True)
        (output/'stdout.jsonl').write_text(result.stdout);(output/'stderr.txt').write_text(result.stderr)
        assert result.returncode==0,result.stderr
        report=json.loads((destination/'report.json').read_text());assert report['passed']
        assert len(report['runs'])==30
        for run in report['runs']:
            assert 0<=run['core_start_ns']<=run['core_end_ns']<=run['pipeline_start_ns']<=run['pipeline_end_ns']
            assert 0<=run['core_ms']<=100 and 0<=run['select_save_reload_ms']<=2000
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        saved={p.name:sha(p) for p in sorted(destination.glob('*.json')) if p.name!='report.json'}
        assert len(saved)==30
    after={str(p.relative_to(root)):sha(p) for p in sorted(sources)};assert before==after
    manifest={'passed':True,'hardware':hardware,'platform':platform.platform(),'profile':'release','exit_code':result.returncode,
              'benchmark_sha256':sha(binary),'source_files_sha256':before,'saved_scenes_sha256':saved,
              'driver_sha256':sha(root/'examples/selection_performance.rs'),'wrapper_sha256':sha(Path(__file__)),
              'artifacts':{p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()},
              'full_feature_acceptance':'unrun','three_platform_acceptance':'unrun'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'passed':True,'runs':30,'maximum_core_ms':max(r['core_ms'] for r in report['runs']),
                      'maximum_select_save_reload_ms':max(r['select_save_reload_ms'] for r in report['runs'])}))


if __name__=='__main__':main()

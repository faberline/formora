#!/usr/bin/env python3
"""Verify stored candidate, case coverage, raw bytes and explicit open gates."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from compare_selection_reference import load, require, digest
from snap_runtime_smoke import covered


def local_path(name):
    p=Path(name);require(not p.is_absolute() and '..' not in p.parts,'nonlocal evidence path')
    path=(ROOT/p).resolve();require(path.is_relative_to(ROOT),'evidence escaped repository')
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=Path);args=parser.parse_args()
    m=load(HERE/'manifest.json');require(m['implementation_commit']=='f3403dc720a6b6e2f26d86af61ad10e9ccdc7f86','candidate differs')
    require(m['milestones_accepted']==0 and m['full_feature_acceptance']=='unrun','finite results cannot accept a milestone')
    for key in ['three_platform_ci','dependency_integration','independent_acceptance']:require(m[key]=='unrun','unrun acceptance gate was relabelled')
    for name,sha in m['artifacts'].items():require(digest(local_path(name))==sha,'artifact content changed: '+name)
    require(not subprocess.check_output(['git','diff',m['implementation_commit'],'--','Cargo.toml','Cargo.lock','src','tests','tools','baseline','.github/workflows/contracts.yml','docs/contracts'],cwd=ROOT),'candidate source changed')
    full=load(HERE/'full/report.json');require(full['passed'] and full['required_full_gate_passed'] and full['verification_inputs_unchanged'],'complete snap gate is missing')
    require(full['checks']==2244 and full['remaining_object_multi_edit_cases']==550,'bounded required scope differs')
    for name,sha in full['input_hashes'].items():require(digest(local_path(name))==sha,'verification input changed: '+name)
    require(full['binary_sha256']==m['binary_sha256'],'snap binary differs')
    if args.binary:require(digest(args.binary)==m['binary_sha256'],'actual binary differs')
    suite=load(ROOT/'baseline/fixtures/snap-menu.json');cases={r['id']:r for r in suite['runs'] if covered(r)}
    require(len(cases)==1122,'authored single edit case set differs')
    identities={(r['interface'],r['id']) for r in full['runs']}
    require(identities=={(interface,id) for interface in ['cli','official_mcp_sdk'] for id in cases} and len(full['runs'])==2244,'missing or duplicate real requests')
    counts=Counter()
    for row in full['runs']:
        require(row['file']==row['interface']+'-'+row['id']+'.json','raw snap path differs')
        path=HERE/'full'/row['file'];require(digest(path)==row['sha256'] and row['status']=='passed','raw snap result changed')
        data=load(path);require(data['case']==cases[row['id']] and data['status']=='passed' and data['comparison_error'] is None,'raw snap case differs')
        require(data['fresh_reload_matches'] is True,'fresh reload was not checked')
        outcome=row['source_outcome'];counts[outcome]+=1
        if outcome=='ERROR':
            require(row['comparison_kind']=='explicit_atomic_rejection' and data['result'] is None and data['error'].strip()=='mesh snap: no active element found','source rejection relabelled')
            require(data['before_scene']==data['after_scene'] and data['saved_before_sha256']==data['saved_after_sha256'],'rejection changed scene or disk')
        elif outcome=='CANCELLED':
            require(row['comparison_kind']=='explicit_cancellation' and data['result']['snaps'][0]['status']=='cancelled','source cancellation relabelled')
            require(data['before']==data['after'] and not data['result']['snaps'][0]['cursor_changed'],'cancellation changed data')
        else:require(outcome=='FINISHED' and row['comparison_kind']=='defined_numeric_source_comparison' and data['error'] is None,'numeric source comparison missing')
    require(dict(counts)=={'FINISHED':2072,'CANCELLED':136,'ERROR':36},'source outcome classes differ')
    legacy=load(HERE/'legacy-transform-full/report.json')
    require(legacy['passed'] and legacy['required_full_gate_passed'] and legacy['checks']==2406,'retained complete transform gate failed')
    require((legacy['defined_deterministic_source_checks'],legacy['stochastic_support_checks'],legacy['approved_source_rejection_checks'])==(2344,48,14),'approved rotation policy changed')
    require(legacy['binary_sha256']==m['binary_sha256'],'legacy binary differs')
    for row in legacy['runs']:require(row['status']=='passed' and digest(HERE/'legacy-transform-full'/row['file'])==row['sha256'],'retained transform raw result changed')
    retained=load(HERE/'retained/report.json');require(retained['passed'] and retained['verification_inputs_unchanged'],'retained regression suite failed')
    require(all(r['passed'] and r['exit_code']==0 for r in retained['checks']),'retained process failed')
    require({r['name']:r['actual_checks'] for r in retained['checks']}=={'primitive':162,'scale':8,'selection':1060,'creation':262,'payload':57,'normal':42,'rng':96,'mcp':None},'retained scope differs')
    require(load(HERE/'rng-one-shot/report.json')['checks']==48,'one-shot RNG scope differs')
    for name in ['isolation','rng-rotation-isolation','isolation-primitive','isolation-selection','isolation-creation','recipe','source-oracle']:
        report=load(HERE/name/'report.json');require(report['passed'] is True,'native check failed: '+name)
        key='copied_binary_sha256' if name=='isolation-primitive' else 'binary_sha256'
        require(report[key]==m['binary_sha256'],'native binary differs: '+name)
    for name in ['isolation','recipe']:
        report=load(HERE/name/'report.json');require(report['native_terminal_exit']==report['fresh_process_exit']==0,'native wait or fresh process failed')
    require(len(load(HERE/'source-oracle/report.json')['cases'])==6,'six Euler-order queries required')
    for name in ['gpu','gpu-rng-legacy','gpu-mirror-legacy']:
        report=load(HERE/name/'manifest.json');require(report['passed'] and '(Metal,' in report['gpu'] and report['binary_sha256']==m['binary_sha256'],'native Metal check failed')
        require(digest(HERE/name/'after.png')==digest(HERE/name/'reloaded.png'),'fresh Metal image differs')
    performance=load(HERE/'performance/fixed-source-comparison.json');require(performance['passed'] and performance['samples']==30 and performance['forms']==10,'complete snap performance source comparisons missing')
    require(performance['maximum_core_ms']<=250 and performance['maximum_pipeline_ms']<=2000,'fixed snap performance limit failed')
    samples=load(HERE/'performance/fixed-samples/report.json');require(len(samples['runs'])==30 and all(r['passed'] and 0<=r['core_ms']<=250 and 0<=r['operation_save_reload_ms']<=2000 for r in samples['runs']),'a snap timing sample failed')
    oldperf=load(HERE/'legacy-performance/report.json');require(oldperf['passed'] and len(oldperf['runs'])==9 and all(r['passed'] and 0<=r['core_ms']<=250 and 0<=r['operation_save_reload_ms']<=2000 for r in oldperf['runs']),'retained timing sample failed')
    require(load(HERE/'legacy-performance/source-comparison-report.json')['passed'],'retained performance source comparison missing')
    old=load(HERE/'diagnostics/pre-cursor-fix/raw-result-storage.json');require(old['accepted_as_current_candidate'] is False and len(old['raw_results'])==2244,'pre-fix history missing')
    for row in old['raw_results']:require(row['byte_identical'] and digest(local_path(row['shared_path']))==row['sha256'],'shared historical raw bytes changed')
    interrupted=load(HERE/'diagnostics/disk-interruption/raw-result-storage.json');require(interrupted['accepted_as_complete_gate'] is False and len(interrupted['entries'])==2220,'interrupted history differs')
    for row in interrupted['entries']:require(digest(local_path(row['storage_path']))==row['sha256'],'interrupted original bytes changed')
    pilots=load(HERE/'diagnostics/pilot-raw-storage.json');require(pilots['accepted_as_complete_gate'] is False and len(pilots['entries'])==43,'pilot history differs')
    for row in pilots['entries']:require(digest(local_path(row['storage_path']))==row['sha256'],'pilot original bytes changed')
    archive=load(HERE/'performance/samples/archive-storage.json');path=HERE/'performance/samples'/archive['archive'];require(digest(path)==archive['archive_sha256'],'diagnostic archive differs')
    with zipfile.ZipFile(path) as saved:
        require(len(saved.namelist())==30,'diagnostic archive is incomplete')
        for row in archive['files']:require(hashlib.sha256(saved.read(row['name'])).hexdigest()==row['sha256'],'archived original bytes changed')
    rust=(HERE/'local/rust.stdout').read_text();python=(HERE/'local/python.stderr').read_text()
    require(sum(map(int,re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',rust)))==238,'Rust test count differs')
    require(re.search(r'Ran 108 tests in ',python) and re.search(r'\nOK\s*$',python),'Python tests failed or skipped')
    metadata=load(HERE/'local/metadata.json');require(metadata['structurally_valid'] and not metadata['baseline_ready'] and not metadata['problems'],'baseline state differs')
    require((metadata['sources'],metadata['features'],metadata['pending_sources'],metadata['pending_features'])==(9047,38,8994,38),'baseline scope changed')
    require(load(ROOT/'baseline/inventory.json')['complete_products']==[] and all(f['review']=='pending' for f in load(ROOT/'baseline/catalog.json')['features']),'finite work accepted the catalog')
    require(len(load(ROOT/'baseline/lock.json')['artifacts'])==7173,'baseline pin count differs')
    print(json.dumps({'passed':True,'candidate':m['implementation_commit'],'snap_requests':2244,'retained_transform_requests':2406,'rust_tests':238,'python_tests':108,'snap_performance_samples':30,'milestones_accepted':0}))


if __name__=='__main__':main()

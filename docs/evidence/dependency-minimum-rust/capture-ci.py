#!/usr/bin/env python3
"""Retain terminal CI refusal evidence for exact candidate revisions."""
import argparse
import json
from pathlib import Path
import subprocess


def api(path):return json.loads(subprocess.check_output(['gh','api','repos/faberline/formora/'+path],text=True))
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('head');parser.add_argument('output',type=Path);parser.add_argument('runs',nargs='+',type=int)
    args=parser.parse_args();records=[]
    for run_id in args.runs:
        run=api(f'actions/runs/{run_id}');assert run['head_sha']==args.head
        assert run['status']=='completed' and run['conclusion']=='failure'
        jobs=api(f'actions/runs/{run_id}/jobs')['jobs'];assert len(jobs)==3
        items=[]
        for job in jobs:
            assert job['status']=='completed' and job['conclusion']=='failure' and job['steps']==[]
            check=job['check_run_url'].rsplit('/',1)[1]
            annotations=api(f'check-runs/{check}/annotations')
            assert any('recent account payments have failed or your spending limit needs to be increased' in a['message'] for a in annotations)
            items.append({'job':job,'annotations':annotations})
        records.append({'run':run,'jobs':items})
    report={'head':args.head,'runs':records,'required_jobs':3*len(records),'executed_jobs':0,
            'required_ci_status':'unrun','external_blocker':'GitHub account billing/spending limit',
            'rerun_requested':False,'integration_acceptance':'unrun'}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'head':args.head,'required_jobs':report['required_jobs'],'executed_jobs':0,'blocker':report['external_blocker']}))


if __name__=='__main__':main()

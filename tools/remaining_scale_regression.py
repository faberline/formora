#!/usr/bin/env python3
"""Additional negative/zero-axis geometry checks. Full creation contexts remain unrun."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
from primitive_reference_smoke import arguments_for, exercise, GEOMETRY
from compare_mesh_reference import compare
from polygon_reference_smoke import from_query


async def run(binary,output):
    root=Path(__file__).resolve().parents[1];output.mkdir(parents=True,exist_ok=False)
    suite=json.loads((root/'baseline/fixtures/mesh-creation-contexts.json').read_text())
    required={kind+'_'+scale for kind in ['ico_sphere','monkey'] for scale in ['negative_scale','zero_axis_scale']}
    cases=[r for r in suite['runs'] if r['id'] in required];assert len(cases)==4
    records=[]
    with tempfile.TemporaryDirectory(prefix='formora-remaining-scale-') as folder:
        for interface in ['cli','mcp']:
            for case in cases:
                path=root/'baseline/reference/blender-5.2.3/mesh-contexts'/(case['id']+'.json')
                source=json.loads(path.read_text());reference={k:source[k] for k in GEOMETRY}
                request=arguments_for(case,source)
                query,entity=await exercise(binary,Path(folder)/(interface+'-'+case['id']+'.json'),request,interface)
                candidate=from_query(query,entity['entity']['transform'],case['id'])
                file=interface+'-'+case['id']+'.json';(output/file).write_text(json.dumps(candidate,allow_nan=False)+'\n')
                try:result=compare(reference,candidate,suite['comparison']);status='passed';error=None
                except Exception as e:result={};status='failed';error=str(e)
                assert 'creation_attributes_match_reference' not in result
                records.append({'id':case['id'],'interface':interface,'status':status,'error':error,'request':request,
                    'file':file,'candidate_sha256':hashlib.sha256((output/file).read_bytes()).hexdigest(),
                    'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**result})
    passed=all(r['status']=='passed' for r in records)
    report={'passed':passed,'checks':8,'scope':'additional geometry-only scale checks','runs':records,
            'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'full_creation_context_acceptance':'unrun','full_feature_acceptance':'unrun'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':passed,'checks':8,'failures':[(r['id'],r['error']) for r in records if r['status']=='failed']}))
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();asyncio.run(run(args.binary.resolve(),args.output.resolve()))

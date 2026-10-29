#!/usr/bin/env python3
"""Report explicit transform parameter coverage without accepting a full feature."""
import argparse
import hashlib
import json
from pathlib import Path


def report(suite,properties):
    items=[]
    mouse={'mouse_dir_constraint','release_confirm','remove_on_cancel','view2d_edge_pan'}
    other_targets={'gpencil_strokes','texture_space','cursor_transform','translate_origin','use_duplicated_keyframes'}
    for operator,fields in properties.items():
        runs=[r for r in suite['runs'] if r['operator']==operator]
        for name,metadata in fields.items():
            explicit=[r for r in runs if name in r['parameters']]
            values={json.dumps(r['parameters'][name],sort_keys=True):r['parameters'][name] for r in explicit}
            if name=='snap' or name.startswith('snap_') or name.startswith('use_snap_'):
                classification='snapping feature remains required and unrun; false/default calls do not accept snapping'
            elif name=='use_automerge_and_split':classification='topology-changing auto-merge/split remains required and unrun'
            elif name in mouse:classification='legacy mouse/key confirmation controls; only GUI parity is excluded; product outcomes and native preview input remain required'
            elif name in other_targets:classification='other target/data/mode workflow remains required and unrun'
            elif not explicit:classification='no explicit variant coverage; do not infer complete behavior from an omitted parameter'
            else:classification='finite explicit reference inputs; full feature and numeric-domain acceptance remain unrun'
            if name=='proportional_edit_falloff':classification+='; RANDOM checks support and actual normals only, not sequence or distribution'
            enum=metadata.get('enum',[])
            observed=set()
            for value in values.values():
                if isinstance(value,str):observed.add(value)
                elif metadata.get('is_enum_flag') and isinstance(value,list):observed.update(value)
            items.append({'operator':operator,'parameter':name,'explicit_run_ids':[r['id'] for r in explicit],
                          'explicit_values':list(values.values()),'omitted_runs':len(runs)-len(explicit),
                          'observed_rna_enum_items':enum,'rna_enum_items_not_explicitly_exercised':sorted(set(enum)-observed),
                          'classification':classification,'review':'pending'})
    return {'scope':'parameter input coverage; never product acceptance','parameters':items,'parameter_count':len(items),
            'all_operator_parameters_retained':True,'dynamic_enum_note':'An empty RNA enum list is not evidence that no choices exist.',
            'external_context_gaps':['mirror Y/Z axes','all object/data modes and multi-object editing','full parameter domains and capacity'],
            'product_acceptance':'unrun','full_feature_acceptance':'unrun'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('suite',type=Path);parser.add_argument('properties',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    result=report(json.loads(args.suite.read_text()),json.loads(args.properties.read_text()))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    result['inputs_sha256']={'suite':sha(args.suite),'properties':sha(args.properties),'reporter':sha(Path(__file__))}
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'parameter_count':result['parameter_count'],'product_acceptance':'unrun'}))

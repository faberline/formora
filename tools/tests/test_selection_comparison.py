import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
def module(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/filename)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

comparison=module('selection_comparison','compare_selection_reference.py')
builder=module('selection_builder','build_mesh_selection_suite.py')
DATA=ROOT/'baseline/reference/blender-5.2.3/mesh-selection'
SUITE_PATH=ROOT/'baseline/fixtures/mesh-selection.json'
SUITE=comparison.load(SUITE_PATH)
SUITE['_input_sha256']=comparison.digest(SUITE_PATH)


def result(run):
    return comparison.load(DATA/(run['id']+'.json'))


class SelectionComparison(unittest.TestCase):
    def test_fixture_is_reproducible_and_preserves_full_matrix(self):
        authored=copy.deepcopy(SUITE)
        authored.pop('_input_sha256')
        self.assertEqual(builder.build(),authored)
        self.assertEqual(len(authored['runs']),530)
        self.assertEqual(sum(r['expected_status']==['FINISHED'] for r in authored['runs']),480)
        self.assertEqual(sum(r['expected_status']==['CANCELLED'] for r in authored['runs']),30)
        self.assertEqual(sum(r['expected_status']==['POLL_REJECTED'] for r in authored['runs']),20)

    def test_all_captures_validate_with_independent_predicates(self):
        _,records,checks=comparison.capture(DATA,SUITE)
        self.assertEqual(len(records),530)
        self.assertEqual(checks,152)

    def test_same_count_wrong_selected_identity_is_rejected(self):
        run=next(r for r in SUITE['runs'] if r['operator']=='select_non_manifold'
                 and r['initial_mode']==['VERT'] and not r['parameters']['extend']
                 and r['parameters']['use_wire']
                 and sum(v for k,v in r['parameters'].items() if k.startswith('use_'))==1)
        reference=result(run)
        candidate=copy.deepcopy(reference)
        selected=candidate['after']['selected']['VERT']
        original=len(selected)
        selected[0]='v000000'
        selected.sort()
        self.assertEqual(len(selected),original)
        with self.assertRaises(ValueError):
            comparison.compare_run(reference,candidate)

    def test_same_count_geometry_identity_and_positions_are_rejected(self):
        reference=result(SUITE['runs'][0])
        for change in ['position','edge','winding']:
            candidate=copy.deepcopy(reference)
            for side in ['before','after']:
                geometry=candidate[side]['geometry']
                if change=='position':
                    geometry['vertices']['v000000'][0]+=0.125
                elif change=='edge':
                    geometry['edges']['e000000']=['v000000','v000002']
                else:
                    geometry['faces']['f000000'].reverse()
            with self.subTest(change=change),self.assertRaises(ValueError):
                comparison.compare_run(reference,candidate)

    def test_mode_history_and_active_face_are_not_counts(self):
        reference=result(SUITE['runs'][0])
        for change in ['mode','history','active_face']:
            candidate=copy.deepcopy(reference)
            for side in ['before','after']:
                if change=='mode':
                    candidate[side]['mode']=['EDGE']
                elif change=='history':
                    candidate[side]['history'].reverse()
                else:
                    candidate[side]['active_face']='f000000'
            with self.subTest(change=change),self.assertRaises(ValueError):
                comparison.compare_run(reference,candidate)

    def test_uv_material_hidden_and_group_changes_are_rejected(self):
        reference=result(SUITE['runs'][0])
        for change in ['uv','uv_order','material','hidden','weights','seam']:
            candidate=copy.deepcopy(reference)
            for side in ['before','after']:
                state=candidate[side]
                if change=='uv':
                    state['geometry']['uv_layers']['UVMap']['f000000'][0][0]+=1
                elif change=='uv_order':
                    state['geometry']['uv_layer_order'].reverse()
                elif change=='material':
                    state['geometry']['face_materials']['f000000']=1
                elif change=='hidden':
                    state['hidden']['VERT'].pop()
                elif change=='weights':
                    state['groups']['weights']['v000000']['FixtureGroup']=0
                else:
                    state['geometry']['edge_seams']['e000000']=False
            with self.subTest(change=change),self.assertRaises(ValueError):
                comparison.compare_run(reference,candidate)

    def test_unrelated_mutation_fails_even_against_itself(self):
        candidate=result(SUITE['runs'][1])
        candidate['after']['geometry']['vertices']['v000000'][0]+=1
        with self.assertRaises(ValueError):
            comparison.compare_run(candidate,candidate)

    def test_unexpected_outcome_cannot_be_reported_as_success(self):
        reference=result(SUITE['runs'][0])
        candidate=copy.deepcopy(reference)
        candidate['result']['outcome']='completed'
        with self.assertRaises(ValueError):
            comparison.compare_run(reference,candidate)

    def test_unknown_status_with_null_outcome_is_rejected(self):
        candidate=result(SUITE['runs'][0])
        candidate['result']={'status':['UNKNOWN'],'error':None,'outcome':None}
        with self.assertRaises(ValueError):
            comparison.compare_run(candidate,candidate)

    def test_duplicate_json_keys_cannot_replace_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'duplicate.json'
            path.write_text('{"selected":[],"selected":["v000000"]}')
            with self.assertRaises(ValueError):
                comparison.load(path)

    def test_omitted_run_cannot_shrink_reproduction_scope(self):
        manifest=comparison.load(DATA/'manifest.json')
        manifest['runs'].pop()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            (path/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'missing, reordered or duplicate runs'):
                comparison.capture(path,SUITE)

    def test_independent_face_predicate_rejects_self_consistent_fake_capture(self):
        run=next(r for r in SUITE['runs'] if r['operator']=='select_face_by_sides'
                 and r['initial_mode']==['FACE'] and r['parameters']=={'number':4,'type':'EQUAL','extend':False})
        data=result(run)
        data['after']['selected']['FACE'].pop()
        with self.assertRaises(ValueError):
            comparison.oracle(run,data,SUITE['mesh'])

    def test_input_digest_is_bound_to_exact_suite_bytes(self):
        suite=copy.deepcopy(SUITE)
        suite['_input_sha256']='0'*64
        with self.assertRaises(ValueError):
            comparison.capture(DATA,suite)

    def test_claimed_input_digest_cannot_hide_different_initial_data(self):
        run=SUITE['runs'][0]
        data=result(run)
        data['before']['geometry']['vertices']['v000000'][0]+=0.25
        with self.assertRaises(ValueError):
            comparison.bind_initial_state(SUITE['mesh'],run,data['before'])


if __name__=='__main__':
    unittest.main()

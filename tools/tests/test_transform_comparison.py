import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import compare_transform_reference as comparison
from generate_mesh_transform_cases import author

SUITE_PATH=ROOT/'baseline/fixtures/mesh-transform.json'
SUITE=comparison.load(SUITE_PATH)
REFERENCE=ROOT/'baseline/reference/blender-5.2.3/mesh-transform'
REPEAT=ROOT/'baseline/reference/blender-5.2.3/mesh-transform-repeat'


def example(id='transform_0000'):
    run=next(r for r in SUITE['runs'] if r['id']==id)
    return run,comparison.load(REFERENCE/(id+'.json'))


class TransformComparison(unittest.TestCase):
    def test_authored_input_is_reproducible_and_retains_full_matrix(self):
        self.assertEqual(author(),SUITE)
        self.assertEqual(len(SUITE['runs']),1203)
        self.assertEqual(sum(r['repeat_policy']=='stochastic_path_support' for r in SUITE['runs']),24)
        self.assertEqual({r['parameters']['orient_axis'] for r in SUITE['runs'] if 'orient_axis' in r['parameters']},{'X','Y','Z'})
        self.assertEqual({r['parameters']['orient_type'] for r in SUITE['runs']},{'GLOBAL','LOCAL','NORMAL','GIMBAL','VIEW','CURSOR','PARENT'})
        self.assertEqual(len({tuple(r['parameters']['constraint_axis']) for r in SUITE['runs'] if 'constraint_axis' in r['parameters']}),8)

    def test_complete_source_pair_passes_with_actual_independent_checks(self):
        result=comparison.compare(SUITE,REFERENCE,REPEAT,comparison.digest(SUITE_PATH))
        self.assertTrue(result['passed']);self.assertEqual(result['cases'],1203)
        self.assertEqual(result['analytic_checks'],92)
        self.assertEqual(result['stochastic_vertex_path_checks'],960)
        self.assertEqual(result['product_acceptance'],'unrun')
        self.assertEqual(result['random_sequence_or_distribution_acceptance'],'unrun')

    def test_changed_authored_positions_fail_even_when_both_states_agree(self):
        run,data=example()
        for side in ['before','after']:
            data[side]['geometry']['vertices']['v000000'][0]+=0.125
            data[side]['world_vertices']['v000000'][0]+=0.125
        with self.assertRaisesRegex(ValueError,'initial positions'):comparison.validate(run,data,SUITE)

    def test_additional_initial_selection_is_not_accepted_as_seed_inclusion(self):
        run,data=example()
        for side in ['before','after']:data[side]['selected']['VERT']=sorted(data[side]['selected']['VERT']+['v000004'])
        with self.assertRaisesRegex(ValueError,'selection closure'):comparison.validate(run,data,SUITE)

    def test_authored_uv_material_weight_seam_and_winding_mutations_fail(self):
        for name in ['uv','uv_order','material','active_material','weight','seam','winding']:
            run,data=example()
            for side in ['before','after']:
                state=data[side];g=state['geometry']
                if name=='uv':g['uv_layers']['Detail']['f000000'][0][0]+=0.125
                elif name=='uv_order':g['uv_layer_order'].reverse()
                elif name=='material':g['face_materials']['f000000']=1
                elif name=='active_material':state['active_material_index']=0
                elif name=='weight':state['groups']['weights']['v000004']['pin']=0.5
                elif name=='seam':g['edge_seams']['e000000']=not g['edge_seams']['e000000']
                else:g['faces']['f000000'].reverse()
            with self.subTest(name=name),self.assertRaises(ValueError):comparison.validate(run,data,SUITE)

    def test_stale_view_matrix_is_rejected(self):
        run,data=example()
        for side in ['before','after']:data[side]['environment']['view_matrix']=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
        with self.assertRaisesRegex(ValueError,'stale viewport'):comparison.validate(run,data,SUITE)

    def test_world_positions_and_parent_frame_are_bound_to_inputs(self):
        run,data=example()
        for side in ['before','after']:data[side]['world_vertices']['v000000'][0]+=0.125
        with self.assertRaisesRegex(ValueError,'world positions'):comparison.validate(run,data,SUITE)
        run,data=example('transform_0001')
        for side in ['before','after']:data[side]['objects']['parent']['matrix_world'][0][0]+=0.125
        with self.assertRaisesRegex(ValueError,'authored world matrix'):comparison.validate(run,data,SUITE)

    def test_corrupt_basic_and_proportional_results_fail_independent_oracles(self):
        for id,label in [('transform_0000','independent basic'),('transform_0852','independent proportional')]:
            run,data=example(id)
            data['after']['geometry']['vertices']['v000000'][0]+=0.125
            data['after']['world_vertices']['v000000'][0]+=0.125
            with self.subTest(id=id),self.assertRaisesRegex(ValueError,label):comparison.validate(run,data,SUITE)

    def test_random_result_must_stay_on_the_requested_path_and_support(self):
        for axis,amount in [(0,5),(2,0.1)]:
            run,data=example('transform_0908');data['after']['world_vertices']['v000000'][axis]+=amount
            with self.subTest(axis=axis),self.assertRaises(ValueError):comparison.stochastic(run,data)

    def test_random_support_does_not_allow_zero_selected_or_disconnected_influence(self):
        run,data=example('transform_0908')
        data['after']['world_vertices']['v000004']=data['before']['world_vertices']['v000004']
        with self.assertRaisesRegex(ValueError,'full influence'):comparison.stochastic(run,data)
        run,data=example('transform_0912');point=data['before']['world_vertices']['v000009']
        changed=[point[j]+run['parameters']['value'][j]*0.25 for j in range(3)]
        data['after']['world_vertices']['v000009']=changed;data['after']['geometry']['vertices']['v000009']=changed
        with self.assertRaisesRegex(ValueError,'disconnected geometry'):comparison.stochastic(run,data)

    def test_numeric_repeat_comparison_rejects_normal_and_uv_drift(self):
        _,reference=example()
        for field in ['normal','uv']:
            candidate=copy.deepcopy(reference['after'])
            if field=='normal':candidate['normals']['faces']['f000000'][0]+=0.01
            else:candidate['geometry']['uv_layers']['Detail']['f000000'][0][0]+=0.01
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'numeric mismatch'):comparison.tree(reference['after'],candidate)

    def test_unknown_status_error_success_nonfinite_and_extra_fields_fail(self):
        for change in ['status','error','cancelled','nonfinite','extra']:
            run,data=example()
            if change=='status':data['result']['status']=['SKIPPED']
            elif change=='error':data['result']['error']='not a success'
            elif change=='cancelled':data['result']['status']=['CANCELLED']
            elif change=='nonfinite':data['after']['normals']['faces']['f000000'][0]=float('nan')
            else:data['claimed_acceptance']=True
            with self.subTest(change=change),self.assertRaises(ValueError):comparison.validate(run,data,SUITE)

    def test_partial_suite_and_weakened_tolerances_cannot_pass(self):
        for change in ['count','tolerance']:
            suite=copy.deepcopy(SUITE)
            if change=='count':suite['runs'].pop()
            else:suite['comparison']['positions_absolute_tolerance_metres']=1
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'complete authored|tolerances'):
                comparison.compare(suite,REFERENCE,REPEAT,comparison.digest(SUITE_PATH))

    def test_build_process_adapter_suite_and_context_pins_cannot_be_relabelled(self):
        for field,value,message in [('scope','focused','focused capture'),('schema_version',2,'identity'),('build_hash','wrong','build differs'),
            ('binary_sha256','0'*64,'executable pin'),('adapter_sha256','0'*64,'adapter pin'),('base_adapter_sha256','0'*64,'base adapter pin'),
            ('suite_sha256','0'*64,'suite pin'),('background',True,'background context'),('process_id',comparison.load(REPEAT/'manifest.json')['process_id'],'not independent')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as directory:
                ref,repeat=Path(directory)/'ref',Path(directory)/'repeat';ref.mkdir();repeat.mkdir()
                for source,target in [(REFERENCE,ref),(REPEAT,repeat)]:
                    for file in ['manifest.json','operator-properties.json']:shutil.copyfile(source/file,target/file)
                data=comparison.load(ref/'manifest.json');data[field]=value;(ref/'manifest.json').write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,message):comparison.compare(SUITE,ref,repeat,comparison.digest(SUITE_PATH))

    def test_changed_capture_content_without_matching_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ref,repeat=Path(directory)/'ref',Path(directory)/'repeat';ref.mkdir();repeat.mkdir()
            for source,target in [(REFERENCE,ref),(REPEAT,repeat)]:
                for file in ['manifest.json','operator-properties.json','transform_0000.json']:shutil.copyfile(source/file,target/file)
            with (ref/'transform_0000.json').open('a') as stream:stream.write(' ')
            with self.assertRaisesRegex(ValueError,'capture hash'):comparison.compare(SUITE,ref,repeat,comparison.digest(SUITE_PATH))


if __name__=='__main__':unittest.main()

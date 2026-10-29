import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import transform_runtime_smoke as runtime

SUITE=json.loads((ROOT/'baseline/fixtures/mesh-transform.json').read_text())


class TransformRuntimeTests(unittest.TestCase):
    def test_every_authored_request_has_a_mapping_and_setup_has_no_measured_normals(self):
        for run in SUITE['runs']:
            with self.subTest(id=run['id']):
                request=runtime.request_for(run);self.assertEqual(request['expected_revision'],1)
                setup=runtime.setup(SUITE,run);asset=next(c['asset'] for c in setup['commands'] if c['operation']=='set_mesh_asset')
                self.assertEqual(asset['vertices'],{f'v{i:06}':p for i,p in enumerate(SUITE['mesh']['vertices'])})
                for face in asset['polygons'].values():self.assertIsNone(face['normal']);self.assertIsNone(face['corner_normals'])

    def test_source_final_arrays_masks_custom_storage_and_view_rotation_map_without_answers(self):
        run=copy.deepcopy(SUITE['runs'][0])
        for operator in ['translate','resize']:
            run['operator']=operator
            actual=runtime.request_for(run)['commands'][0]['transform']
            self.assertEqual(actual['change']['value'],run['parameters']['value'])
            self.assertEqual(actual['constraint_axis'],[False]*3)
        run['operator']='rotate';run['parameters']['value']=0.61;run['parameters']['constraint_axis']=[False]*3
        self.assertEqual(runtime.request_for(run)['commands'][0]['transform']['change']['radians'],-0.61)
        run['parameters']['constraint_axis']=[True,False,False]
        self.assertEqual(runtime.request_for(run)['commands'][0]['transform']['change']['radians'],0.61)
        run['parameters']['orient_matrix']=[[0.8,-0.6,0],[0.6,0.8,0],[0,0,1]]
        self.assertEqual(runtime.request_for(run)['commands'][0]['transform']['orientation']['matrix'],[[0.8,0.6,0],[-0.6,0.8,0],[0,0,1]])

    def test_unknown_or_snapping_requests_cannot_be_silently_ignored(self):
        for key,value in [('snap',True),('unmapped_required_parameter',1)]:
            run=copy.deepcopy(SUITE['runs'][0]);run['parameters'][key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):runtime.request_for(run)

    def test_source_explicit_center_disables_every_source_pivot_before_native_setup(self):
        for pivot in runtime.PIVOTS:
            run=copy.deepcopy(SUITE['runs'][0]);run['context']['pivot']=pivot
            run['parameters']['center_override']=[0.375,-0.625,0.875]
            actual=runtime.request_for(run)['commands'][0]['transform']
            self.assertEqual(actual['pivot'],'bounds');self.assertEqual(actual['center_override'],[0.375,-0.625,0.875])
            self.assertEqual(actual['change']['value'],run['parameters']['value'])
            run['parameters'].pop('center_override')
            self.assertEqual(runtime.request_for(run)['commands'][0]['transform']['pivot'],runtime.PIVOTS[pivot])

    def test_only_the_specific_empty_selection_error_can_match_source_cancellation(self):
        run=next(r for r in SUITE['runs'] if r['label']=='empty selection')
        source=json.loads((ROOT/'baseline/reference/blender-5.2.3/mesh-transform'/(run['id']+'.json')).read_text())
        before={key:copy.deepcopy(source['before'][key]) for key in runtime.RUNTIME_KEYS}
        args=(run,source,before,copy.deepcopy(before),None)
        self.assertEqual(runtime.compare_output(*args,'mesh transform has no visible selected vertices',runtime.request_for(run)),{'source_outcome':'CANCELLED'})
        for message in ['mesh transform normal orientation is not implemented yet','out of budget','']:
            with self.subTest(message=message),self.assertRaises(AssertionError):runtime.compare_output(*args,message,runtime.request_for(run))
        for key in runtime.RUNTIME_KEYS:
            broken=copy.deepcopy(before);broken.pop(key)
            with self.subTest(missing=key),self.assertRaisesRegex(AssertionError,'incomplete'):
                runtime.compare_output(run,source,broken,copy.deepcopy(broken),None,'mesh transform has no visible selected vertices',runtime.request_for(run))

    def test_pose_and_world_are_derived_from_actual_queried_rotation_state(self):
        pose=runtime.pose({'location':[2,3,4],'rotation':[0,0,1.5707963267948966],'scale':[2,3,4]})
        matrix=runtime.world({'entities':{'object':{'transform':pose,'parent':None}}},'object')
        expected=[[0,-3,0,2],[2,0,0,3],[0,0,4,4],[0,0,0,1]]
        for actual,row in zip(matrix,expected):
            for a,e in zip(actual,row):self.assertLessEqual(abs(a-e),1e-6)

    def test_setup_preserves_authored_source_euler_state_without_recovering_angles(self):
        for run in SUITE['runs']:
            setup=runtime.setup(SUITE,run);profile=SUITE['profiles'][run['context']['profile']]
            target=next(c['entity'] for c in setup['commands'] if c.get('id')=='target')
            self.assertEqual(target['transform']['rotation'],{'kind':'euler','angles':[runtime.f32(v) for v in profile['rotation']],'order':'xyz'})

    def test_world_observer_uses_queried_mode_and_order_and_accepts_legacy_arrays(self):
        t={'translation':[0,0,0],'scale':[1,1,1],'rotation':[0,0,0,1]};scene={'entities':{'object':{'transform':t,'parent':None}}}
        self.assertEqual(runtime.world(scene,'object'),[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        t['rotation']={'kind':'euler','angles':[0.31,-0.47,0.83],'order':'xyz'};xyz=runtime.world(scene,'object')
        t['rotation']['order']='zyx';self.assertNotEqual(runtime.world(scene,'object'),xyz)
        t['rotation']={'kind':'axis_angle','axis':[0,0,5],'radians':1.5707963267948966}
        expected=[[0,-1,0,0],[1,0,0,0],[0,0,1,0],[0,0,0,1]]
        for actual,row in zip(runtime.world(scene,'object'),expected):
            for a,e in zip(actual,row):self.assertLessEqual(abs(a-e),1e-12)


if __name__=='__main__':unittest.main()

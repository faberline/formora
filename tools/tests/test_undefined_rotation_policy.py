import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import transform_runtime_smoke as runtime
from transform_source_policy import ERROR, POLICY, undefined_rotation

SUITE=json.loads((ROOT/'baseline/fixtures/mesh-transform.json').read_text())


class UndefinedRotationPolicyTests(unittest.TestCase):
    def values(self):
        raw=json.loads((ROOT/'docs/evidence/random-falloff/full/cli-transform_0693.json').read_text())
        reference=json.loads((ROOT/'baseline/reference/blender-5.2.3/mesh-transform/transform_0693.json').read_text())
        return [raw['case'],reference,copy.deepcopy(raw['before']),copy.deepcopy(raw['before']),None,ERROR,raw['request']]

    def test_policy_classifies_exactly_the_seven_authored_source_cases(self):
        actual=[run['id'] for run in SUITE['runs'] if undefined_rotation(run)]
        self.assertEqual(actual,['transform_0693','transform_0701','transform_0709','transform_0717',
                                 'transform_0725','transform_0733','transform_0741'])
        for operator in ['translate','resize','rotate']:
            for bits in range(8):
                mask=[bool(bits & (1<<i)) for i in range(3)]
                self.assertEqual(undefined_rotation({'operator':operator,'parameters':{'constraint_axis':mask}}),
                                 operator=='rotate' and bits==7)

    def test_untyped_or_incomplete_masks_cannot_use_the_policy(self):
        for mask in [None,[],[True,True],[True,True,True,True],[1,1,1],'true',{'x':True}]:
            self.assertFalse(undefined_rotation({'operator':'rotate','parameters':{'constraint_axis':mask}}))

    def test_exact_rejection_is_explicitly_distinct_from_a_numeric_source_match(self):
        result=runtime.compare_output(*self.values())
        self.assertEqual(result['comparison_kind'],POLICY)
        self.assertEqual(result['policy_outcome'],'REJECTED')
        self.assertFalse(result['numeric_source_match_claimed'])

    def test_other_errors_and_success_receipts_cannot_pass(self):
        for error in [None,'mesh transform has no visible selected vertices','generic error',ERROR+' ']:
            args=self.values();args[5]=error
            with self.subTest(error=error),self.assertRaises(AssertionError):runtime.compare_output(*args)
        for result in [{},{'transforms':[]},{'transforms':[{'changed':{}}]}]:
            args=self.values();args[4]=result
            with self.subTest(result=result),self.assertRaises(AssertionError):runtime.compare_output(*args)

    def test_modified_scene_or_request_cannot_pass(self):
        args=self.values();args[3]['geometry']['vertices']['v000000'][0]+=0.001
        with self.assertRaises(AssertionError):runtime.compare_output(*args)
        for change in ['mask','untyped_mask','angle','kind']:
            args=self.values();t=args[6]['commands'][0]['transform']
            if change=='mask':t['constraint_axis']=[False]*3
            elif change=='untyped_mask':t['constraint_axis']=[1]*3
            elif change=='angle':t['change']['radians']+=0.1
            else:t['change']={'kind':'translate','value':[0,0,0]}
            with self.subTest(change=change),self.assertRaises(AssertionError):runtime.compare_output(*args)

    def test_policy_error_does_not_waive_a_defined_source_case(self):
        raw=json.loads((ROOT/'docs/evidence/random-falloff/full/cli-transform_0000.json').read_text())
        reference=json.loads((ROOT/'baseline/reference/blender-5.2.3/mesh-transform/transform_0000.json').read_text())
        with self.assertRaises(AssertionError):
            runtime.compare_output(raw['case'],reference,raw['before'],raw['before'],None,ERROR,raw['request'])


if __name__=='__main__':
    unittest.main()

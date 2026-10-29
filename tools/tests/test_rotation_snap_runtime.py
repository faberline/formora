"""Negative controls on actual CLI/MCP artifacts, not prepared source answers."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rotation_snap_runtime import setup, load, digest, compare_state, check_result

ROOT=Path(__file__).resolve().parents[2]
PILOT=ROOT/'docs/evidence/snap-rotation-core/diagnostics/pilot-01'


class RawRotationRuntimeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite=load(ROOT/'baseline/fixtures/snap-rotation.json')
        report=load(PILOT/'report.json');assert report['passed'] and report['checks']==272
        cls.value=None;cls.nonunit=None
        for row in report['runs']:
            if row['interface']!='cli':continue
            path=PILOT/row['file'];assert digest(path)==row['sha256'];v=load(path)
            c=v['case'];q=v['after']['rotation_channels']['target']['quaternion_wxyz']
            if cls.value is None and c['rotations']['objects']['mode']=='QUATERNION' and c['label']=='cross_modes' and c['context']['profile']=='unparented':cls.value=v
            if cls.nonunit is None and c['label']=='locks' and c['rotations']['objects']['mode']=='QUATERNION' and abs(sum(x*x for x in q)-1)>.01:cls.nonunit=v
        assert cls.value and cls.nonunit

    def compare(self,value):
        reference=load(ROOT/'baseline/reference/blender-5.2.3/snap-rotation'/(value['case']['id']+'.json.gz'))
        compare_state(reference['before'],value['before']);compare_state(reference['after'],value['after'])

    def receipt(self,value):
        check_result(value['request'],value['before'],value['after'],value['result'],value['error'],value['before_scene'],value['after_scene'])

    def test_actual_product_artifacts_match_source_and_real_receipts(self):
        for value in [self.value,self.nonunit]:self.compare(value);self.receipt(value)

    def test_wrong_raw_mode(self):
        value=copy.deepcopy(self.value);value['after']['rotation_channels']['target']['mode']='XYZ'
        with self.assertRaises(ValueError):self.compare(value)

    def test_wrong_quaternion_order(self):
        value=copy.deepcopy(self.value);q=value['after']['rotation_channels']['target']['quaternion_wxyz'];q[:]=q[1:]+q[:1]
        with self.assertRaises(ValueError):self.compare(value)

    def test_stored_sign_is_not_folded(self):
        value=copy.deepcopy(self.value);q=value['after']['rotation_channels']['target']['quaternion_wxyz'];q[:]=[-x for x in q]
        with self.assertRaises(ValueError):self.compare(value)

    def test_nonunit_raw_channels_are_not_normalized(self):
        value=copy.deepcopy(self.nonunit);q=value['after']['rotation_channels']['target']['quaternion_wxyz'];n=sum(x*x for x in q)**.5;q[:]=[x/n for x in q]
        with self.assertRaises(ValueError):self.compare(value)

    def test_false_lock_flag(self):
        value=copy.deepcopy(self.value);value['before']['rotation_channels']['target']['lock_rotation_w']=True
        with self.assertRaises(ValueError):self.compare(value)

    def test_stale_physical_matrix(self):
        value=copy.deepcopy(self.value);value['after']['objects']['target']['matrix_world']=value['before']['objects']['target']['matrix_world']
        with self.assertRaises(ValueError):self.compare(value)

    def test_false_changed_object_receipt(self):
        value=copy.deepcopy(self.value);self.assertTrue(value['result']['scene_snaps'][0]['objects']);value['result']['scene_snaps'][0]['objects']=[]
        with self.assertRaises(AssertionError):self.receipt(value)

    def test_false_cursor_orientation_receipt(self):
        value=copy.deepcopy(self.value);value['result']['scene_snaps'][0]['cursor_orientation_before']['mode']='axis_angle'
        with self.assertRaises(AssertionError):self.receipt(value)

    def test_query_matrix_is_checked_instead_of_python_reconstruction(self):
        value=copy.deepcopy(self.value);value['after']['cursor_matrix'][0][0]=42.
        with self.assertRaises(ValueError):self.compare(value)

    def test_authored_setup_never_reads_reference_outputs(self):
        with patch('rotation_snap_runtime.load',side_effect=AssertionError('reference read')):
            request=setup(self.suite,self.value['case'])
        self.assertEqual(request,self.value['setup'])

    def test_all_modes_are_explicit_raw_channels_in_authored_setup(self):
        modes=set()
        for case in self.suite['runs']:
            if case['label']!='cross_modes':continue
            if case['rotations']['objects']['mode'].lower() in modes:continue
            commands=setup(self.suite,case)['commands']
            for command in commands:
                if command['operation']=='create_entity' and command['id']=='target':
                    rotation=command['entity']['transform']['rotation'];self.assertEqual(rotation['kind'],'channels');modes.add(rotation['channels']['mode'])
        self.assertEqual(modes,{'xyz','xzy','yxz','yzx','zxy','zyx','quaternion','axis_angle'})


if __name__=='__main__':unittest.main()

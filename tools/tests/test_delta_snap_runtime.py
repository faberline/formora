"""Protect real delta runtime state and receipts against false acceptance."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from delta_snap_runtime import setup, snapshot, compare_state
from rotation_snap_runtime import load, check_result

ROOT=Path(__file__).resolve().parents[2]


class DeltaRuntimeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite=load(ROOT/'baseline/fixtures/snap-delta.json')
        cls.case=next(r for r in cls.suite['runs'] if r['id']=='delta_snap_0437')
        cls.actual=load(ROOT/'docs/evidence/snap-delta-core/pilot-01/cli-delta_snap_0437.json.gz')
        cls.reference=load(ROOT/'baseline/reference/blender-5.2.3/snap-delta/delta_snap_0437.json.gz')

    def rejected(self, edit):
        actual=copy.deepcopy(self.actual['after']);edit(actual)
        with self.assertRaises((AssertionError,ValueError,KeyError)):
            compare_state(self.reference['after'],actual)

    def test_real_delta_channels_and_frames_pass(self):
        for state in ['before','after']:
            compare_state(self.reference[state],self.actual[state])
        v=self.actual
        check_result(v['request'],v['before'],v['after'],v['result'],v['error'],v['before_scene'],v['after_scene'])

    def test_omitted_delta_translation_fails(self):
        self.rejected(lambda v:v['delta_channels']['target'].update(location=[0.]*3))

    def test_delta_scale_cannot_be_duplicated(self):
        self.rejected(lambda v:v['objects']['target']['matrix_basis'][0].__setitem__(0,99.))

    def test_raw_delta_sign_cannot_be_folded(self):
        def edit(v):
            q=v['delta_channels']['target']['quaternion_wxyz']
            v['delta_channels']['target']['quaternion_wxyz']=[-n for n in q]
        self.rejected(edit)

    def test_raw_delta_quaternion_cannot_be_normalized(self):
        self.rejected(lambda v:v['delta_channels']['target'].update(quaternion_wxyz=[-.5,.5,.5,-.5]))

    def test_inactive_delta_euler_cannot_change(self):
        self.rejected(lambda v:v['delta_channels']['target']['euler'].__setitem__(0,99.))

    def test_delta_world_frame_cannot_be_stale(self):
        self.rejected(lambda v:v['objects']['target']['matrix_world'][0].__setitem__(3,99.))

    def test_saved_scene_supplies_delta_snapshot(self):
        v=self.actual
        state=snapshot(v['scene_inspections']['after'],v['queries']['after'],v['world_queries']['after'])
        self.assertEqual(state,v['after'])
        changed=copy.deepcopy(v['scene_inspections']['after'])
        changed['scene']['entities']['target']['transform']['delta']['euler'][0]=99.
        with self.assertRaises(AssertionError):
            snapshot(changed,v['queries']['after'],v['world_queries']['after'])
        worlds=copy.deepcopy(v['world_queries']['after'])
        worlds['target']['entity']=copy.deepcopy(changed['scene']['entities']['target'])
        state=snapshot(changed,v['queries']['after'],worlds)
        with self.assertRaises((AssertionError,ValueError)):
            compare_state(self.reference['after'],state)

    def test_authored_setup_does_not_read_source_files(self):
        with (patch.object(Path,'read_bytes',side_effect=AssertionError('source read')),
              patch.object(Path,'read_text',side_effect=AssertionError('source read'))):
            self.assertEqual(setup(self.suite,self.case),self.actual['setup'])

    def test_false_delta_receipt_fails(self):
        v=self.actual;result=copy.deepcopy(v['result'])
        result['scene_snaps'][0]['objects'][0]['transform_after']['delta']['translation'][0]=99.
        with self.assertRaises(AssertionError):
            check_result(v['request'],v['before'],v['after'],result,v['error'],v['before_scene'],v['after_scene'])

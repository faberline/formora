"""Negative controls over retained actual runtime output and authored setup."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scene_snap_runtime_smoke import setup, compare_state, check_result

ROOT=Path(__file__).resolve().parents[2]

class SceneSnapComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads((ROOT/'docs/evidence/scene-snap-core/diagnostics/pilot-cli-snap_1086.json').read_text())
        cls.source=json.loads((ROOT/'baseline/reference/blender-5.2.3/snap-menu/snap_1086.json').read_text())
        cls.suite=json.loads((ROOT/'baseline/fixtures/snap-menu.json').read_text())

    def test_retained_actual_before_after_and_receipt_match(self):
        raw=self.raw
        compare_state(self.source['before'],raw['before']);compare_state(self.source['after'],raw['after'])
        self.assertEqual(check_result(self.source,raw['request'],raw['before'],raw['after'],raw['result'],raw['error'],raw['before_scene'],raw['after_scene']),'defined_numeric_source_comparison')

    def test_parent_inverse_or_mode_or_sharing_cannot_be_hidden(self):
        for kind in ['matrix','mode','sharing']:
            actual=copy.deepcopy(self.raw['after'])
            if kind=='matrix':actual['objects']['child']['matrix_parent_inverse'][0][3]=.25
            elif kind=='mode':actual['objects']['secondary']['mode']='EDIT'
            else:actual['sharing']=[['secondary','target']]
            with self.subTest(kind=kind),self.assertRaises(ValueError):compare_state(self.source['after'],actual)

    def test_wrong_geometry_and_nonfinite_normals_fail(self):
        for kind in ['geometry','normal']:
            actual=copy.deepcopy(self.raw['after'])
            if kind=='geometry':actual['meshes']['target']['geometry']['vertices']['v000000'][0]+=.01
            else:actual['meshes']['target']['normals']['faces']['f000000'][0]=float('nan')
            with self.subTest(kind=kind),self.assertRaises(ValueError):compare_state(self.source['after'],actual)

    def test_wrong_lock_and_cursor_are_rejected(self):
        for kind in ['lock','cursor']:
            actual=copy.deepcopy(self.raw['after'])
            if kind=='lock':actual['objects']['target']['lock_location'][0]=True
            else:actual['cursor']['cursor_rotation'][0]+=.1
            with self.subTest(kind=kind),self.assertRaises(ValueError):compare_state(self.source['after'],actual)

    def test_false_transform_receipt_and_missing_object_are_rejected(self):
        for kind in ['transform','missing']:
            result=copy.deepcopy(self.raw['result']);changes=result['scene_snaps'][0]['objects'];self.assertTrue(changes)
            if kind=='transform':changes[0]['transform_after']['translation'][0]+=.25
            else:changes.pop()
            with self.subTest(kind=kind),self.assertRaises(AssertionError):
                check_result(self.source,self.raw['request'],self.raw['before'],self.raw['after'],result,None,self.raw['before_scene'],self.raw['after_scene'])

    def test_double_shared_mesh_receipt_is_rejected(self):
        result=copy.deepcopy(self.raw['result']);item={'mesh_asset':'mesh','shared_instances':['target'],
            'changed':{'vertices':[],'edges':[],'faces':[]}}
        result['scene_snaps'][0]['meshes']=[item,item]
        with self.assertRaisesRegex(AssertionError,'double shared mesh'):
            check_result(self.source,self.raw['request'],self.raw['before'],self.raw['after'],result,None,self.raw['before_scene'],self.raw['after_scene'])

    def test_authored_setup_never_reads_measured_source_results(self):
        run=self.suite['runs'][1400]
        with patch('builtins.open',side_effect=AssertionError('setup read a file')),patch.object(Path,'read_text',side_effect=AssertionError('setup read a file')):
            request=setup(self.suite,run)
        context=request['commands'][-1]['context']
        self.assertEqual(context['edit_objects'],['target'])
        self.assertEqual(set(context['selected']),{'target','secondary'})
        entities={x['id']:x['entity'] for x in request['commands'] if x['operation']=='create_entity'}
        self.assertEqual(entities['target']['content']['geometry']['id'],entities['secondary']['content']['geometry']['id'])

if __name__=='__main__':unittest.main()

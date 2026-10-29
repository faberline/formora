"""Controls for raw representation and provenance acceptance boundaries."""
import copy
import gzip
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compare_snap_rotation_reference import compare, compare_case, rotation_matrix, validate_run, provenance_inputs
from compare_snap_menu_reference import tree
from generate_snap_rotation_cases import author, channels, MODES

ROOT=Path(__file__).resolve().parents[2]
REFERENCE=ROOT/'baseline/reference/blender-5.2.3/snap-rotation'


class RotationReferenceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite=author()
        cls.case=next(r for r in cls.suite['runs'] if r['label']=='locks' and
                     r['rotations']['objects']['mode']=='QUATERNION' and
                     r['context']['profile']=='unparented' and
                     r['context']['lock_rotation']==[True,False,False] and
                     not r['rotations']['lock_rotation_w'] and
                     r['parameters']=={'use_offset':False,'use_rotation':True})
        cls.value=json.loads(gzip.decompress((REFERENCE/(cls.case['id']+'.json.gz')).read_bytes()))

    def rejected(self,edit,both=False):
        a=copy.deepcopy(self.value);b=copy.deepcopy(self.value);edit(b)
        if both:a=copy.deepcopy(b)
        with self.assertRaises((AssertionError,ValueError,KeyError)):
            compare_case(self.suite,self.case,a,b)

    def test_actual_source_and_nonunit_raw_channels(self):
        validate_run(self.suite,self.case,self.value)
        q=self.value['after']['rotation_channels']['target']['quaternion_wxyz']
        self.assertGreater(abs(sum(v*v for v in q)-1),.01)

    def test_wrong_initial_mode_in_both_captures(self):
        self.rejected(lambda v:v['before']['rotation_channels']['target'].update(mode='XYZ'),True)

    def test_wrong_quaternion_order_in_both_captures(self):
        def edit(v):
            q=v['before']['rotation_channels']['target']['quaternion_wxyz'];q[:]=q[1:]+q[:1]
        self.rejected(edit,True)

    def test_equivalent_quaternion_sign_still_differs(self):
        def edit(v):
            q=v['after']['rotation_channels']['target']['quaternion_wxyz'];q[:]=[-n for n in q]
        self.rejected(edit)

    def test_unwanted_raw_normalization(self):
        def edit(v):
            q=v['after']['rotation_channels']['target']['quaternion_wxyz'];n=math.sqrt(sum(x*x for x in q));q[:]=[x/n for x in q]
        self.rejected(edit)

    def test_lock_w_flag(self):
        self.rejected(lambda v:v['before']['rotation_channels']['target'].update(lock_rotation_w=True),True)

    def test_four_dimensional_flag(self):
        self.rejected(lambda v:v['before']['rotation_channels']['target'].update(lock_rotations_4d=False),True)

    def test_wrong_matrix(self):
        self.rejected(lambda v:v['after']['objects']['target']['matrix_world'][0].__setitem__(0,42.))

    def test_source_input_injection(self):
        self.rejected(lambda v:v['run']['parameters'].update(use_rotation=False),True)

    def test_cursor(self):
        self.rejected(lambda v:v['before']['cursor']['location'].__setitem__(0,99.),True)

    def test_vertex(self):
        self.rejected(lambda v:v['before']['meshes']['target']['geometry']['vertices']['v000000'].__setitem__(0,99.),True)

    def test_uv(self):
        def edit(v):
            layers=v['before']['meshes']['target']['geometry']['uv_layers'];next(iter(next(iter(layers.values())).values()))[0][0]=99.
        self.rejected(edit,True)

    def test_sharing(self):
        self.rejected(lambda v:v['before'].update(sharing=[['target'],['secondary']]),True)

    def test_missing_channel(self):
        self.rejected(lambda v:v['after']['rotation_channels']['target'].pop('axis_angle'))

    def test_nonfinite(self):
        self.rejected(lambda v:v['after']['rotation_channels']['target']['euler'].__setitem__(0,float('nan')))

    def test_source_error_cannot_pass(self):
        self.rejected(lambda v:v.update(result={'status':['ERROR'],'error':'failure'}),True)

    def test_same_process_rejected(self):
        manifest=json.loads((REFERENCE/'manifest.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            a,b=Path(temporary)/'a',Path(temporary)/'b';a.mkdir();b.mkdir()
            for folder in [a,b]:(folder/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'same native process'):
                compare(ROOT/'baseline/fixtures/snap-rotation.json',a,b)

    def test_changed_script_hash_rejected(self):
        first=json.loads((REFERENCE/'manifest.json').read_text());second=copy.deepcopy(first);second['process_id']+=1
        second['input_hashes'][str(ROOT/'tools/blender_snap_rotation_reference.py')]='0'*64
        with tempfile.TemporaryDirectory() as temporary:
            a,b=Path(temporary)/'a',Path(temporary)/'b';a.mkdir();b.mkdir()
            for folder,value in [(a,first),(b,second)]:(folder/'manifest.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'capture inputs differ'):
                compare(ROOT/'baseline/fixtures/snap-rotation.json',a,b)

    def test_other_checkout_root_preserves_exact_input_binding(self):
        manifest=json.loads((REFERENCE/'manifest.json').read_text())
        prefix=str(ROOT)+'/'
        self.assertTrue(all(name.startswith(prefix) for name in manifest['input_hashes']))
        manifest['input_hashes']={'/different/checkout/'+name[len(prefix):]:sha for name,sha in manifest['input_hashes'].items()}
        provenance_inputs(REFERENCE,manifest,ROOT/'baseline/fixtures/snap-rotation.json')

    def test_same_bad_script_hash_in_both_captures_rejected(self):
        manifest=json.loads((REFERENCE/'manifest.json').read_text())
        manifest['input_hashes'][str(ROOT/'tools/blender_snap_rotation_reference.py')]='0'*64
        with self.assertRaisesRegex(ValueError,'capture provenance changed'):
            provenance_inputs(REFERENCE,manifest,ROOT/'baseline/fixtures/snap-rotation.json')

    def test_zero_rotation_has_identity_pose_for_every_mode(self):
        for mode in MODES:tree([[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],rotation_matrix(channels(mode,'zero')))

    def test_analytic_z_quarter_turn(self):
        expected=[[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]]
        for mode in ['XYZ','QUATERNION','AXIS_ANGLE']:
            data={'mode':mode,'euler':[0.,0.,math.pi/2],
                  'quaternion_wxyz':[math.sqrt(.5),0.,0.,math.sqrt(.5)],'axis_angle':[math.pi/2,0.,0.,2.]}
            tree(expected,rotation_matrix(data))


if __name__=='__main__':unittest.main()

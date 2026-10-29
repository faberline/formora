import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import compare_snap_menu_reference as check

SUITE_PATH=ROOT/'baseline/fixtures/snap-menu.json'
SUITE=check.load(SUITE_PATH)
REFERENCE=ROOT/'baseline/reference/blender-5.2.3/snap-menu'
REPEAT=ROOT/'baseline/reference/blender-5.2.3/snap-menu-repeat'


def example(id='snap_0000'):
    run=next(r for r in SUITE['runs'] if r['id']==id)
    return run,check.load(REFERENCE/(id+'.json'))


class SnapMenuComparison(unittest.TestCase):
    def test_complete_authored_fixture_is_reproducible(self):
        self.assertEqual(SUITE,check.author())
        self.assertEqual(len(SUITE['runs']),1672)
        self.assertEqual(set(SUITE['operators']),set(check.OPERATORS))
        self.assertEqual({tuple(sorted(r['parameters'].items())) for r in SUITE['runs'] if r['operator']=='snap_selected_to_cursor' and len(r['parameters'])==2},
            {(('use_offset',a),('use_rotation',b)) for a in [False,True] for b in [False,True]})

    def test_complete_independent_source_pair(self):
        result=check.compare(SUITE_PATH,REFERENCE,REPEAT)
        self.assertEqual((result['cases'],result['captures'],result['analytic_checks']),(1672,3344,358))
        self.assertNotEqual(*result['process_ids']);self.assertEqual(result['product_acceptance'],'unrun')

    def test_negative_half_rounding_and_f32_adjacent_boundary(self):
        self.assertEqual(check.snapped([-.5,-1.5,-2.5],1.),[0.,-1.,-2.])
        self.assertEqual(check.snapped([.4999999701976776,.5000000596046448,-.5000000596046448],1.),[1.,1.,-1.])
        self.assertEqual(check.grid_step({'unit_system':'NONE','grid_spacing':2.,'unit_scale_length':.25}),2.)
        self.assertEqual(check.grid_step({'unit_system':'IMPERIAL','grid_spacing':2.,'unit_scale_length':.25}),check.f32(check.f32(.3048)*8))

    def test_input_corruptions_fail_even_when_both_states_agree(self):
        for kind in ['vertex','uv','weight','winding','material','selection','hidden','history','cursor','frame','parent_inverse','local_matrix','sharing','settings','flags']:
            run,data=example()
            for phase in ['before','after']:
                s=data[phase];m=s['meshes']['target'];g=m['geometry'];o=s['objects']['target']
                if kind=='vertex':
                    for points in [g['vertices'],m['world_vertices'],m['vertices_metres'],m['world_vertices_metres']]:points['v000003'][0]+=.125
                elif kind=='uv':g['uv_layers']['Detail']['f000000'][0][0]+=.125
                elif kind=='weight':m['groups']['weights']['v000004']['pin']=.5
                elif kind=='winding':g['faces']['f000000'].reverse()
                elif kind=='material':g['face_materials']['f000000']=1
                elif kind=='selection':m['selected']['VERT']=sorted(m['selected']['VERT']+['v000004'])
                elif kind=='hidden':m['hidden']['FACE']=[]
                elif kind=='history':m['history']=[]
                elif kind=='cursor':s['cursor']['rotation'][0]+=.125
                elif kind=='frame':o['location'][0]+=.125
                elif kind=='parent_inverse':o['matrix_parent_inverse'][0][3]+=.125
                elif kind=='local_matrix':o['matrix_local'][0][3]+=.125
                elif kind=='sharing':s['sharing']=[]
                elif kind=='settings':s['settings']['grid_spacing']=.5
                else:m['flags']['mirror_x']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):check.validate(SUITE,run,data)

    def test_repeat_corruptions_fail_for_geometry_uv_normal_cursor_and_frame(self):
        _,data=example()
        for kind in ['vertex','uv','normal','cursor','frame','selection','sharing']:
            candidate=copy.deepcopy(data['after']);m=candidate['meshes']['target']
            if kind=='vertex':m['vertices_metres']['v000003'][0]+=.01
            elif kind=='uv':m['geometry']['uv_layers']['Detail']['f000000'][0][0]+=.01
            elif kind=='normal':m['normals']['faces']['f000000'][0]+=.01
            elif kind=='cursor':candidate['cursor']['rotation'][0]+=.01
            elif kind=='frame':candidate['objects']['target']['matrix_basis'][0][0]+=.01
            elif kind=='selection':m['selected']['VERT']=[]
            else:candidate['sharing']=[]
            with self.subTest(kind=kind),self.assertRaises(ValueError):check.compare_states(data['after'],candidate)

    def test_unknown_status_parameters_nonfinite_and_missing_fields_fail(self):
        for kind in ['status','error','parameter','nan','missing','extra']:
            run,data=example()
            if kind=='status':data['result']['status']=['SKIPPED']
            elif kind=='error':data['result']['error']='false success'
            elif kind=='parameter':data['run']['parameters']['use_rotation']=True
            elif kind=='nan':data['after']['meshes']['target']['normals']['faces']['f000000'][0]=float('nan')
            elif kind=='missing':del data['after']['objects']['target']['delta_scale']
            else:data['after']['claimed_acceptance']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):check.validate(SUITE,run,data)

    def test_linked_edit_users_read_one_live_mesh_and_bind_real_sharing(self):
        run,data=example('snap_1343');check.validate(SUITE,run,data)
        for phase in ['before','after']:
            s=data[phase]
            self.assertEqual(s['sharing'],[['secondary','target']])
            self.assertEqual(s['meshes']['secondary']['geometry'],s['meshes']['target']['geometry'])
            self.assertTrue(s['meshes']['secondary']['data_edit_mode'])
        data['after']['meshes']['secondary']['geometry']['vertices']['v000000'][0]+=.01
        with self.assertRaises(ValueError):check.validate(SUITE,run,data)

    def test_source_singular_parent_local_matrix_is_explicit_zero(self):
        run,data=example('snap_1297');check.validate(SUITE,run,data)
        self.assertEqual(data['before']['objects']['child']['matrix_local'],[[0.]*4 for _ in range(4)])
        data['before']['objects']['child']['matrix_local'][0][0]=1.
        with self.assertRaisesRegex(ValueError,'authored local matrix'):check.validate(SUITE,run,data)

    def test_capture_provenance_cannot_be_relabelled(self):
        for kind in ['hash','binary','scope','process','background','count','metadata']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temporary:
                folder=Path(temporary)
                for name in ['manifest.json','operator-properties.json']:shutil.copyfile(REFERENCE/name,folder/name)
                m=check.load(folder/'manifest.json')
                if kind=='hash':m['input_hashes'][next(iter(m['input_hashes']))]='0'*64
                elif kind=='binary':m['binary_sha256']='0'*64
                elif kind=='scope':m['scope']='focused_diagnostic'
                elif kind=='process':m['process_id']=0
                elif kind=='background':m['background']=True
                elif kind=='count':m['runs'].pop()
                else:m['operator_properties_sha256']='0'*64
                (folder/'manifest.json').write_text(json.dumps(m))
                with self.assertRaises(ValueError):check.provenance(folder,SUITE,SUITE_PATH)

    def test_discrete_values_and_tolerances_stay_fixed(self):
        with self.assertRaises(ValueError):check.tree({'index':1},{'index':2})
        with self.assertRaises(ValueError):check.tree({'selected':True},{'selected':1})
        with self.assertRaises(ValueError):check.tree([0.],[1.000001e-6])
        with self.assertRaises(ValueError):check.tree([float('inf')],[float('inf')])


if __name__=='__main__':unittest.main()

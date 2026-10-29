from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import snap_runtime_smoke as runtime

SUITE=runtime.load(ROOT/'baseline/fixtures/snap-menu.json')
SOURCE=ROOT/'baseline/reference/blender-5.2.3/snap-menu'
PILOT=ROOT/'docs/evidence/mesh-snap-core/diagnostics/pilot-cli-snap_0000.json'


def compare(data):
    run=data['case'];reference=runtime.load(SOURCE/(run['id']+'.json'))
    return runtime.compare_output(run,reference,data['before'],data['after'],data['result'],data['error'],
        data['request'],data['before_scene'],data['after_scene'])


class SnapRuntime(unittest.TestCase):
    def test_all_single_edit_cases_are_required_and_550_other_cases_stay_required(self):
        covered=[r for r in SUITE['runs'] if runtime.covered(r)]
        self.assertEqual(len(covered),1122);self.assertEqual(len(SUITE['runs'])-len(covered),550)
        self.assertEqual({r['operator'] for r in covered},set(SUITE['operators']))

    def test_setup_and_request_use_authored_inputs_without_loading_answers(self):
        for run in [SUITE['runs'][0],SUITE['runs'][840],SUITE['runs'][1654]]:
            with patch.object(runtime,'load',side_effect=AssertionError('reference input leakage')):
                setup=runtime.setup(SUITE,run);request=runtime.request_for(run)
            self.assertEqual(setup['expected_revision'],0)
            self.assertEqual(request['expected_revision'],1)
            self.assertNotIn('answer',str(request));self.assertEqual(request['commands'][0]['operation'],'snap_mesh')

    def test_hidden_only_seed_is_mapped_to_actual_source_flush_before_validation(self):
        run=SUITE['runs'][150];self.assertTrue(run['context']['hide_all'])
        editing=next(c['editing'] for c in runtime.setup(SUITE,run)['commands'] if c['operation']=='set_mesh_editing')
        self.assertEqual(editing['selected'],{'vertices':[],'edges':[],'faces':[]});self.assertEqual(editing['history'],[])
        self.assertEqual(len(editing['hidden']['vertices']),27)
        self.assertEqual(SUITE['runs'][150]['seed']['indices'],[0,2])

    def test_physical_grid_and_cursor_conversion_come_from_authored_units(self):
        for run in SUITE['runs']:
            if not runtime.covered(run) or run['operator']!='snap_selected_to_grid':continue
            c=run['context'];base=runtime.f32(.3048) if c['unit_system']=='IMPERIAL' else 1.
            expected=runtime.f32(base*c['grid_spacing'])
            self.assertEqual(runtime.request_for(run)['commands'][0]['snap']['action']['spacing'],expected)

    def test_retained_real_pilot_receipt_passes(self):
        result=compare(runtime.load(PILOT));self.assertEqual(result['comparison_kind'],'defined_numeric_source_comparison')

    def test_false_receipt_identity_changed_components_and_cursor_are_rejected(self):
        for kind in ['index','entity','asset','sharing','vertices','edges','faces','cursor','rotation','status']:
            data=runtime.load(PILOT);receipt=data['result']['snaps'][0]
            if kind=='index':receipt['command_index']=1
            elif kind=='entity':receipt['entity']='other'
            elif kind=='asset':receipt['mesh_asset']='other'
            elif kind=='sharing':receipt['shared_instances']=['other','target']
            elif kind in ['vertices','edges','faces']:receipt['changed'][kind]=[] if receipt['changed'][kind] else ['false']
            elif kind=='cursor':receipt['cursor_before'][0]+=.125
            elif kind=='rotation':receipt['rotation_applied']=True
            else:receipt['status']='cancelled'
            with self.subTest(kind=kind),self.assertRaises(AssertionError):compare(data)

    def test_altered_geometry_normals_uvs_and_cursor_fail_numeric_source_comparison(self):
        for kind in ['vertex','normal','uv','cursor']:
            data=runtime.load(PILOT)
            if kind=='vertex':data['after']['geometry']['vertices']['v000000'][0]+=.125
            elif kind=='normal':data['after']['normals']['faces']['f000000'][0]+=.125
            elif kind=='uv':data['after']['geometry']['uv_layers']['Detail']['f000000'][0][0]+=.125
            else:data['after_scene']['authoring_context']['cursor_rotation'][0]+=.125
            with self.subTest(kind=kind),self.assertRaises(ValueError):compare(data)

    def test_errors_and_cancelled_outcomes_cannot_be_relabelled_as_finished(self):
        data=runtime.load(PILOT);data['error']='pretend rejection';data['result']=None
        with self.assertRaises(AssertionError):compare(data)
        data=runtime.load(PILOT);data['result']['snaps'][0]['status']='cancelled'
        with self.assertRaises(AssertionError):compare(data)


if __name__=='__main__':unittest.main()

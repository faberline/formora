import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from generate_mesh_normal_cases import author
from normal_runtime_smoke import asset_from_case, compare, load_reference


class NormalComparisonTests(unittest.TestCase):
    def setUp(self):
        self.suite=json.loads((ROOT/'baseline/fixtures/mesh-normals.json').read_text())
        self.references=load_reference(ROOT,self.suite)
        self.case=self.suite['cases'][0]
        self.reference=self.references[self.case['id']]
        asset=asset_from_case(self.case);asset.pop('smooth_triangles')
        self.query={'mesh_asset':asset,'normals':{'faces':[{'face':{'kind':self.case['kinds'][i],'id':f'f{i:06}'},**copy.deepcopy(normal)} for i,normal in enumerate(self.reference['normals'])]}}

    def test_authored_fixture_is_reproducible_and_runtime_inputs_have_no_measured_normals(self):
        self.assertEqual(author(),self.suite)
        for case in self.suite['cases']:
            asset=asset_from_case(case)
            for face in [*asset['polygons'].values(),*asset['triangles'].values()]:
                self.assertIsNone(face['corner_normals'])
                self.assertIsNone(face.get('normal'))
            self.assertEqual(asset['vertices'],{f'v{i:06}':p for i,p in enumerate(case['vertices'])})

    def test_exact_source_normals_pass_and_all_components_are_counted(self):
        result=compare(self.case,self.reference,self.query)
        self.assertEqual(result,{'components':30,'maximum_absolute_error':0})

    def test_matching_normals_cannot_hide_changed_geometry_or_attributes(self):
        for mutation in ['position','edge','face','smooth','payload']:
            query=copy.deepcopy(self.query);asset=query['mesh_asset']
            if mutation=='position':asset['vertices']['v000000'][0]+=0.25
            elif mutation=='edge':asset['edges']['e000000'].reverse()
            elif mutation=='face':asset['polygons']['f000000']['vertices'].reverse()
            elif mutation=='smooth':asset['polygons']['f000000']['smooth']=False
            else:asset['polygons']['f000000']['normal']=[0,0,1]
            with self.subTest(mutation=mutation),self.assertRaisesRegex(AssertionError,'authored geometry'):
                compare(self.case,self.reference,query)

    def test_wrong_normal_nonfinite_missing_extra_and_wrong_identity_fail(self):
        for mutation in ['normal','corner','nonfinite','missing','extra','identity','duplicate','corner_count']:
            query=copy.deepcopy(self.query);faces=query['normals']['faces']
            if mutation=='normal':faces[0]['normal'][0]+=2e-6
            elif mutation=='corner':faces[0]['corner_normals'][0][0]+=2e-6
            elif mutation=='nonfinite':faces[0]['normal'][0]=float('nan')
            elif mutation=='missing':faces.pop()
            elif mutation=='extra':faces.append(copy.deepcopy(faces[0]))
            elif mutation=='identity':faces[0]['face']['kind']='triangle'
            elif mutation=='duplicate':faces[1]['face']=copy.deepcopy(faces[0]['face'])
            elif mutation=='corner_count':faces[0]['corner_normals'].pop()
            with self.subTest(mutation=mutation),self.assertRaises((AssertionError,KeyError)):
                compare(self.case,self.reference,query)

    def test_source_hash_input_binding_count_and_completion_fail_closed(self):
        for mutation in ['hash','input','count','duplicate','complete','adapter','binary']:
            with tempfile.TemporaryDirectory(prefix='formora-normal-reference-test-') as directory:
                root=Path(directory)
                folder=root/'baseline/reference/blender-5.2.3/mesh-normals'
                shutil.copytree(ROOT/'baseline/reference/blender-5.2.3/mesh-normals',folder)
                for name in ['baseline/fixtures/mesh-normals.json','tools/blender_normal_reference.py']:
                    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
                manifest=json.loads((folder/'manifest.json').read_text())
                suite=copy.deepcopy(self.suite)
                if mutation=='hash':manifest['records'][0]['sha256']='0'*64
                elif mutation=='input':suite['cases'][0]['vertices'][0][0]+=0.5
                elif mutation=='count':manifest['cases']-=1
                elif mutation=='duplicate':manifest['records'][1]=copy.deepcopy(manifest['records'][0])
                elif mutation=='complete':manifest['complete']=False
                elif mutation=='adapter':manifest['adapter_sha256']='0'*64
                elif mutation=='binary':manifest['binary_sha256']='0'*64
                (folder/'manifest.json').write_text(json.dumps(manifest))
                with self.subTest(mutation=mutation),self.assertRaises(AssertionError):
                    load_reference(root,suite)


if __name__=='__main__':unittest.main()

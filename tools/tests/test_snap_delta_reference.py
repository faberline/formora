"""Analytic controls for nonidentity delta source preparation."""
from collections import Counter
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_snap_delta_reference import delta_matrix
from compare_snap_menu_reference import tree
from generate_snap_delta_cases import author, delta
from generate_snap_rotation_cases import channels


class DeltaPreparationControls(unittest.TestCase):
    def test_authored_family_and_identity(self):
        suite = author()
        self.assertEqual(len(suite['runs']), 1792)
        self.assertEqual(Counter(r['label'] for r in suite['runs']), suite['groups_expected'])
        self.assertEqual(len({r['id'] for r in suite['runs']}), 1792)

    def test_identity_delta_preserves_zero_pose(self):
        expected = [[2.,0.,0.,1.], [0.,3.,0.,2.], [0.,0.,4.,3.], [0.,0.,0.,1.]]
        for mode in ['XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX', 'QUATERNION', 'AXIS_ANGLE']:
            tree(expected, delta_matrix({'location':[1.,2.,3.], 'scale':[2.,3.,4.]},
                 channels(mode, 'zero'), delta('identity')))

    def test_delta_translation_and_scale(self):
        d = delta('identity'); d.update(location=[.25,-.5,1.], scale=[-2.,.5,3.])
        expected = [[-4.,0.,0.,1.25], [0.,1.5,0.,1.5], [0.,0.,12.,4.], [0.,0.,0.,1.]]
        tree(expected, delta_matrix({'location':[1.,2.,3.], 'scale':[2.,3.,4.]}, channels('XYZ','zero'), d))

    def test_noncommuting_delta_precedes_normal_rotation(self):
        normal = channels('XYZ', 'zero'); normal['euler'] = [math.pi/2,0.,0.]
        d = delta('identity'); d['euler'] = [0.,0.,math.pi/2]
        result = delta_matrix({'location':[0.]*3, 'scale':[1.]*3}, normal, d)
        # Delta Z after normal X maps +Y to +Z; reversing the order maps it to -X.
        tree([0.,0.,1.], [result[i][1] for i in range(3)])
        tree([0.,1.,0.], [result[i][0] for i in range(3)])

    def test_nonunit_delta_quaternion_evaluates_copy(self):
        d = delta('rotation'); original = copy.deepcopy(d)
        unit = copy.deepcopy(d); unit['quaternion_wxyz'] = [v/2 for v in d['quaternion_wxyz']]
        p = {'location':[0.]*3, 'scale':[1.]*3}; normal = channels('QUATERNION')
        tree(delta_matrix(p,normal,unit), delta_matrix(p,normal,d), tolerance=0.)
        self.assertEqual(d, original)

    def test_axis_angle_ignores_inactive_exposed_delta_rotations(self):
        p = {'location':[0.]*3, 'scale':[1.]*3}; normal = channels('AXIS_ANGLE')
        tree(delta_matrix(p,normal,delta('identity')), delta_matrix(p,normal,delta('rotation')), tolerance=0.)


if __name__ == '__main__':
    unittest.main()

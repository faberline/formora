"""Before-code negative controls for the separate local-query channel."""
import copy
import unittest
from singular_snap_runtime import compare_local


def identity():
    return [[float(i == j) for j in range(4)] for i in range(4)]


def unavailable():
    return [[{'__source_nonfinite_diagnostic__': {
        'path': f'/after/objects/child/matrix_local/{i}/{j}', 'repr': 'nan',
        'f32_little_endian_hex': '0000c07f', 'f64_little_endian_hex': '000000000000f87f'}}
        for j in range(4)] for i in range(4)]


class LocalQueryControls(unittest.TestCase):
    def test_finite_and_explicit_error_channels(self):
        self.assertEqual(compare_local(identity(), identity()), 'available_numeric')
        self.assertEqual(compare_local(unavailable(), None, 'cannot_invert'), 'unavailable_query')

    def test_false_unavailable_on_finite_or_zero_is_rejected(self):
        for expected in [identity(), [[0.] * 4 for _ in range(4)]]:
            with self.assertRaises(AssertionError):
                compare_local(expected, None, 'cannot_invert')

    def test_zero_and_identity_numeric_replacements_are_rejected(self):
        for actual in [identity(), [[0.] * 4 for _ in range(4)]]:
            with self.assertRaises(AssertionError):
                compare_local(unavailable(), actual, 'cannot_invert')

    def test_missing_or_wrong_error_is_rejected(self):
        for error in [None, 'unavailable', '', False]:
            with self.assertRaises(AssertionError):
                compare_local(unavailable(), None, error)

    def test_boolean_or_wrong_numeric_value_is_rejected(self):
        for value in [True, 2.]:
            actual = identity()
            actual[0][0] = value
            with self.assertRaises((AssertionError, ValueError)):
                compare_local(identity(), actual)

    def test_source_tag_drift_is_rejected(self):
        for field in ['repr', 'f32_little_endian_hex', 'f64_little_endian_hex']:
            expected = unavailable()
            expected[0][0]['__source_nonfinite_diagnostic__'][field] = 'different'
            with self.assertRaises(AssertionError):
                compare_local(expected, None, 'cannot_invert')

    def test_comparison_does_not_mutate_source_or_response(self):
        expected = unavailable()
        before = copy.deepcopy(expected)
        compare_local(expected, None, 'cannot_invert')
        self.assertEqual(expected, before)

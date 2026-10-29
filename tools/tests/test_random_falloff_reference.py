import struct
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from random_falloff_reference import STAT_DRAWS, statistics


class RandomReferenceTests(unittest.TestCase):
    def test_complete_source_distribution_passes_the_frozen_limits(self):
        raw = (ROOT / 'baseline/reference/blender-5.2.3/random-falloff/first-distribution.bin').read_bytes()
        report = statistics(raw)
        self.assertTrue(report['passed'])
        self.assertEqual(sum(report['histogram']), STAT_DRAWS)

    def test_truncated_raw_samples_are_rejected(self):
        with self.assertRaises(ValueError):
            statistics(b'\0' * (STAT_DRAWS * 4 - 1))

    def test_non_finite_and_out_of_range_samples_are_rejected(self):
        for value in [float('nan'), float('inf'), -0.01, 1.01]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                statistics(struct.pack('<f', value) * STAT_DRAWS)

    def test_constant_and_alternating_distributions_cannot_pass(self):
        for raw in [struct.pack('<f', 0.5) * STAT_DRAWS,
                    struct.pack('<ff', 0.0, 1.0) * (STAT_DRAWS // 2)]:
            self.assertFalse(statistics(raw)['passed'])


if __name__ == '__main__':
    unittest.main()

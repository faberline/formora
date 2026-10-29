#!/usr/bin/env python3
"""Capture exact seeded RNG output from the unchanged frozen Blender header."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SEEDS = [0, 1, 2, 42, 65535, 65536, 1234567, 2147483647, 2147483648, 4294967295]
DRAWS = 4096
STAT_DRAWS = 1048576
DRIVER = r'''#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstring>
#define BLI_assert assert
#include "BLI_rand.hh"
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *out = std::fopen(argv[1], "wb");
  if (!out) return 3;
  const uint32_t seeds[] = {0,1,2,42,65535,65536,1234567,2147483647,2147483648,4294967295};
  for (uint32_t seed : seeds) {
    blender::RandomNumberGenerator rng(seed);
    for (int i=0; i<4096; ++i) {
      const float value = rng.get_float();
      uint32_t bits;
      std::memcpy(&bits, &value, sizeof(bits));
      for (int b=0; b<4; ++b) if (std::fputc((bits >> (b*8)) & 255, out) == EOF) return 4;
    }
  }
  if (std::fclose(out)) return 5;
  blender::RandomNumberGenerator rng(42);
  for (int i=0; i<1048576; ++i) {
    const float value = rng.get_float();
    uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    for (int b=0; b<4; ++b) if (std::putchar((bits >> (b*8)) & 255) == EOF) return 6;
  }
  return std::ferror(stdout) ? 7 : 0;
}
'''
STUBS = {
    'BLI_math_vector_types.hh': '#pragma once\nnamespace blender { struct float2 {}; struct float3 { float3(float,float,float) {} }; }\n',
    'BLI_span.hh': '#pragma once\nnamespace blender { template<typename T> class MutableSpan; }\n',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def statistics(raw):
    if len(raw) != STAT_DRAWS * 4:
        raise ValueError('wrong raw statistical sample length')
    values = [row[0] for row in struct.iter_unpack('<f', raw)]
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in values):
        raise ValueError('non-finite or out-of-range draw')
    mean = math.fsum(values) / len(values)
    variance = math.fsum((v - mean) ** 2 for v in values) / len(values)
    covariance = math.fsum((a - mean) * (b - mean) for a, b in zip(values, values[1:])) / (len(values)-1)
    correlation = covariance / variance if variance else float('inf')
    histogram = [0] * 256
    for v in values:
        histogram[min(255, int(v * 256))] += 1
    expected = len(values) / 256
    passed = (abs(mean - 0.5) <= 0.002 and abs(variance - 1/12) <= 0.001
              and abs(correlation) < 0.01
              and all(abs(n - expected) / expected <= 0.12 for n in histogram))
    return {'draws': len(values), 'mean': mean, 'variance': variance,
            'lag_one_correlation': correlation, 'histogram': histogram,
            'minimum': min(values), 'maximum': max(values), 'passed': passed}


def capture(output):
    output = output.resolve()
    if output.exists():
        raise ValueError('refuse existing output directory')
    source = ROOT / 'baseline/sources/random-falloff'
    manifest = json.loads((source / 'manifest.json').read_text())
    assert manifest['commit'] == 'e13b728c6880d3084d9d57c30031ed5df8b39dee'
    inputs = {str((source / row['file']).relative_to(ROOT)): row['sha256']
              for row in manifest['source_files']}
    inputs[str((source / 'manifest.json').relative_to(ROOT))] = digest(source / 'manifest.json')
    inputs[str(Path(__file__).relative_to(ROOT))] = digest(__file__)
    inputs['docs/contracts/random-falloff-sequence.md'] = digest(ROOT / 'docs/contracts/random-falloff-sequence.md')
    assert all(digest(ROOT / p) == sha for p, sha in inputs.items())
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='formora-rng-reference-', dir=output.parent) as tmp:
        work = Path(tmp)
        shutil.copyfile(source / 'BLI_rand.hh', work / 'BLI_rand.hh')
        for name, text in STUBS.items():
            (work / name).write_text(text)
        (work / 'driver.cc').write_text(DRIVER)
        command = ['xcrun', 'clang++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-I', str(work), str(work / 'driver.cc'), '-o', str(work / 'oracle')]
        compile_result = subprocess.run(command, capture_output=True)
        (work / 'compile.stdout').write_bytes(compile_result.stdout)
        (work / 'compile.stderr').write_bytes(compile_result.stderr)
        compile_result.check_returncode()
        processes = []
        for label in ['first', 'repeat']:
            child = subprocess.Popen([str(work / 'oracle'), str(work / (label + '-sequence.bin'))],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            raw, err = child.communicate(timeout=60)
            (work / (label + '-distribution.bin')).write_bytes(raw)
            (work / (label + '.stderr')).write_bytes(err)
            assert child.returncode == 0
            processes.append({'pid': child.pid, 'returncode': child.returncode})
            assert (work / (label + '-sequence.bin')).stat().st_size == len(SEEDS) * DRAWS * 4
        assert processes[0]['pid'] != processes[1]['pid']
        assert (work / 'first-sequence.bin').read_bytes() == (work / 'repeat-sequence.bin').read_bytes()
        assert (work / 'first-distribution.bin').read_bytes() == (work / 'repeat-distribution.bin').read_bytes()
        stats = statistics((work / 'first-distribution.bin').read_bytes())
        assert stats['passed'], stats
        assert all(digest(ROOT / p) == sha for p, sha in inputs.items()), 'input changed during capture'
        compiler = subprocess.run(['xcrun', 'clang++', '--version'], capture_output=True, check=True)
        (work / 'compiler.txt').write_bytes(compiler.stdout + compiler.stderr)
        (work / 'capture-driver.py').write_bytes(Path(__file__).read_bytes())
        report = {'source_commit': manifest['commit'], 'input_hashes': inputs,
                  'seeds': SEEDS, 'draws_per_seed': DRAWS, 'processes': processes,
                  'compile_command': command, 'statistics': stats, 'passed': True,
                  'operator_sequence_acceptance': False,
                  'artifacts': {p.name: digest(p) for p in sorted(work.iterdir()) if p.is_file()}}
        (work / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        work.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = capture(args.output)
    print(json.dumps({k: report[k] for k in ['seeds', 'draws_per_seed', 'processes', 'passed']}, indent=2))


if __name__ == '__main__':
    main()

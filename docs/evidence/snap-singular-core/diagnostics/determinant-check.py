"""Reproduce the pinned Eigen check on actual queried f32 world values."""
import ctypes
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
lib = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
fma = lib.fmaf
fma.argtypes = [ctypes.c_float] * 3
fma.restype = ctypes.c_float


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


rows = []
for stage in ['before', 'after']:
    path = HERE / 'world-02' / (stage + '-target.stdout')
    m = json.loads(path.read_bytes())['world_matrix']

    def det2(a, b):
        return f32(f32(m[a][0] * m[b][1]) - f32(m[b][0] * m[a][1]))

    a, b, c, d, e, g = [det2(i, j) for i, j in [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]]

    def det3(i0, d0, i1, d1, i2, d2):
        return fma(m[i0][2], d0, fma(-m[i1][2], d1, f32(m[i2][2] * d2)))

    d3 = [det3(1, g, 2, e, 3, d), det3(0, g, 2, c, 3, b),
          det3(0, e, 1, c, 3, a), det3(0, d, 1, b, 2, a)]
    determinant = f32(fma(-m[0][3], d3[0], f32(m[1][3] * d3[1]))
                      + fma(-m[2][3], d3[2], f32(m[3][3] * d3[3])))
    bits = struct.pack('<f', determinant).hex()
    assert bits == ('00000000' if stage == 'before' else '888d62a4')
    rows.append({'stage': stage, 'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'det2': [a, b, c, d, e, g], 'det3': d3,
                 'check_determinant': determinant, 'check_determinant_f32_le': bits})
print(json.dumps({'passed': True, 'scope': 'diagnostic determinant only; not product acceptance',
                  'source_commit': '8a1083e9bf41b91fdea6546681f806154efdc25a', 'runs': rows}, indent=2))

# SPDX-License-Identifier: GPL-2.0-or-later
"""Reference-only scalar model of the pinned single-corner normal codec.

Source: mesh_normals.cc, RNA mesh API and Python RNA array adapter at e13b728c6880.
This is not a Rust product implementation or a smooth multi-corner fan solver.
"""
import math

from generate_merge_distance_cases import f32


def add(a, b): return f32(f32(a)+f32(b))
def sub(a, b): return f32(f32(a)-f32(b))
def mul(a, b): return f32(f32(a)*f32(b))
def div(a, b): return f32(f32(a)/f32(b))
def dot(a, b): return add(add(mul(a[0], b[0]), mul(a[1], b[1])), mul(a[2], b[2]))
def cross(a, b): return [sub(mul(a[1], b[2]), mul(a[2], b[1])),
                         sub(mul(a[2], b[0]), mul(a[0], b[2])),
                         sub(mul(a[0], b[1]), mul(a[1], b[0]))]
def normalize(v):
    length_squared = dot(v, v)
    if length_squared <= f32(1e-35): return [0., 0., 0.]
    length = f32(math.sqrt(length_squared))
    return [div(x, length) for x in v]


def acos_approx(x):
    x = f32(x); absolute = abs(x)
    m = sub(1., sub(1., absolute)) if absolute < 1. else 1.
    polynomial = add(f32(1.5707963267), mul(m, add(f32(-.213300989), mul(m, add(f32(.077980478), mul(m, f32(-.02164095)))))))
    angle = mul(f32(math.sqrt(sub(1., m))), polynomial)
    return sub(f32(math.pi), angle) if x < 0. else angle


def face_normal(points):
    result = [0., 0., 0.]
    for previous, current in zip(points[-1:]+points[:-1], points):
        result[0] = add(result[0], mul(sub(previous[1], current[1]), add(previous[2], current[2])))
        result[1] = add(result[1], mul(sub(previous[2], current[2]), add(previous[0], current[0])))
        result[2] = add(result[2], mul(sub(previous[0], current[0]), add(previous[1], current[1])))
    return normalize(result)


def space(normal, next_direction, previous_direction, edge_vectors=()):
    threshold = sub(1., f32(1e-4)); pi2 = f32(math.pi*2)
    a, b = dot(next_direction, normal), dot(previous_direction, normal)
    assert abs(a) < threshold and abs(b) < threshold, 'degenerate normal space needs separate source coverage'
    reference = normalize([sub(x, mul(n, a)) for x, n in zip(next_direction, normal)])
    other = normalize([sub(x, mul(n, b)) for x, n in zip(previous_direction, normal)])
    ortho = normalize(cross(normal, reference)); angle = dot(reference, other)
    beta = acos_approx(angle)
    beta = sub(pi2, beta) if dot(ortho, other) < 0. else beta
    if angle >= threshold: beta = pi2
    alpha = 0.
    if edge_vectors:
        for edge in edge_vectors: alpha = add(alpha, acos_approx(dot(edge, normal)))
        alpha = div(alpha, float(len(edge_vectors)))
    else: alpha = div(add(acos_approx(a), acos_approx(b)), 2.)
    return {'normal': normal, 'reference': reference, 'ortho': ortho, 'alpha': alpha, 'beta': beta}


def encode(s, requested):
    # The Python API first casts each component to float, then clamps it to the
    # RNA range [-1, 1]. The mesh setter normalizes that converted vector.
    # rna_mesh_api.cc:345; bpy_rna_array.cc:654; mesh_normals.cc:1693.
    n = normalize([max(-1., min(1., f32(value))) for value in requested])
    return encode_normalized(s, n)


def encode_normalized(s, n):
    if all(x == 0. for x in n) or all(abs(sub(a, b)) <= f32(1e-4) for a, b in zip(s['normal'], n)):
        return [0, 0]
    pi2 = f32(math.pi*2); cosine = dot(s['normal'], n); alpha = acos_approx(cosine)
    alpha_factor = div(-sub(pi2, alpha), sub(pi2, s['alpha'])) if alpha > s['alpha'] else div(alpha, s['alpha'])
    projected = normalize([add(mul(axis, -cosine), value) for axis, value in zip(s['normal'], n)])
    cos_beta = dot(s['reference'], projected)
    beta_factor = 0.
    if cos_beta < sub(1., f32(1e-4)):
        beta = acos_approx(cos_beta)
        if dot(s['ortho'], projected) < 0.: beta = sub(pi2, beta)
        beta_factor = div(-sub(pi2, beta), sub(pi2, s['beta'])) if beta > s['beta'] else div(beta, s['beta'])
    values = [math.floor(add(mul(value, 32767.), .5)) for value in [alpha_factor, beta_factor]]
    assert all(-32767 <= value <= 32767 for value in values)
    return values


def decode(s, packed):
    if packed[0] == 0 or s['alpha'] == 0. or s['beta'] == 0.: return s['normal']
    pi2 = f32(math.pi*2); a = div(float(packed[0]), 32767.); b = div(float(packed[1]), 32767.)
    alpha = mul(s['alpha'] if a > 0. else sub(pi2, s['alpha']), a)
    result = [mul(value, f32(math.cos(alpha))) for value in s['normal']]
    sine = f32(math.sin(alpha))
    if b == 0.:
        return [add(value, mul(axis, sine)) for value, axis in zip(result, s['reference'])]
    beta = mul(s['beta'] if b > 0. else sub(pi2, s['beta']), b)
    x, y = mul(sine, f32(math.cos(beta))), mul(sine, f32(math.sin(beta)))
    return [add(add(value, mul(ref, x)), mul(ortho, y)) for value, ref, ortho in zip(result, s['reference'], s['ortho'])]


def single_corner_fans(mesh):
    incidence = {}
    for name, face in mesh['polygons'].items():
        loop = face['vertices']
        for i in range(len(loop)): incidence.setdefault(frozenset((loop[i-1], loop[i])), []).append(name)
    sharp = {frozenset(mesh['edges'][name]) for name in mesh['sharp_edges']}
    for edge, faces in incidence.items():
        assert not (len(faces) == 2 and edge not in sharp and all(mesh['polygons'][name]['smooth'] for name in faces)), \
            'smooth multi-corner normal fans require a separate reference model'
    normals = {}; packed_values = {}
    for name, face in mesh['polygons'].items():
        points = [mesh['vertices'][v] for v in face['vertices']]; normal = face_normal(points)
        decoded = []; packed = []
        for i, point in enumerate(points):
            next_direction = normalize([sub(x, y) for x, y in zip(points[(i+1) % len(points)], point)])
            previous = normalize([sub(x, y) for x, y in zip(points[i-1], point)])
            s = space(normal, next_direction, previous)
            encoded = encode(s, mesh['custom_corner_normals'][name][i])
            packed.append(encoded); decoded.append(decode(s, encoded))
        normals[name] = decoded; packed_values[name] = packed
    return {'decoded': normals, 'encoded': packed_values, 'scope': 'single-corner normal fans only'}

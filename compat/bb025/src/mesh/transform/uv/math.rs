// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
use super::super::{Vector, add, dot, sub};

fn cross(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[(i + 1) % 3] * b[(i + 2) % 3] - a[(i + 2) % 3] * b[(i + 1) % 3])
}
pub(super) fn unit(v: Vector) -> Vector {
    let d = dot(v, v);
    if d > 1e-35 {
        let inverse = 1. / d.sqrt();
        v.map(|x| x * inverse)
    } else {
        [0.; 3]
    }
}
pub(super) fn projection_axis(normal: Vector, tangent: Vector) -> [Vector; 2] {
    let n = if normal == [0.; 3] {
        let [x, y, z] = tangent;
        let a = [x.abs(), y.abs(), z.abs()];
        unit(if a[0] > a[1] && a[0] > a[2] {
            [-y - z, x, x]
        } else if a[1] > a[2] {
            [y, -x - z, y]
        } else {
            [z, z, -x - y]
        })
    } else {
        normal
    };
    let f = n[0] * n[0] + n[1] * n[1];
    if f > f32::EPSILON {
        let d = 1. / f.sqrt();
        let x = [n[1] * d, -n[0] * d, 0.];
        [x, [-n[2] * x[1], n[2] * x[0], n[0] * x[1] - n[1] * x[0]]]
    } else {
        [[if n[2] < 0. { -1. } else { 1. }, 0., 0.], [0., 1., 0.]]
    }
}
pub(super) fn project(p: Vector, axis: [Vector; 2]) -> [f32; 2] {
    [dot(axis[0], p), dot(axis[1], p)]
}
fn factor(p: [f32; 2], a: [f32; 2], b: [f32; 2]) -> f32 {
    let u = [b[0] - a[0], b[1] - a[1]];
    let h = [p[0] - a[0], p[1] - a[1]];
    let d = u[0] * u[0] + u[1] * u[1];
    if d > 0. {
        (u[0] * h[0] + u[1] * h[1]) / d
    } else {
        0.
    }
}
fn segment_distance(p: [f32; 2], a: [f32; 2], b: [f32; 2]) -> f32 {
    let f = factor(p, a, b);
    let closest = if f <= 0. {
        a
    } else if f >= 1. {
        b
    } else {
        [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
    };
    let x = p[0] - closest[0];
    let y = p[1] - closest[1];
    x * x + y * y
}
fn direction(p: [f32; 2], co: [f32; 2]) -> ([f64; 2], f64) {
    let d = [
        f64::from(p[0]) - f64::from(co[0]),
        f64::from(p[1]) - f64::from(co[1]),
    ];
    (d, (d[0] * d[0] + d[1] * d[1]).sqrt())
}
fn half_tan(a: ([f64; 2], f64), b: ([f64; 2], f64)) -> f64 {
    let area = a.0[0] * b.0[1] - a.0[1] * b.0[0];
    if area != 0. {
        let value = (a.1 * b.1 - (a.0[0] * b.0[0] + a.0[1] * b.0[1])) / area;
        if value.is_finite() {
            return value;
        }
    }
    0.
}
pub(super) fn weights(points: &[[f32; 2]], co: [f32; 2]) -> Vec<f32> {
    let n = points.len();
    let mut weights = vec![0.; n];
    let largest = points
        .iter()
        .flatten()
        .enumerate()
        .fold(0_f32, |m, (i, v)| m.max((*v - co[i % 2]).abs()));
    let eps = 16. * f32::EPSILON * largest;
    let eps_squared = eps * eps;
    let mut current = n - 1;
    let mut next = 0;
    let mut d_next = direction(points[current], co);
    let mut previous = half_tan(direction(points[n - 2], co), d_next);
    let mut total = 0.;
    while next < n {
        if d_next.1 < f64::from(eps) {
            weights.fill(0.);
            weights[current] = 1.;
            return weights;
        }
        if segment_distance(co, points[current], points[next]) < eps_squared {
            let f = factor(co, points[current], points[next]).clamp(0., 1.);
            weights.fill(0.);
            weights[current] = 1. - f;
            weights[next] = f;
            return weights;
        }
        let d_current = d_next;
        d_next = direction(points[next], co);
        let half = half_tan(d_current, d_next);
        weights[current] = if d_current.1 == 0. {
            0.
        } else {
            ((previous + half) / d_current.1) as f32
        };
        total += weights[current];
        current = next;
        next += 1;
        previous = half;
    }
    if total != 0. {
        for value in &mut weights {
            *value /= total;
        }
    }
    weights
}
pub(super) fn corner_angle(points: &[Vector], corner: usize) -> f32 {
    let n = points.len();
    let p = points[corner];
    let mut prev = (corner + n - 1) % n;
    while dot(sub(p, points[prev]), sub(p, points[prev])) < f32::EPSILON {
        prev = (prev + n - 1) % n;
        if prev == (corner + 1) % n {
            return 0.;
        }
    }
    let mut next = (corner + 1) % n;
    while dot(sub(p, points[next]), sub(p, points[next])) < f32::EPSILON {
        next = (next + 1) % n;
        if next == prev {
            return 0.;
        }
    }
    let a = unit(sub(p, points[prev]));
    let b = unit(sub(p, points[next]));
    let (difference, negative) = if dot(a, b) >= 0. {
        (sub(a, b), false)
    } else {
        (add(a, b), true)
    };
    let angle = 2.
        * (dot(difference, difference).sqrt() / 2.)
            .clamp(-1., 1.)
            .asin();
    if negative {
        std::f32::consts::PI - angle
    } else {
        angle
    }
}
fn plane(p: Vector, axis: Vector) -> Vector {
    add(p, axis.map(|x| x * -dot(p, axis)))
}
fn signed_plane(p: Vector, normal: Vector) -> f32 {
    let len = dot(normal, normal);
    let side = dot(normal, p);
    let f = side / len;
    (len * (f * f)).copysign(side)
}
fn corner_distance(p: Vector, a: Vector, b: Vector, c: Vector, axis_ref: Vector) -> f32 {
    let da = sub(a, b);
    let db = sub(c, b);
    let mut axis = cross(da, db);
    let mut flip = false;
    if dot(axis, axis) < f32::EPSILON {
        axis = axis_ref;
    } else if dot(axis, axis_ref) < 0. {
        flip = true;
        axis = axis.map(|v| -v);
    }
    let a = signed_plane(sub(p, b), cross(da, axis));
    let b = signed_plane(sub(p, b), cross(axis, db));
    if flip {
        if a < b { a } else { b }
    } else if a > b {
        a
    } else {
        b
    }
}
pub(super) fn moved_weight(points: &[Vector], corner: usize, moved: Vector, axis: Vector) -> f32 {
    let n = points.len();
    let b = plane(points[corner], axis);
    let mut prev = (corner + n - 1) % n;
    let mut next = (corner + 1) % n;
    let mut a = plane(points[prev], axis);
    while dot(sub(b, a), sub(b, a)) <= 1e-8 {
        prev = (prev + n - 1) % n;
        if prev == (corner + 1) % n {
            break;
        }
        a = plane(points[prev], axis);
    }
    let mut c = plane(points[next], axis);
    while dot(sub(b, c), sub(b, c)) <= 1e-8 {
        next = (next + 1) % n;
        if next == (corner + n - 1) % n {
            break;
        }
        c = plane(points[next], axis);
    }
    if dot(sub(b, a), sub(b, a)) <= 1e-8 || dot(sub(b, c), sub(b, c)) <= 1e-8 {
        return 0.;
    }
    let distance = corner_distance(moved, a, b, c, axis);
    let weight = if distance >= 0. {
        1.
    } else if distance <= -1e-8 {
        0.
    } else {
        1. + distance / 1e-8
    };
    if weight.is_finite() { weight } else { 0. }
}

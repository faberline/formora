// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
// Behavior derived from Blender e13b728c6880 BMesh primitives and KD partition order.
// See docs/rotational-primitives.md for provenance and the retained license text.
//! Parametric surfaces, with source polygons and independent face/corner normal data.
use super::{Builder, CircleFill, MAX_DIMENSION, MAX_DIVISIONS, Primitive, vertex_id};
use crate::scene::{Result, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum TorusMode {
    #[default]
    MajorMinor,
    ExtInt,
}
pub(super) fn rings() -> u32 {
    16
}
pub(super) fn cap_fill() -> CircleFill {
    CircleFill::Ngon
}
pub(super) fn major_segments() -> u32 {
    48
}
pub(super) fn minor_segments() -> u32 {
    12
}
pub(super) fn minor_radius() -> f64 {
    0.25
}
pub(super) fn outer_radius() -> f64 {
    1.25
}
pub(super) fn inner_radius() -> f64 {
    0.75
}
fn fail<T>(message: &str) -> Result<T> {
    Err(SceneError(message.into()))
}
fn dimensions(values: &[f64], max: f64) -> bool {
    values
        .iter()
        .all(|n| n.is_finite() && (0. ..=max).contains(n))
}

pub(super) fn component_count(p: &Primitive) -> Result<usize> {
    if let Primitive::UvSphere {
        creation_rotation, ..
    }
    | Primitive::Cylinder {
        creation_rotation, ..
    }
    | Primitive::Cone {
        creation_rotation, ..
    } = p
    {
        if creation_rotation
            .iter()
            .any(|a| !a.is_finite() || a.abs() > f32::MAX as f64)
        {
            return fail("creation rotation must fit a finite f32 angle");
        }
    }
    let value = (|| -> Option<usize> {
        Some(match p {
            Primitive::UvSphere {
                radius,
                segments,
                ring_count,
                ..
            } => {
                if !dimensions(&[*radius], MAX_DIMENSION)
                    || !(3..=100000).contains(segments)
                    || !(3..=100000).contains(ring_count)
                {
                    return None;
                }
                if *radius == 0. {
                    1
                } else {
                    (*segments as usize)
                        .checked_mul((*ring_count as usize).checked_mul(8)?.checked_sub(4)?)?
                        .checked_add(2)?
                }
            }
            Primitive::Cylinder {
                radius,
                depth,
                vertices,
                end_fill_type,
                ..
            } => conic_count(*radius, *radius, *depth, *vertices, *end_fill_type)?,
            Primitive::Cone {
                radius1,
                radius2,
                depth,
                vertices,
                end_fill_type,
                ..
            } => conic_count(*radius1, *radius2, *depth, *vertices, *end_fill_type)?,
            Primitive::Torus {
                major_segments,
                minor_segments,
                major_radius,
                minor_radius,
                abso_major_rad,
                abso_minor_rad,
                ..
            } => {
                if !dimensions(
                    &[
                        *major_radius,
                        *minor_radius,
                        *abso_major_rad,
                        *abso_minor_rad,
                    ],
                    10000.,
                ) || !(3..=256).contains(major_segments)
                    || !(3..=256).contains(minor_segments)
                {
                    return None;
                }
                (*major_segments as usize)
                    .checked_mul(*minor_segments as usize)?
                    .checked_mul(8)?
            }
            _ => return None,
        })
    })();
    value.ok_or_else(|| {
        SceneError("invalid rotational primitive parameters or component arithmetic".into())
    })
}
fn conic_count(r1: f64, r2: f64, depth: f64, n: u32, fill: CircleFill) -> Option<usize> {
    if !dimensions(&[r1, r2, depth], MAX_DIMENSION) || !(3..=MAX_DIVISIONS).contains(&n) {
        return None;
    }
    if r1 == 0. && r2 == 0. {
        return Some(3);
    }
    let n = n as usize;
    let both = r1 > 0. && r2 > 0.;
    let (factor, extra) = match (both, fill) {
        (true, CircleFill::Nothing) => (10, 0),
        (true, CircleFill::Ngon) => (12, 2),
        (true, CircleFill::Trifan) => (20, 2),
        (false, CircleFill::Nothing) => (7, 1),
        (false, CircleFill::Ngon) => (8, 2),
        (false, CircleFill::Trifan) => (12, 2),
    };
    n.checked_mul(factor)?.checked_add(extra)
}

impl Builder {
    fn surface(&mut self, indices: &[usize], uv: Vec<[f64; 2]>) {
        let points: Vec<_> = indices
            .iter()
            .map(|i| self.asset.vertices[&vertex_id(*i)])
            .collect();
        let normal = polygon_normal(&points, false);
        let corner = polygon_normal(&points, true);
        self.face(indices, uv, normal);
        let last = format!("p{:06}", self.asset.polygons.len() - 1);
        self.asset
            .polygons
            .get_mut(&last)
            .expect("new polygon")
            .corner_normals = Some(vec![corner; indices.len()]);
    }
}

fn polygon_normal(points: &[[f64; 3]], single: bool) -> [f64; 3] {
    let mut n = [0.; 3];
    for i in 0..points.len() {
        let a = points[(i + points.len() - 1) % points.len()];
        let b = points[i];
        for j in 0..3 {
            let term = if single {
                ((a[(j + 1) % 3] as f32 - b[(j + 1) % 3] as f32)
                    * (a[(j + 2) % 3] as f32 + b[(j + 2) % 3] as f32)) as f64
            } else {
                (a[(j + 1) % 3] - b[(j + 1) % 3]) * (a[(j + 2) % 3] + b[(j + 2) % 3])
            };
            n[j] = if single {
                (n[j] as f32 + term as f32) as f64
            } else {
                n[j] + term
            };
        }
    }
    let length = n.iter().map(|n| n * n).sum::<f64>().sqrt();
    if length == 0. {
        return [0., 0., 1.];
    }
    if single {
        let inv = (1. / length) as f32;
        n.map(|v| ((v as f32) * inv) as f64)
    } else {
        n.map(|v| v / length)
    }
}

pub(super) fn generate(p: &Primitive, b: &mut Builder) -> Result<()> {
    match p {
        Primitive::UvSphere {
            radius,
            segments,
            ring_count,
            ..
        } => sphere(b, *radius as f32, *segments as usize, *ring_count as usize),
        Primitive::Cylinder {
            radius,
            depth,
            vertices,
            end_fill_type,
            ..
        } => conic(
            b,
            *radius as f32,
            *radius as f32,
            *depth as f32,
            *vertices as usize,
            *end_fill_type,
        ),
        Primitive::Cone {
            radius1,
            radius2,
            depth,
            vertices,
            end_fill_type,
            ..
        } => conic(
            b,
            *radius1 as f32,
            *radius2 as f32,
            *depth as f32,
            *vertices as usize,
            *end_fill_type,
        ),
        Primitive::Torus {
            major_segments,
            minor_segments,
            mode,
            major_radius,
            minor_radius,
            abso_major_rad,
            abso_minor_rad,
            ..
        } => {
            let (major, minor) = if *mode == TorusMode::ExtInt {
                (
                    (*abso_major_rad + *abso_minor_rad) * 0.5,
                    ((*abso_major_rad - *abso_minor_rad) * 0.5).max(0.),
                )
            } else {
                (*major_radius, *minor_radius)
            };
            torus(
                b,
                major as f32,
                minor as f32,
                *major_segments as usize,
                *minor_segments as usize,
            );
        }
        _ => return fail("not a rotational primitive"),
    }
    if let Primitive::UvSphere {
        scale,
        creation_rotation,
        ..
    }
    | Primitive::Cylinder {
        scale,
        creation_rotation,
        ..
    }
    | Primitive::Cone {
        scale,
        creation_rotation,
        ..
    } = p
    {
        let basis = creation_basis(*creation_rotation, *scale);
        for position in b.asset.vertices.values_mut() {
            let point = position.map(|v| v as f32);
            *position =
                basis.map(|row| (row[0] * point[0] + row[1] * point[1] + row[2] * point[2]) as f64);
        }
        for polygon in b.asset.polygons.values_mut() {
            let points: Vec<_> = polygon
                .vertices
                .iter()
                .map(|id| b.asset.vertices[id])
                .collect();
            polygon.normal = Some(polygon_normal(&points, false));
            polygon.corner_normals = Some(vec![polygon_normal(&points, true); points.len()]);
        }
    }
    Ok(())
}
// The creation frame uses float trigonometry promoted to double products.
// The object frame uses double trigonometry. Convert between those rounded
// frames before applying local scale. Zero rotation gives an exact identity.
fn creation_basis(rotation: [f64; 3], scale: [f64; 3]) -> [[f32; 3]; 3] {
    fn euler(rotation: [f64; 3], single: bool) -> [[f32; 3]; 3] {
        let trig = rotation.map(|angle| {
            let angle = angle as f32;
            if single {
                let (s, c) = angle.sin_cos();
                (s as f64, c as f64)
            } else {
                (angle as f64).sin_cos()
            }
        });
        let [(si, ci), (sj, cj), (sh, ch)] = trig;
        let (cc, cs, sc, ss) = (ci * ch, ci * sh, si * ch, si * sh);
        [
            [
                (cj * ch) as f32,
                (sj * sc - cs) as f32,
                (sj * cc + ss) as f32,
            ],
            [
                (cj * sh) as f32,
                (sj * ss + cc) as f32,
                (sj * cs - sc) as f32,
            ],
            [-sj as f32, (cj * si) as f32, (cj * ci) as f32],
        ]
    }
    fn inverse(m: [[f32; 3]; 3]) -> [[f32; 3]; 3] {
        let adj: [[f32; 3]; 3] = std::array::from_fn(|i| {
            std::array::from_fn(|j| {
                m[(j + 1) % 3][(i + 1) % 3] * m[(j + 2) % 3][(i + 2) % 3]
                    - m[(j + 1) % 3][(i + 2) % 3] * m[(j + 2) % 3][(i + 1) % 3]
            })
        });
        let det = m[0][0] * adj[0][0] + m[0][1] * adj[1][0] + m[0][2] * adj[2][0];
        let reciprocal = 1. / det;
        adj.map(|row| row.map(|v| v * reciprocal))
    }
    let a = inverse(euler(rotation, true));
    let b = euler(rotation, false);
    let combined = std::array::from_fn(|i| {
        std::array::from_fn(|j| a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j])
    });
    let mut basis = inverse(combined);
    for row in &mut basis {
        for (value, scale) in row.iter_mut().zip(scale) {
            *value *= scale as f32;
        }
    }
    basis
}

fn point(radius: f32, theta: f64, z: f32) -> [f64; 3] {
    [
        (radius * theta.sin() as f32) as f64,
        (radius * theta.cos() as f32) as f64,
        z as f64,
    ]
}
fn disk(theta: f64, x: f64, r: f64) -> [f64; 2] {
    [
        (x + r * theta.sin()) as f32 as f64,
        (0.25 + r * theta.cos()) as f32 as f64,
    ]
}

fn conic(b: &mut Builder, r1: f32, r2: f32, depth: f32, n: usize, fill: CircleFill) {
    let half = depth * 0.5;
    if r1 == 0. && r2 == 0. {
        let a = b.vertex([0., 0., -half as f64]);
        let c = b.vertex([0., 0., half as f64]);
        b.edge(a, c);
        return;
    }
    let bottom: Vec<_> = if r1 == 0. {
        vec![b.vertex([0., 0., -half as f64])]
    } else {
        (0..n)
            .map(|i| {
                b.vertex(point(
                    r1,
                    std::f64::consts::TAU * i as f64 / n as f64,
                    -half,
                ))
            })
            .collect()
    };
    let top: Vec<_> = if r2 == 0. {
        vec![b.vertex([0., 0., half as f64])]
    } else {
        (0..n)
            .map(|i| b.vertex(point(r2, std::f64::consts::TAU * i as f64 / n as f64, half)))
            .collect()
    };
    for i in 0..n {
        let j = (i + 1) % n;
        let t0 = std::f64::consts::TAU * i as f64 / n as f64;
        let t1 = std::f64::consts::TAU * (i + 1) as f64 / n as f64;
        if r1 > 0. && r2 > 0. {
            let u0 = 1. - i as f64 / n as f64;
            let u1 = 1. - (i + 1) as f64 / n as f64;
            let v0 = if fill == CircleFill::Nothing { 0. } else { 0.5 };
            b.surface(
                &[bottom[i], top[i], top[j], bottom[j]],
                vec![[u0, v0], [u0, 1.], [u1, 1.], [u1, v0]],
            );
        } else {
            let r = if fill == CircleFill::Nothing {
                0.5
            } else {
                0.24
            };
            let x = if fill == CircleFill::Nothing {
                0.5
            } else if r1 > 0. {
                0.25
            } else {
                0.75
            };
            let y = if fill == CircleFill::Nothing {
                0.5
            } else {
                0.25
            };
            let uv = |t: f64| {
                [
                    (x + r * t.sin()) as f32 as f64,
                    (y + r * t.cos()) as f32 as f64,
                ]
            };
            if r1 > 0. {
                b.surface(
                    &[bottom[i], top[0], bottom[j]],
                    vec![uv(t0), [x, y], uv(t1)],
                );
            } else {
                b.surface(&[bottom[0], top[i], top[j]], vec![[x, y], uv(t0), uv(t1)]);
            }
        }
    }
    if fill != CircleFill::Nothing {
        for (ring, absent, is_top, z, center_x) in [
            (&bottom, r1 == 0., false, -half, 0.75),
            (&top, r2 == 0., true, half, 0.25),
        ] {
            if absent {
                continue;
            }
            if fill == CircleFill::Ngon {
                let order: Vec<_> = if is_top {
                    (0..n).rev().collect()
                } else {
                    (0..n).collect()
                };
                let indices: Vec<_> = order.iter().map(|i| ring[*i]).collect();
                let uv = order
                    .iter()
                    .map(|i| disk(std::f64::consts::TAU * *i as f64 / n as f64, center_x, 0.24))
                    .collect();
                b.surface(&indices, uv);
            } else {
                let center = b.vertex([0., 0., z as f64]);
                for i in 0..n {
                    let j = (i + 1) % n;
                    let pair = if is_top { [j, i] } else { [i, j] };
                    b.surface(
                        &[center, ring[pair[0]], ring[pair[1]]],
                        vec![
                            [center_x, 0.25],
                            disk(
                                std::f64::consts::TAU * pair[0] as f64 / n as f64,
                                center_x,
                                0.24,
                            ),
                            disk(
                                std::f64::consts::TAU * pair[1] as f64 / n as f64,
                                center_x,
                                0.24,
                            ),
                        ],
                    );
                }
            }
        }
    }
}

// Reduce rational turns to the nearest octant before f32 trigonometry.
// This preserves symmetry at axis and diagonal samples.
fn fraction_sin_cos(numerator: usize, denominator: usize) -> (f32, f32) {
    let octant = 8 * numerator / denominator;
    let d = (8 * denominator) as i64;
    let n = (8 * numerator) as i64;
    let reduced = match octant {
        0 => n,
        1 | 2 => d / 4 - n,
        3 | 4 => d / 2 - n,
        5 | 6 => n - 3 * d / 4,
        _ => n - d,
    };
    let (sin, cos) = (std::f32::consts::TAU * (reduced as f32 / d as f32)).sin_cos();
    let sign = if (3..=6).contains(&octant) { -1. } else { 1. };
    if matches!(octant, 1 | 2 | 5 | 6) {
        (cos * sign, sin)
    } else {
        (sin, cos * sign)
    }
}

// Median partitions use a rightmost pivot and a two-sided scan. Equal values
// swap in a fixed order. This makes seam selection stable across platforms.
fn partition_samples(ids: &mut [usize], points: &[[f32; 3]], axis: usize) {
    if ids.len() < 2 {
        return;
    }
    let median = ids.len() / 2;
    let mut left = 0;
    let mut right = ids.len() - 1;
    while left < right {
        let pivot = points[ids[right]][axis];
        let mut low = left;
        let mut high = right - 1;
        loop {
            while points[ids[low]][axis] < pivot {
                low += 1;
            }
            while high > left && points[ids[high]][axis] > pivot {
                high -= 1;
            }
            if low >= high {
                break;
            }
            ids.swap(low, high);
            low += 1;
            high -= 1;
        }
        ids.swap(low, right);
        if low >= median {
            if low == 0 {
                break;
            }
            right = low - 1;
        }
        if low <= median {
            left = low + 1;
        }
    }
    let (before, rest) = ids.split_at_mut(median);
    partition_samples(before, points, (axis + 1) % 3);
    partition_samples(&mut rest[1..], points, (axis + 1) % 3);
}

fn sphere(b: &mut Builder, r: f32, s: usize, rings: usize) {
    if r == 0. {
        b.vertex([0.; 3]);
        return;
    }
    let angle = (std::f64::consts::TAU / s as f64) as f32;
    let (sin, cos) = angle.sin_cos();
    let zz = (1. - cos) + cos;
    let offset = -r - zz * -r;
    let mut meridian: Vec<_> = (0..=rings)
        .map(|j| {
            let (sp, cp) = fraction_sin_cos(j, 2 * rings);
            [0., r * sp, r * cp]
        })
        .collect();
    let mut spun = Vec::with_capacity((s + 1) * (rings + 1));
    for _ in 0..=s {
        spun.extend_from_slice(&meridian);
        for position in &mut meridian {
            *position = [
                cos * position[0] + sin * position[1],
                -sin * position[0] + cos * position[1],
                zz * position[2] + offset,
            ];
        }
    }
    // The spatial partition determines which coincident seam sample survives.
    // Retain that sample rather than averaging or replacing it with an ideal circle.
    let mut order: Vec<_> = (0..spun.len()).collect();
    partition_samples(&mut order, &spun, 0);
    let mut rank = vec![0; spun.len()];
    for (i, id) in order.into_iter().enumerate() {
        rank[id] = i;
    }
    let north = b.vertex(spun[0].map(f64::from));
    let south = b.vertex(spun[rings].map(f64::from));
    let mut grid = vec![vec![0; rings - 1]; s];
    for (i, column) in grid.iter_mut().enumerate() {
        for j in 1..rings {
            let original = i * (rings + 1) + j;
            let seam = s * (rings + 1) + j;
            let chosen = if i == 0 && rank[seam] < rank[original] {
                seam
            } else {
                original
            };
            column[j - 1] = b.vertex(spun[chosen].map(f64::from));
        }
    }
    for i in 0..s {
        let next = (i + 1) % s;
        let mut u0 = ((3 * s / 4 + s - i) % s) as f64 / s as f64;
        if u0 == 0. {
            u0 = 1.;
        }
        let u1 = u0 - 1. / s as f64;
        let mid = (u0 + u1) * 0.5;
        b.surface(
            &[grid[i][0], north, grid[next][0]],
            vec![
                [u0, 1. - 1. / rings as f64],
                [mid, 1.],
                [u1, 1. - 1. / rings as f64],
            ],
        );
        for j in 1..rings - 1 {
            let v0 = 1. - j as f64 / rings as f64;
            let v1 = 1. - (j + 1) as f64 / rings as f64;
            b.surface(
                &[grid[i][j], grid[i][j - 1], grid[next][j - 1], grid[next][j]],
                vec![[u0, v1], [u0, v0], [u1, v0], [u1, v1]],
            );
        }
        b.surface(
            &[south, grid[i][rings - 2], grid[next][rings - 2]],
            vec![[mid, 0.], [u0, 1. / rings as f64], [u1, 1. / rings as f64]],
        );
    }
}

fn torus(b: &mut Builder, major: f32, minor: f32, m: usize, n: usize) {
    for i in 0..m {
        let angle = (std::f64::consts::TAU * i as f64 / m as f64) as f32;
        let a =
            (angle + std::f32::consts::PI).rem_euclid(std::f32::consts::TAU) - std::f32::consts::PI;
        for j in 0..n {
            let t = std::f64::consts::TAU * j as f64 / n as f64;
            let r = (major as f64 + minor as f64 * t.cos()) as f32;
            b.vertex([
                (r * a.cos()) as f64,
                (r * a.sin()) as f64,
                (minor as f64 * t.sin()) as f32 as f64,
            ]);
        }
    }
    for i in 0..m {
        for j in 0..n {
            let u0 = ((i + m.div_ceil(2)) % m) as f64 / m as f64;
            let v0 = ((j + n.div_ceil(2)) % n) as f64 / n as f64;
            let u1 = u0 + 1. / m as f64;
            let v1 = v0 + 1. / n as f64;
            b.surface(
                &[
                    i * n + j,
                    ((i + 1) % m) * n + j,
                    ((i + 1) % m) * n + (j + 1) % n,
                    i * n + (j + 1) % n,
                ],
                vec![[u0, v0], [u1, v0], [u1, v1], [u0, v1]],
            );
        }
    }
}

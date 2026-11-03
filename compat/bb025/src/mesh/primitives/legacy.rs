// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
// Pinned BMesh primitive tables, edge subdivision and mirror rules.
use super::{
    Builder, MAX_DIMENSION, Primitive, legacy_tables::*, rotational::creation_basis, vertex_id,
};
use crate::scene::{Result, SceneError};
use std::collections::BTreeMap;

pub(super) fn subdivisions() -> u32 {
    2
}
pub(super) fn component_count(primitive: &Primitive) -> Result<usize> {
    let (dimension, rotation, count) = match primitive {
        Primitive::IcoSphere {
            radius,
            subdivisions,
            creation_rotation,
            ..
        } => {
            if !(1..=10).contains(subdivisions) {
                return Err(SceneError(
                    "icosphere subdivisions must be within 1..10".into(),
                ));
            }
            let n = 1usize
                .checked_shl(subdivisions - 1)
                .ok_or_else(|| SceneError("icosphere subdivision arithmetic overflow".into()))?;
            let count = n
                .checked_mul(n)
                .and_then(|x| x.checked_mul(120))
                .and_then(|x| x.checked_add(2))
                .ok_or_else(|| SceneError("icosphere component arithmetic overflow".into()))?;
            (*radius, creation_rotation, count)
        }
        Primitive::Monkey {
            size,
            creation_rotation,
            ..
        } => (*size, creation_rotation, 3980),
        _ => return Err(SceneError("not a legacy primitive".into())),
    };
    if !dimension.is_finite() || !(0. ..=MAX_DIMENSION).contains(&dimension) {
        return Err(SceneError(
            "legacy primitive dimension is outside the finite range".into(),
        ));
    }
    if rotation
        .iter()
        .any(|angle| !angle.is_finite() || angle.abs() > f32::MAX as f64)
    {
        return Err(SceneError(
            "creation rotation must fit a finite f32 angle".into(),
        ));
    }
    Ok(count)
}

struct Face {
    vertices: Vec<usize>,
    uv: Vec<[f64; 2]>,
}
pub(super) fn generate(primitive: &Primitive, b: &mut Builder) -> Result<()> {
    let (faces, basis) = match primitive {
        Primitive::IcoSphere {
            radius,
            subdivisions,
            scale,
            creation_rotation,
            ..
        } => (
            icosphere(b, *radius as f32, *subdivisions),
            creation_basis(*creation_rotation, *scale),
        ),
        Primitive::Monkey {
            size,
            creation_rotation,
            ..
        } => {
            let mut basis = creation_basis(*creation_rotation, [1.; 3]);
            let half = (*size as f32) * 0.5;
            for row in &mut basis {
                for value in row {
                    *value *= half;
                }
            }
            (monkey(b), basis)
        }
        _ => return Err(SceneError("not a legacy primitive".into())),
    };
    for position in b.asset.vertices.values_mut() {
        let point = position.map(|v| v as f32);
        *position =
            basis.map(|row| (row[0] * point[0] + row[1] * point[1] + row[2] * point[2]) as f64);
    }
    for face in faces {
        b.surface(&face.vertices, face.uv);
    }
    Ok(())
}

fn project(point: [f32; 3], radius: f32) -> [f32; 3] {
    let length2 = point[0] * point[0] + point[1] * point[1] + point[2] * point[2];
    if length2 > 1e-35 {
        let factor = radius / length2.sqrt();
        point.map(|x| x * factor)
    } else {
        [0.; 3]
    }
}
fn position(b: &Builder, id: usize) -> [f32; 3] {
    b.asset.vertices[&vertex_id(id)].map(|x| x as f32)
}
fn lerp(a: [f32; 3], b: [f32; 3], factor: f32) -> [f32; 3] {
    std::array::from_fn(|i| a[i] + (b[i] - a[i]) * factor)
}
fn uv_lerp(a: [f32; 2], b: [f32; 2], factor: f32) -> [f32; 2] {
    std::array::from_fn(|i| a[i] * (1. - factor) + b[i] * factor)
}

fn icosphere(b: &mut Builder, radius: f32, subdivisions: u32) -> Vec<Face> {
    let divisor = radius / 200.;
    for point in ICO_VERTICES {
        b.vertex(point.map(|x| (x * divisor) as f64));
    }
    if subdivisions == 1 {
        return ICO_FACES
            .iter()
            .enumerate()
            .map(|(i, face)| Face {
                vertices: face.to_vec(),
                uv: ICO_UVS[i * 3..i * 3 + 3]
                    .iter()
                    .map(|p| p.map(f64::from))
                    .collect(),
            })
            .collect();
    }
    let n = 1usize << (subdivisions - 1);
    let mut edge_samples: BTreeMap<[usize; 2], Vec<usize>> = BTreeMap::new();
    for face in ICO_FACES {
        for i in 0..3 {
            let (a, c) = (face[(i + 2) % 3], face[i]);
            let key = if a < c { [a, c] } else { [c, a] };
            if edge_samples.contains_key(&key) {
                continue;
            }
            let mut samples = vec![a];
            let mut current = position(b, a);
            let target = position(b, c);
            for k in 0..n - 1 {
                current = lerp(current, target, 1. / (n - k) as f32);
                samples.push(b.vertex(project(current, radius).map(f64::from)));
            }
            samples.push(c);
            if a > c {
                samples.reverse();
            }
            edge_samples.insert(key, samples);
        }
    }
    for i in 0..12 {
        let p = project(position(b, i), radius);
        b.asset.vertices.insert(vertex_id(i), p.map(f64::from));
    }
    let sample = |a: usize, c: usize, k: usize| {
        if a < c {
            edge_samples[&[a, c]][k]
        } else {
            edge_samples[&[c, a]][n - k]
        }
    };
    let mut faces = Vec::with_capacity(20 * n * n);
    for (face_index, [a, c, apex]) in ICO_FACES.into_iter().enumerate() {
        let [ua, uc, ut] = [
            ICO_UVS[face_index * 3],
            ICO_UVS[face_index * 3 + 1],
            ICO_UVS[face_index * 3 + 2],
        ];
        let mut previous = vec![apex];
        let mut previous_uv = vec![ut];
        for row in 1..=n {
            let left = sample(apex, a, row);
            let right = sample(apex, c, row);
            let ul = uv_lerp(ut, ua, row as f32 / n as f32);
            let ur = uv_lerp(ut, uc, row as f32 / n as f32);
            let mut ids = vec![left];
            let mut uvs = vec![ul];
            let mut current = position(b, left);
            let target = position(b, right);
            for col in 1..row {
                let id = if row == n {
                    sample(a, c, col)
                } else {
                    current = lerp(current, target, 1. / (row - col + 1) as f32);
                    b.vertex(project(current, radius).map(f64::from))
                };
                ids.push(id);
                uvs.push(uv_lerp(ul, ur, col as f32 / row as f32));
            }
            ids.push(right);
            uvs.push(ur);
            for col in 0..row {
                faces.push(Face {
                    vertices: vec![previous[col], ids[col], ids[col + 1]],
                    uv: vec![
                        previous_uv[col].map(f64::from),
                        uvs[col].map(f64::from),
                        uvs[col + 1].map(f64::from),
                    ],
                });
                if col + 1 < row {
                    faces.push(Face {
                        vertices: vec![previous[col], ids[col + 1], previous[col + 1]],
                        uv: vec![
                            previous_uv[col].map(f64::from),
                            uvs[col + 1].map(f64::from),
                            previous_uv[col + 1].map(f64::from),
                        ],
                    });
                }
            }
            previous = ids;
            previous_uv = uvs;
        }
    }
    faces
}

fn monkey(b: &mut Builder) -> Vec<Face> {
    let mut mirror = Vec::with_capacity(271);
    for [x, y, z] in MONKEY_VERTICES {
        let point = [(x as f32 + 127.) / 128., z as f32 / -128., y as f32 / 128.];
        let first = b.vertex(point.map(f64::from));
        let second = if point[0].abs() < 0.001 {
            first
        } else {
            b.vertex([-point[0] as f64, point[1] as f64, point[2] as f64])
        };
        mirror.push([first, second]);
    }
    let mut uv_index = 0;
    let mut faces = Vec::with_capacity(500);
    for (i, face) in MONKEY_FACES.into_iter().enumerate() {
        let count = if face[2] == face[3] { 3 } else { 4 };
        for (side, order) in [[0, 1, 2, 3], [2, 1, 0, 3]].into_iter().enumerate() {
            let vertices = order[..count]
                .iter()
                .map(|&j| mirror[(face[j] as i32 + i as i32 - 4) as usize][side])
                .collect();
            let uv = MONKEY_UVS[uv_index..uv_index + count]
                .iter()
                .map(|p| p.map(f64::from))
                .collect();
            uv_index += count;
            faces.push(Face { vertices, uv });
        }
    }
    assert_eq!(uv_index, MONKEY_UVS.len());
    faces
}

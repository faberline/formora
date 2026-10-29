// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-FileCopyrightText: 2022 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
//! Automatic normals and read-only resolution of explicit normal payloads.
use super::{
    MeshAsset,
    selection::{FaceRef, Graph},
};
use crate::scene::{Result, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

type Vector = [f32; 3];
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct FaceNormals {
    pub face: FaceRef,
    pub normal: [f64; 3],
    pub corner_normals: Vec<[f64; 3]>,
}
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct MeshNormals {
    pub faces: Vec<FaceNormals>,
}
fn sub(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|j| a[j] - b[j])
}
fn dot(a: Vector, b: Vector) -> f32 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}
fn cross(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|j| a[(j + 1) % 3] * b[(j + 2) % 3] - a[(j + 2) % 3] * b[(j + 1) % 3])
}
fn normalized(v: Vector, reciprocal: bool) -> Vector {
    let length = dot(v, v);
    if !length.is_finite() {
        return [f32::NAN; 3];
    }
    if length > 1e-35 {
        let length = length.sqrt();
        if reciprocal {
            let inverse = 1. / length;
            v.map(|x| x * inverse)
        } else {
            v.map(|x| x / length)
        }
    } else {
        [0.; 3]
    }
}
fn fallback(v: Vector) -> Vector {
    if v == [0.; 3] { [0., 0., 1.] } else { v }
}
fn newell(points: &[Vector]) -> Vector {
    let mut n = [0.; 3];
    for (i, b) in points.iter().enumerate() {
        let a = points[(i + points.len() - 1) % points.len()];
        for j in 0..3 {
            n[j] += (a[(j + 1) % 3] - b[(j + 1) % 3]) * (a[(j + 2) % 3] + b[(j + 2) % 3]);
        }
    }
    fallback(normalized(n, true))
}
fn polygon_normal(points: &[Vector]) -> Vector {
    let n = match points.len() {
        3 => normalized(
            cross(sub(points[0], points[1]), sub(points[1], points[2])),
            true,
        ),
        4 => normalized(
            cross(sub(points[0], points[2]), sub(points[1], points[3])),
            true,
        ),
        _ => return newell(points),
    };
    fallback(n)
}
fn angle(x: f32) -> f32 {
    if !x.is_finite() {
        return f32::NAN;
    }
    let f = x.abs();
    let m = if f < 1. { 1. - (1. - f) } else { 1. };
    // These are the pinned source coefficients rounded to their exact f32 values.
    let a = (1. - m).sqrt()
        * (std::f32::consts::FRAC_PI_2
            + m * (-0.213_300_99 + m * (0.077_980_48 + m * -0.021_640_95)));
    if x < 0. { std::f32::consts::PI - a } else { a }
}
fn smooth(asset: &MeshAsset, face: &FaceRef) -> bool {
    match face {
        FaceRef::Polygon(id) => asset.polygons[id].smooth,
        FaceRef::Triangle(id) => asset.smooth_triangles.contains(id),
    }
}

/// Derive automatic values without changing explicit payloads, IDs or editing state.
pub fn automatic(asset: &MeshAsset) -> Result<MeshNormals> {
    asset.validate()?;
    let graph = Graph::new(asset)?;
    let positions: Vec<_> = graph
        .positions
        .iter()
        .map(|p| p.map(|v| v as f32))
        .collect();
    if positions.iter().flatten().any(|v| !v.is_finite()) {
        return Err(SceneError(
            "automatic normals require finite f32 geometry".into(),
        ));
    }
    let smooth: Vec<_> = graph.faces.iter().map(|f| smooth(asset, &f.key)).collect();
    let mut true_normals = Vec::with_capacity(graph.faces.len());
    let mut output = MeshNormals::default();
    let mut angles = Vec::with_capacity(graph.faces.len());
    for face in &graph.faces {
        let points: Vec<_> = face.vertices.iter().map(|v| positions[*v]).collect();
        let normal = polygon_normal(&points);
        let true_normal = newell(&points);
        if normal
            .iter()
            .chain(true_normal.iter())
            .any(|v| !v.is_finite())
        {
            return Err(SceneError(
                "automatic normal arithmetic exceeded finite f32 range".into(),
            ));
        }
        true_normals.push(true_normal);
        angles.push(
            (0..points.len())
                .map(|i| {
                    let prev = normalized(
                        sub(points[(i + points.len() - 1) % points.len()], points[i]),
                        false,
                    );
                    let next = normalized(sub(points[(i + 1) % points.len()], points[i]), false);
                    angle(dot(prev, next))
                })
                .collect::<Vec<_>>(),
        );
        output.faces.push(FaceNormals {
            face: face.key.clone(),
            normal: normal.map(f64::from),
            corner_normals: vec![true_normal.map(f64::from); points.len()],
        });
    }
    if smooth.iter().all(|v| !*v) {
        return Ok(output);
    }
    let all_smooth = smooth.iter().all(|v| *v);
    for (vertex, incident) in graph.vertex_faces.iter().enumerate() {
        let mut visited = BTreeSet::new();
        for start in incident {
            if visited.contains(start) || !smooth[*start] {
                continue;
            }
            let mut fan = Vec::new();
            let mut stack = vec![*start];
            while let Some(fi) = stack.pop() {
                if !visited.insert(fi) {
                    continue;
                }
                fan.push(fi);
                if all_smooth {
                    fan = incident.clone();
                    visited.extend(incident.iter().copied());
                    break;
                }
                for ei in &graph.faces[fi].edges {
                    let edge = &graph.edges[*ei];
                    if !edge.vertices.contains(&vertex) || edge.faces.len() != 2 {
                        continue;
                    }
                    let [(a, wa), (b, wb)] = edge.faces[..] else {
                        unreachable!("two incident faces")
                    };
                    if wa == wb || !smooth[a] || !smooth[b] {
                        continue;
                    }
                    stack.push(if fi == a { b } else { a });
                }
            }
            fan.sort_unstable();
            let normal = if !all_smooth && fan.len() == 1 {
                true_normals[fan[0]]
            } else {
                let mut sum = [0.; 3];
                for fi in &fan {
                    let corner = graph.faces[*fi]
                        .vertices
                        .iter()
                        .position(|v| *v == vertex)
                        .expect("incident face contains vertex");
                    for (j, value) in sum.iter_mut().enumerate() {
                        *value += true_normals[*fi][j] * angles[*fi][corner];
                    }
                }
                normalized(sum, false)
            };
            for fi in fan {
                let corner = graph.faces[fi]
                    .vertices
                    .iter()
                    .position(|v| *v == vertex)
                    .expect("incident face contains vertex");
                output.faces[fi].corner_normals[corner] = normal.map(f64::from);
            }
        }
    }
    if output.faces.iter().any(|f| {
        f.normal
            .iter()
            .chain(f.corner_normals.iter().flatten())
            .any(|v| !v.is_finite())
    }) {
        return Err(SceneError(
            "automatic normal arithmetic exceeded finite f32 range".into(),
        ));
    }
    Ok(output)
}

/// Resolve exactly the stored-corner, stored-face, automatic precedence used by preview.
pub fn resolved(asset: &MeshAsset) -> Result<MeshNormals> {
    let mut output = automatic(asset)?;
    for face in &mut output.faces {
        match &face.face {
            FaceRef::Polygon(id) => {
                let polygon = &asset.polygons[id];
                if let Some(normal) = polygon.normal {
                    face.normal = normal;
                    face.corner_normals.fill(normal);
                }
                if let Some(corners) = &polygon.corner_normals {
                    face.corner_normals.clone_from(corners);
                }
            }
            FaceRef::Triangle(id) => {
                if let Some(corners) = asset.triangles[id].corner_normals {
                    face.corner_normals = corners.to_vec();
                }
            }
        }
    }
    Ok(output)
}

/// Replace only geometry-dependent normals after a successful geometry edit.
pub fn apply_automatic(asset: &mut MeshAsset) -> Result<()> {
    for face in automatic(asset)?.faces {
        match face.face {
            FaceRef::Polygon(id) => {
                let p = asset.polygons.get_mut(&id).expect("calculated polygon");
                p.normal = Some(face.normal);
                p.corner_normals = Some(face.corner_normals);
            }
            FaceRef::Triangle(id) => {
                asset
                    .triangles
                    .get_mut(&id)
                    .expect("calculated triangle")
                    .corner_normals = Some(
                    face.corner_normals
                        .try_into()
                        .expect("three triangle corners"),
                )
            }
        }
    }
    Ok(())
}

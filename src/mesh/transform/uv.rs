// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! Original-face interpolation and per-layer contiguous UV fans.
use super::{Request, Vector, context::Context, dot, mirror::Plan, normal_orientation, sub};
use crate::mesh::{MeshAsset, selection::FaceRef};
use crate::scene::{Result, SceneError};
use std::collections::{BTreeMap, BTreeSet};
mod math;
type Uv = [f32; 2];
type Layers = BTreeMap<String, Vec<Uv>>;

struct Face {
    points: Vec<Vector>,
    projection: [Vector; 2],
    projected: Vec<Uv>,
    layers: Layers,
}
struct Group {
    layer: String,
    corners: Vec<(usize, usize)>,
    weights: Vec<f32>,
}
fn spend(work: &mut usize, count: usize) -> Result<()> {
    *work = work
        .checked_sub(count)
        .ok_or_else(|| SceneError("mesh UV correction exceeded its work budget".into()))?;
    Ok(())
}
fn interpolate(face: &Face, point: Vector, work: &mut usize) -> Result<BTreeMap<String, Uv>> {
    spend(work, face.points.len())?;
    let weights = math::weights(&face.projected, math::project(point, face.projection));
    let mut result = BTreeMap::new();
    for (name, values) in &face.layers {
        spend(work, values.len())?;
        let mut uv = [0.; 2];
        for (value, weight) in values.iter().zip(&weights) {
            for i in 0..2 {
                uv[i] += value[i] * weight;
            }
        }
        if !uv.iter().all(|v| v.is_finite()) {
            return Err(SceneError(
                "mesh UV correction exceeded finite f32 range".into(),
            ));
        }
        result.insert(name.clone(), uv);
    }
    Ok(result)
}
fn next_radial(context: &Context, face: usize, edge: usize) -> usize {
    let faces = &context.graph.edges[edge].faces;
    let index = faces.iter().position(|(f, _)| *f == face).unwrap();
    faces[(index + 1) % faces.len()].0
}
fn groups(
    context: &Context,
    vertex: usize,
    original: &[Layers],
    work: &mut usize,
) -> Result<Vec<Group>> {
    let graph = &context.graph;
    let corners: Vec<_> = graph.vertex_faces[vertex]
        .iter()
        .map(|fi| {
            (
                *fi,
                graph.faces[*fi]
                    .vertices
                    .iter()
                    .position(|v| *v == vertex)
                    .unwrap(),
            )
        })
        .collect();
    let layers: BTreeSet<_> = corners
        .iter()
        .flat_map(|(fi, _)| original[*fi].keys().cloned())
        .collect();
    let mut groups = Vec::new();
    for layer in layers {
        let mut visited = BTreeSet::new();
        for &(start, corner) in &corners {
            let Some(values) = original[start].get(&layer) else {
                continue;
            };
            if visited.contains(&start) {
                continue;
            }
            let reference = values[corner];
            let mut pending = vec![start];
            let mut members = Vec::new();
            while let Some(fi) = pending.pop() {
                spend(work, 1)?;
                if !visited.insert(fi) {
                    continue;
                }
                let face = &graph.faces[fi];
                let c = face.vertices.iter().position(|v| *v == vertex).unwrap();
                members.push((fi, c));
                for edge in [
                    face.edges[c],
                    face.edges[(c + face.edges.len() - 1) % face.edges.len()],
                ] {
                    let other = next_radial(context, fi, edge);
                    if other == fi || visited.contains(&other) {
                        continue;
                    }
                    let Some(values) = original[other].get(&layer) else {
                        continue;
                    };
                    let c = graph.faces[other]
                        .vertices
                        .iter()
                        .position(|v| *v == vertex)
                        .unwrap();
                    let delta = [reference[0] - values[c][0], reference[1] - values[c][1]];
                    if delta[0] * delta[0] + delta[1] * delta[1] < 0.00001 {
                        pending.push(other);
                    }
                }
            }
            let mut weights: Vec<_> = members
                .iter()
                .map(|(fi, c)| {
                    spend(work, graph.faces[*fi].vertices.len())?;
                    let points: Vec<_> = graph.faces[*fi]
                        .vertices
                        .iter()
                        .map(|v| context.positions[*v])
                        .collect();
                    Ok(math::corner_angle(&points, *c))
                })
                .collect::<Result<_>>()?;
            let total: f32 = weights.iter().sum();
            let inverse = if total != 0. {
                1. / total
            } else {
                1. / weights.len() as f32
            };
            for w in &mut weights {
                *w = if total != 0. { *w * inverse } else { inverse };
            }
            groups.push(Group {
                layer: layer.clone(),
                corners: members,
                weights,
            });
        }
    }
    Ok(groups)
}

pub(super) fn apply(
    context: &Context,
    request: &Request,
    mirror: &Plan,
    before: &MeshAsset,
    next: &mut MeshAsset,
) -> Result<BTreeSet<FaceRef>> {
    if !request.correct_face_attributes {
        return Ok(BTreeSet::new());
    }
    let graph = &context.graph;
    let has_uv = before.polygons.values().any(|p| !p.uv_layers.is_empty())
        || before.triangles.values().any(|p| !p.uv_layers.is_empty());
    if !has_uv {
        return Ok(BTreeSet::new());
    }
    let mut work = request.max_components.saturating_mul(64);
    let active: Vec<_> = (0..context.positions.len())
        .map(|i| {
            context.visible[i]
                && (context.selected[i]
                    || request.proportional.is_some()
                    || mirror.sources[i].is_some())
        })
        .collect();
    let (face_normals, vertex_normals) = normal_orientation::normals(graph, &context.positions)?;
    let mut faces = Vec::new();
    for (fi, face) in graph.faces.iter().enumerate() {
        let points: Vec<_> = face
            .vertices
            .iter()
            .map(|v| context.positions[*v])
            .collect();
        let tangent = if face_normals[fi] == [0.; 3] {
            normal_orientation::tangent_pair(&points, true)?[0]
        } else {
            [0.; 3]
        };
        let projection = math::projection_axis(face_normals[fi], tangent);
        let layers: Layers = match &face.key {
            FaceRef::Polygon(id) => before.polygons[id]
                .uv_layers
                .iter()
                .map(|(n, v)| (n.clone(), v.iter().map(|uv| uv.map(|x| x as f32)).collect()))
                .collect(),
            FaceRef::Triangle(id) => before.triangles[id]
                .uv_layers
                .iter()
                .map(|(n, v)| (n.clone(), v.iter().map(|uv| uv.map(|x| x as f32)).collect()))
                .collect(),
        };
        if layers.values().flatten().flatten().any(|v| !v.is_finite()) {
            return Err(SceneError(
                "mesh UV correction requires finite f32 UV values".into(),
            ));
        }
        let projected = points
            .iter()
            .map(|p| math::project(*p, projection))
            .collect();
        faces.push(Face {
            points,
            projection,
            projected,
            layers,
        });
    }
    let mut references: Vec<_> = (0..faces.len()).collect();
    let mut values: Vec<_> = faces.iter().map(|f| f.layers.clone()).collect();
    let mut touched: BTreeSet<(usize, usize)> = BTreeSet::new();
    for (fi, face) in graph.faces.iter().enumerate() {
        if face_normals[fi] != [0.; 3] || !face.vertices.iter().any(|v| active[*v]) {
            continue;
        }
        let mut best = None;
        for (corner, edge) in face.edges.iter().enumerate() {
            let other = next_radial(context, fi, *edge);
            if other == fi || face_normals[other] == [0.; 3] {
                continue;
            }
            if !context.selected[face.vertices[corner]]
                && !context.selected[face.vertices[(corner + 1) % face.vertices.len()]]
            {
                best = Some(other);
                break;
            }
            if best.is_none() {
                best = Some(other);
            }
        }
        if let Some(other) = best {
            references[fi] = other;
            for (corner, point) in faces[fi].points.iter().enumerate() {
                let interpolated = interpolate(&faces[other], *point, &mut work)?;
                for (layer, uv) in interpolated {
                    if let Some(values) = values[fi].get_mut(&layer) {
                        values[corner] = uv;
                    }
                }
                touched.insert((fi, corner));
            }
        }
    }
    let initial = values.clone();
    let groups: Vec<_> = (0..active.len())
        .map(|v| {
            if active[v] && request.keep_connected {
                groups(context, v, &initial, &mut work)
            } else {
                Ok(Vec::new())
            }
        })
        .collect::<Result<_>>()?;
    for (vertex, is_active) in active.iter().enumerate() {
        if !*is_active {
            continue;
        }
        let position = next.vertices[&graph.vertex_ids[vertex]].map(|v| v as f32);
        for &fi in &graph.vertex_faces[vertex] {
            let corner = graph.faces[fi]
                .vertices
                .iter()
                .position(|v| *v == vertex)
                .unwrap();
            for (layer, uv) in interpolate(&faces[references[fi]], position, &mut work)? {
                if let Some(values) = values[fi].get_mut(&layer) {
                    values[corner] = uv;
                }
            }
            touched.insert((fi, corner));
        }
        let delta = sub(position, context.positions[vertex]);
        let moved = dot(delta, delta) > f32::EPSILON;
        for group in &groups[vertex] {
            spend(&mut work, group.corners.len())?;
            let mut weights = group.weights.clone();
            if moved {
                for ((fi, corner), weight) in group.corners.iter().zip(&mut weights) {
                    spend(&mut work, graph.faces[*fi].vertices.len())?;
                    let points: Vec<_> = graph.faces[*fi]
                        .vertices
                        .iter()
                        .map(|v| {
                            if active[*v] {
                                context.positions[*v]
                            } else {
                                next.vertices[&graph.vertex_ids[*v]].map(|x| x as f32)
                            }
                        })
                        .collect();
                    *weight *=
                        math::moved_weight(&points, *corner, position, vertex_normals[vertex]);
                }
                let total: f32 = weights.iter().sum();
                if total != 0. {
                    let inverse = 1. / total;
                    for w in &mut weights {
                        *w *= inverse;
                    }
                } else {
                    weights.clone_from(&group.weights);
                }
            }
            let mut uv = [0.; 2];
            for ((fi, corner), weight) in group.corners.iter().zip(weights) {
                let value = values[*fi][&group.layer][*corner];
                for i in 0..2 {
                    uv[i] += value[i] * weight;
                }
            }
            if uv.iter().any(|v| !v.is_finite()) {
                return Err(SceneError(
                    "mesh UV group merge exceeded finite f32 range".into(),
                ));
            }
            for (fi, corner) in &group.corners {
                values[*fi].get_mut(&group.layer).unwrap()[*corner] = uv;
            }
        }
    }
    let mut changed = BTreeSet::new();
    for (fi, corner) in touched {
        let face = &graph.faces[fi];
        match &face.key {
            FaceRef::Polygon(id) => {
                let target = &mut next.polygons.get_mut(id).unwrap().uv_layers;
                for (layer, uvs) in &values[fi] {
                    target.get_mut(layer).unwrap()[corner] = uvs[corner].map(f64::from);
                }
                if *target != before.polygons[id].uv_layers {
                    changed.insert(face.key.clone());
                }
            }
            FaceRef::Triangle(id) => {
                let target = &mut next.triangles.get_mut(id).unwrap().uv_layers;
                for (layer, uvs) in &values[fi] {
                    target.get_mut(layer).unwrap()[corner] = uvs[corner].map(f64::from);
                }
                if *target != before.triangles[id].uv_layers {
                    changed.insert(face.key.clone());
                }
            }
        }
    }
    Ok(changed)
}

// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
//! Geometric edit orientation. Shading payloads never supply these normals.
use super::{IDENTITY, Matrix, Pivot, Vector, add, dot, math, sub};
use crate::mesh::{
    MeshAsset,
    selection::{Component, Editing, Graph},
};
use crate::scene::{Result, SceneError};
use std::collections::BTreeMap;

fn checked(v: Vector) -> Result<Vector> {
    if v.iter().all(|v| v.is_finite()) {
        Ok(v)
    } else {
        Err(SceneError(
            "normal orientation arithmetic exceeded finite f32 range".into(),
        ))
    }
}
fn squared(v: Vector) -> Result<f32> {
    let d = dot(v, v);
    if d.is_finite() {
        Ok(d)
    } else {
        Err(SceneError(
            "normal orientation arithmetic exceeded finite f32 range".into(),
        ))
    }
}
fn unit_length(v: Vector) -> Result<(Vector, f32)> {
    let d = squared(v)?;
    if d > 1e-35 {
        let length = d.sqrt();
        Ok((checked(v.map(|v| v * (1. / length)))?, length))
    } else {
        Ok(([0.; 3], 0.))
    }
}
fn unit(v: Vector) -> Result<Vector> {
    Ok(unit_length(v)?.0)
}
fn cross(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[(i + 1) % 3] * b[(i + 2) % 3] - a[(i + 2) % 3] * b[(i + 1) % 3])
}
fn project(v: Vector, direction: Vector) -> Result<Vector> {
    if direction == [0.; 3] {
        return Ok([0.; 3]);
    }
    let factor = dot(v, direction) / squared(direction)?;
    checked(direction.map(|v| v * factor))
}
fn ortho(v: Vector) -> Vector {
    let a = v.map(f32::abs);
    // axis_dominant_v3_single: ties choose the later axis.
    let axis = if a[0] > a[1] {
        if a[0] > a[2] { 0 } else { 2 }
    } else if a[1] > a[2] {
        1
    } else {
        2
    };
    match axis {
        0 => [-v[1] - v[2], v[0], v[0]],
        1 => [v[1], -v[0] - v[2], v[1]],
        _ => [v[2], v[2], -v[0] - v[1]],
    }
}
fn angle(x: f32) -> f32 {
    let f = x.abs();
    let m = if f < 1. { 1. - (1. - f) } else { 1. };
    let a = (1. - m).sqrt()
        * (std::f32::consts::FRAC_PI_2
            + m * (-0.213_300_99 + m * (0.077_980_48 + m * -0.021_640_95)));
    if x < 0. { std::f32::consts::PI - a } else { a }
}
fn face_normal(p: &[Vector]) -> Result<Vector> {
    let normal = match p.len() {
        3 => cross(sub(p[0], p[1]), sub(p[1], p[2])),
        4 => cross(sub(p[0], p[2]), sub(p[1], p[3])),
        _ => {
            let mut n = [0.; 3];
            for (i, b) in p.iter().enumerate() {
                let a = p[(i + p.len() - 1) % p.len()];
                for j in 0..3 {
                    n[j] += (a[(j + 1) % 3] - b[(j + 1) % 3]) * (a[(j + 2) % 3] + b[(j + 2) % 3]);
                }
                checked(n)?;
            }
            n
        }
    };
    unit(normal)
}
pub(super) fn normals(graph: &Graph, p: &[Vector]) -> Result<(Vec<Vector>, Vec<Vector>)> {
    let faces: Vec<_> = graph
        .faces
        .iter()
        .map(|f| face_normal(&f.vertices.iter().map(|v| p[*v]).collect::<Vec<_>>()))
        .collect::<Result<_>>()?;
    let mut vertices = vec![[0.; 3]; p.len()];
    let mut outgoing = vec![Vec::new(); graph.edges.len()];
    for (fi, face) in graph.faces.iter().enumerate() {
        for (corner, ei) in face.edges.iter().enumerate() {
            outgoing[*ei].push((fi, corner));
        }
    }
    for (v, edges) in graph.vertex_edges.iter().enumerate() {
        let mut sum = [0.; 3];
        // Each outgoing loop contributes once. Edge order matches the stable topology.
        for ei in edges {
            for &(fi, i) in &outgoing[*ei] {
                let f = &graph.faces[fi];
                if f.vertices[i] == v {
                    let prev = unit(sub(
                        p[f.vertices[(i + f.vertices.len() - 1) % f.vertices.len()]],
                        p[v],
                    ))?;
                    let next = unit(sub(p[f.vertices[(i + 1) % f.vertices.len()]], p[v]))?;
                    let weight = angle(dot(prev, next));
                    sum = checked(add(sum, faces[fi].map(|x| x * weight)))?;
                }
            }
        }
        vertices[v] = unit(sum)?;
        if vertices[v] == [0.; 3] {
            vertices[v] = unit(p[v])?;
        }
    }
    Ok((faces, vertices))
}
fn unique_triangle_edge(p: &[Vector]) -> Result<usize> {
    let mut difs = [0.; 3];
    for (i, diff) in difs.iter_mut().enumerate() {
        let a = p[(i + 1) % 3];
        let b = p[i];
        let co = p[(i + 2) % 3];
        let direction = sub(add(a, b).map(|v| v * 0.5), co);
        *diff = squared(sub(project(a, direction)?, project(b, direction)?))?;
    }
    // Preserve axis_sort_v3's tie order.
    let mut order = [0, 1, 2];
    if difs[0] < difs[1] {
        if difs[2] < difs[0] {
            order.swap(0, 2);
            difs.swap(0, 2);
        }
    } else if difs[1] < difs[2] {
        order.swap(0, 1);
        difs.swap(0, 1);
    } else {
        order.swap(0, 2);
        difs.swap(0, 2);
    }
    Ok(order[0])
}
pub(super) fn tangent_pair(p: &[Vector], active: bool) -> Result<[Vector; 2]> {
    if p.len() == 4 {
        let a = add(sub(p[3], p[2]), sub(p[0], p[1]));
        let b = add(sub(p[0], p[3]), sub(p[1], p[2]));
        if active {
            return Ok([
                unit(if squared(a)? < squared(b)? { b } else { a })?,
                [0.; 3],
            ]);
        }
        let (a, la) = unit_length(a)?;
        let (b, lb) = unit_length(b)?;
        return Ok(if la < lb { [b, a] } else { [a, b] });
    }
    let i = if p.len() == 3 {
        unique_triangle_edge(p)?
    } else {
        let mut longest = 0;
        let mut length = 0.;
        for j in 0..p.len() {
            let d = squared(sub(p[j], p[(j + 1) % p.len()]))?;
            if d >= length {
                longest = j;
                length = d;
            }
        }
        longest
    };
    let a = unit(sub(p[i], p[(i + 1) % p.len()]))?;
    if active {
        return Ok([a, [0.; 3]]);
    }
    let prev = sub(p[(i + p.len() - 1) % p.len()], p[i]);
    let next = sub(p[(i + 1) % p.len()], p[(i + 2) % p.len()]);
    let b = if squared(cross(a, next))? > squared(cross(a, prev))? {
        next
    } else {
        prev
    };
    Ok([a, unit(b)?])
}
struct Geometry<'a> {
    asset: &'a MeshAsset,
    graph: &'a Graph,
    p: &'a [Vector],
    face_normals: Vec<Vector>,
    vertex_normals: Vec<Vector>,
}
impl Geometry<'_> {
    fn endpoints(&self, ei: usize) -> [usize; 2] {
        let edge = &self.graph.edges[ei];
        self.asset
            .edges
            .get(&edge.id)
            .map(|p| p.each_ref().map(|id| self.graph.vertex_index[id]))
            .unwrap_or(edge.vertices)
    }
    fn boundary(&self, ei: usize) -> Option<[usize; 2]> {
        let edge = &self.graph.edges[ei];
        if let [(_, forward)] = edge.faces[..] {
            let [a, b] = edge.vertices;
            Some(if forward { [a, b] } else { [b, a] })
        } else {
            None
        }
    }
    fn face_tangents(&self, fi: usize, active: bool) -> Result<[Vector; 2]> {
        tangent_pair(
            &self.graph.faces[fi]
                .vertices
                .iter()
                .map(|v| self.p[*v])
                .collect::<Vec<_>>(),
            active,
        )
    }
    fn active(&self, component: &Component) -> Result<(Vector, Vector, bool)> {
        Ok(match component {
            Component::Vertex { id } => {
                let n = self.vertex_normals[self.graph.vertex_index[id]];
                // ORIENTATION_VERT ignores the temporary record's fake plane.
                (n, [0.; 3], false)
            }
            Component::Edge { id } => {
                let ei = self.graph.edge_index[id];
                let [a, b] = self.endpoints(ei);
                let plane = sub(self.p[b], self.p[a]);
                let normal = unit(cross(
                    plane,
                    cross(add(self.vertex_normals[a], self.vertex_normals[b]), plane),
                ))?;
                let plane = if let Some([a, b]) = self.boundary(ei) {
                    sub(self.p[a], self.p[b])
                } else if self.p[b][1] > self.p[a][1] {
                    plane
                } else {
                    plane.map(|v| -v)
                };
                (normal, unit(plane)?, true)
            }
            Component::Face { face } => {
                let fi = self.graph.face_index[face];
                (
                    self.face_normals[fi],
                    self.face_tangents(fi, true)?[0],
                    false,
                )
            }
        })
    }
    fn vertices_from_history(&self, editing: &Editing, selected: &[bool], n: usize) -> Vec<usize> {
        let mut result = Vec::new();
        for component in editing.history.iter().rev() {
            if let Component::Vertex { id } = component {
                let v = self.graph.vertex_index[id];
                if selected[v] {
                    result.push(v);
                } else {
                    break;
                }
            } else {
                break;
            }
            if result.len() == n {
                return result;
            }
        }
        selected
            .iter()
            .enumerate()
            .filter(|(_, s)| **s)
            .map(|(i, _)| i)
            .take(n)
            .collect()
    }
}
fn tangent_space(z: Vector, plane: Vector) -> Result<Option<Matrix>> {
    if z == [0.; 3] {
        return Ok(None);
    }
    let tangent = if plane == [0.; 3] {
        [0., 0., 1.]
    } else {
        plane.map(|v| -v)
    };
    let x = unit(cross(z, tangent))?;
    if x == [0.; 3] {
        return Ok(None);
    }
    let y = unit(cross(z, x))?;
    if y == [0.; 3] {
        return Ok(None);
    }
    Ok(Some(std::array::from_fn(|r| [x[r], y[r], z[r]])))
}
fn space(normal: Vector, plane: Vector, use_plane: bool) -> Result<Matrix> {
    if use_plane && plane != [0.; 3] {
        return Ok(tangent_space(normal, plane)?.unwrap_or(IDENTITY));
    }
    let z = unit(normal)?;
    if z == [0.; 3] {
        return Ok(IDENTITY);
    }
    let x = cross(z, [0., 0., 1.]);
    let x = if x == [0.; 3] {
        cross([1., 0., 0.], z)
    } else {
        x
    };
    let y = cross(z, x);
    let (x, y, z) = (unit(x)?, unit(y)?, unit(z)?);
    Ok(std::array::from_fn(|r| [x[r], y[r], z[r]]))
}

fn dominant(normal: Vector) -> Result<Matrix> {
    if normal == [0.; 3] {
        return Ok(IDENTITY);
    }
    let f = normal[0] * normal[0] + normal[1] * normal[1];
    let (x, y) = if f > f32::EPSILON {
        let d = 1. / f.sqrt();
        let x = [normal[1] * d, -normal[0] * d, 0.];
        let y = [
            -normal[2] * x[1],
            normal[2] * x[0],
            normal[0] * x[1] - normal[1] * x[0],
        ];
        (x, y)
    } else {
        (
            [if normal[2] < 0. { -1. } else { 1. }, 0., 0.],
            [0., 1., 0.],
        )
    };
    math::inverse([x, y, normal])
}

pub(super) fn individual(
    asset: &MeshAsset,
    graph: &Graph,
    p: &[Vector],
    selected: &[bool],
    roots: &[usize],
    member: &[bool],
) -> Result<Vec<Matrix>> {
    let editing = asset.editing.as_ref().expect("validated editing state");
    let (face_normals, vertex_normals) = normals(graph, p)?;
    let g = Geometry {
        asset,
        graph,
        p,
        face_normals,
        vertex_normals,
    };
    let mut groups: BTreeMap<usize, (Vector, Vector)> = BTreeMap::new();
    let components: Vec<_> = if editing.mode.iter().any(|d| {
        matches!(
            d,
            crate::mesh::selection::Domain::Vertex | crate::mesh::selection::Domain::Edge
        )
    }) {
        graph
            .edges
            .iter()
            .filter(|e| {
                editing.selected.edges.contains(&e.id) && e.vertices.iter().all(|v| selected[*v])
            })
            .map(|e| (roots[e.vertices[0]], Component::Edge { id: e.id.clone() }))
            .collect()
    } else {
        graph
            .faces
            .iter()
            .filter(|f| {
                editing.selected.faces.contains(&f.key) && f.vertices.iter().all(|v| selected[*v])
            })
            .map(|f| {
                (
                    roots[f.vertices[0]],
                    Component::Face {
                        face: f.key.clone(),
                    },
                )
            })
            .collect()
    };
    for (root, component) in components {
        let (normal, tangent, _) = g.active(&component)?;
        let pair = groups.entry(root).or_insert(([0.; 3], [0.; 3]));
        pair.0 = checked(add(pair.0, normal))?;
        pair.1 = checked(add(pair.1, tangent))?;
    }
    let groups: BTreeMap<_, _> = groups
        .into_iter()
        .map(|(root, (normal, tangent))| {
            let normal = unit(normal)?;
            let tangent = unit(tangent)?;
            // Island fallback differs from ED_getTransformOrientationMatrix.
            let basis = if normal == [0.; 3] {
                IDENTITY
            } else {
                match tangent_space(normal, tangent)? {
                    Some(basis) => basis,
                    None => dominant(normal)?,
                }
            };
            Ok((root, basis))
        })
        .collect::<Result<_>>()?;
    p.iter()
        .enumerate()
        .map(|(v, _)| {
            if let Some(basis) = groups.get(&roots[v]) {
                Ok(*basis)
            } else if member[v] {
                dominant(g.vertex_normals[v])
            } else {
                space(g.vertex_normals[v], [0.; 3], false)
            }
        })
        .collect()
}

#[allow(clippy::too_many_arguments)]
pub(super) fn basis(
    asset: &MeshAsset,
    graph: &Graph,
    p: &[Vector],
    selected: &[bool],
    edge_visible: &[bool],
    face_visible: &[bool],
    object: Matrix,
    inverse: Matrix,
    pivot: Pivot,
) -> Result<Matrix> {
    let editing = asset.editing.as_ref().expect("validated editing state");
    let (face_normals, vertex_normals) = normals(graph, p)?;
    let g = Geometry {
        asset,
        graph,
        p,
        face_normals,
        vertex_normals,
    };
    let faces: Vec<_> = graph
        .faces
        .iter()
        .enumerate()
        .filter(|(i, f)| face_visible[*i] && editing.selected.faces.contains(&f.key))
        .map(|(i, _)| i)
        .collect();
    let edges: Vec<_> = graph
        .edges
        .iter()
        .enumerate()
        .filter(|(i, e)| edge_visible[*i] && editing.selected.edges.contains(&e.id))
        .map(|(i, _)| i)
        .collect();
    let vertices: Vec<_> = selected
        .iter()
        .enumerate()
        .filter(|(_, s)| **s)
        .map(|(i, _)| i)
        .collect();
    let active_face = editing
        .active_face
        .as_ref()
        .filter(|f| editing.selected.faces.contains(*f))
        .map(|f| Component::Face { face: f.clone() });
    let active = match editing.history.last() {
        Some(Component::Face { .. }) => active_face.or_else(|| editing.history.last().cloned()),
        Some(component) => Some(component.clone()),
        None => active_face,
    };
    let (mut normal, mut plane, edge) =
        if let Some(component) = active.filter(|_| pivot == Pivot::Active) {
            g.active(&component)?
        } else if !faces.is_empty() {
            let mut normal = [0.; 3];
            let mut pair = [[0.; 3]; 2];
            for fi in &faces {
                normal = checked(add(normal, g.face_normals[*fi]))?;
                let tangents = g.face_tangents(*fi, false)?;
                for i in 0..2 {
                    pair[i] = checked(add(pair[i], tangents[i]))?;
                }
            }
            let index = if faces.len() == 1 {
                0
            } else {
                let n = unit(normal)?;
                if squared(cross(n, unit(pair[0])?))? > squared(cross(n, unit(pair[1])?))? {
                    0
                } else {
                    1
                }
            };
            (normal, pair[index], false)
        } else if vertices.len() == 3 {
            let v = g.vertices_from_history(editing, selected, 3);
            let points: Vec<_> = v.iter().map(|v| p[*v]).collect();
            let mut normal = face_normal(&points)?;
            if dot(
                add(
                    add(g.vertex_normals[v[0]], g.vertex_normals[v[1]]),
                    g.vertex_normals[v[2]],
                ),
                normal,
            ) < 0.
            {
                normal = normal.map(|v| -v);
            }
            let mut longest = None;
            let mut length = 0.;
            for j in 0..3 {
                if let Some(e) = graph.vertex_edges[v[j]].iter().find(|e| {
                    graph.edges[**e].vertices.contains(&v[(j + 1) % 3])
                        && editing.selected.edges.contains(&graph.edges[**e].id)
                }) {
                    let d = squared(sub(p[v[j]], p[v[(j + 1) % 3]]))?;
                    if longest.is_none() || length < d {
                        longest = Some(*e);
                        length = d;
                    }
                }
            }
            let plane = if let Some(e) = longest {
                let [a, b] = g.boundary(e).unwrap_or_else(|| g.endpoints(e));
                sub(p[a], p[b])
            } else {
                let i = unique_triangle_edge(&points)?;
                unit(sub(points[i], points[(i + 1) % 3]))?
            };
            (normal, plane, false)
        } else if edges.len() == 1 || vertices.len() == 2 {
            let mut pair = if edges.len() == 1 {
                g.endpoints(edges[0])
            } else {
                let v = g.vertices_from_history(editing, selected, 2);
                [v[0], v[1]]
            };
            let active_vertex = editing.history.last().and_then(|c| {
                if let Component::Vertex { id } = c {
                    Some(graph.vertex_index[id])
                } else {
                    None
                }
            });
            if active_vertex == Some(pair[1])
                || (edges.len() == 1 && g.boundary(edges[0]).is_some_and(|p| p[0] != pair[0]))
            {
                pair.swap(0, 1);
            }
            let [a, b] = pair;
            let mut normal = add(g.vertex_normals[b], g.vertex_normals[a]);
            let plane = unit(sub(p[b], p[a]))?;
            if plane != [0.; 3] {
                normal = unit(sub(normal, plane.map(|v| v * dot(normal, plane))))?;
                if normal == [0.; 3] {
                    normal = checked(ortho(plane))?;
                }
            }
            (normal, plane, true)
        } else if vertices.len() == 1 {
            let v = vertices[0];
            let normal = g.vertex_normals[v];
            let mut plane = [0.; 3];
            if let [ea, eb] = graph.vertex_edges[v][..] {
                let mut pair = [ea, eb].map(|e| {
                    *graph.edges[e]
                        .vertices
                        .iter()
                        .find(|other| **other != v)
                        .expect("edge endpoint")
                });
                let swap = if let Some(boundary) = g.boundary(ea) {
                    boundary[0] != v
                } else {
                    squared(sub(p[v], p[pair[0]]))? < squared(sub(p[v], p[pair[1]]))?
                };
                if swap {
                    pair.swap(0, 1);
                }
                plane = add(unit(sub(p[v], p[pair[0]]))?, unit(sub(p[pair[1]], p[v]))?);
            }
            (normal, plane, plane != [0.; 3])
        } else {
            let mut normal = [0.; 3];
            for v in vertices {
                normal = checked(add(normal, g.vertex_normals[v]))?;
            }
            (unit(normal)?, [0.; 3], false)
        };
    plane = plane.map(|v| -v);
    if edge {
        normal = checked(math::vector(object, normal))?;
        plane = checked(math::vector(object, plane))?;
        normal = sub(normal, project(normal, plane)?);
    } else {
        let transpose = std::array::from_fn(|i| std::array::from_fn(|j| inverse[j][i]));
        normal = checked(math::vector(transpose, normal))?;
        plane = checked(math::vector(transpose, plane))?;
    }
    space(unit(normal)?, unit(plane)?, true)
}

// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! Pinned surface wave propagation. Unreached vertices keep the finite MAX sentinel.
use super::{Vector, context::Context, dot, math, sub};
use crate::scene::{Result, SceneError};

pub(super) struct Distances {
    pub values: Vec<f32>,
    pub origins: Vec<usize>,
}
fn finite(value: f32) -> Result<f32> {
    if value.is_finite() {
        Ok(value)
    } else {
        Err(SceneError(
            "mesh surface distance arithmetic exceeded finite f32 range".into(),
        ))
    }
}
fn length(v: Vector) -> Result<f32> {
    Ok(finite(dot(v, v))?.sqrt())
}
fn normalized(v: Vector) -> Result<(Vector, f32)> {
    let squared = finite(dot(v, v))?;
    if squared > 1e-35 {
        let d = squared.sqrt();
        let inverse = 1. / d;
        Ok((v.map(|x| x * inverse), d))
    } else {
        Ok(([0.; 3], 0.))
    }
}
fn cross(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[(i + 1) % 3] * b[(i + 2) % 3] - a[(i + 2) % 3] * b[(i + 1) % 3])
}
fn triangle(v0: Vector, v1: Vector, v2: Vector, d1: f32, d2: f32) -> Result<f32> {
    let v10 = sub(v0, v1);
    let v12 = sub(v2, v1);
    if d1 != 0. && d2 != 0. {
        let (u, d12) = normalized(v12)?;
        let d12_squared = finite(d12 * d12)?;
        if d12_squared > 0. {
            let (normal, _) = normalized(cross(v12, v10))?;
            let v = cross(normal, u);
            let point = [finite(dot(v10, u))?, finite(dot(v10, v))?.abs()];
            let a = finite(0.5 * (1. + finite(d1 * d1 - d2 * d2)? / d12_squared))?;
            let hh = finite(d1 * d1 - a * a * d12_squared)?;
            if hh > 0. {
                let h = hh.sqrt();
                let source = [a * d12, -h];
                let intercept = finite(source[0] + h * (point[0] - source[0]) / (point[1] + h))?;
                if (0. ..=d12).contains(&intercept) {
                    let x = source[0] - point[0];
                    let y = source[1] - point[1];
                    let distance = finite(x * x + y * y)?.sqrt();
                    if distance >= d1.min(d2) {
                        return Ok(distance);
                    }
                }
            }
        }
    }
    Ok(finite(d1 + length(v10)?)?.min(finite(d2 + length(sub(v0, v2))?)?))
}
struct Wave<'a> {
    context: &'a Context,
    transformed: Vec<Vector>,
    distance: Distances,
    loose: Vec<bool>,
    queued: Vec<bool>,
    next: Vec<usize>,
    work_left: usize,
}
impl Wave<'_> {
    fn spend(&mut self) -> Result<()> {
        self.work_left = self.work_left.checked_sub(1).ok_or_else(|| {
            SceneError("mesh surface propagation exceeded its work budget".into())
        })?;
        Ok(())
    }
    fn improve(&mut self, dest: usize, source: usize, other: Option<usize>) -> Result<bool> {
        self.spend()?;
        if self.context.selected[dest]
            || !self.context.visible[dest]
            || self.distance.values[source] == f32::MAX
            || self.distance.values[dest] <= self.distance.values[source]
        {
            return Ok(false);
        }
        let distance = if let Some(other) = other {
            if self.distance.values[other] == f32::MAX
                || self.distance.values[dest] <= self.distance.values[other]
            {
                return Ok(false);
            }
            triangle(
                self.transformed[dest],
                self.transformed[source],
                self.transformed[other],
                self.distance.values[source],
                self.distance.values[other],
            )?
        } else {
            let delta = math::vector(
                self.context.object,
                sub(self.context.positions[source], self.context.positions[dest]),
            );
            finite(self.distance.values[source] + length(delta)?)?
        };
        if distance < self.distance.values[dest] {
            self.distance.values[dest] = distance;
            self.distance.origins[dest] = self.distance.origins[source];
            return Ok(true);
        }
        Ok(false)
    }
    fn schedule(&mut self, vertex: usize, exclude: usize, direct: bool) -> Result<()> {
        for edge in &self.context.graph.vertex_edges[vertex] {
            self.spend()?;
            if *edge == exclude || self.queued[*edge] || !self.context.edge_visible[*edge] {
                continue;
            }
            let pair = self.context.graph.edges[*edge].vertices;
            let other = if pair[0] == vertex { pair[1] } else { pair[0] };
            if direct || self.loose[*edge] || self.distance.values[other] != f32::MAX {
                self.queued[*edge] = true;
                self.next.push(*edge);
            }
        }
        Ok(())
    }
    fn edge(&mut self, edge: usize) -> Result<()> {
        self.spend()?;
        let [mut a, mut b] = self.context.graph.edges[edge].vertices;
        if self.loose[edge]
            || self.distance.values[a] == f32::MAX
            || self.distance.values[b] == f32::MAX
        {
            if self.distance.values[a] > self.distance.values[b] {
                std::mem::swap(&mut a, &mut b);
            }
            if self.improve(b, a, None)? {
                self.schedule(
                    b,
                    edge,
                    self.loose[edge] || self.context.selected[a] || self.context.selected[b],
                )?;
            }
        }
        if !self.loose[edge] {
            for (face, _) in &self.context.graph.edges[edge].faces {
                self.spend()?;
                if !self.context.face_visible[*face] {
                    continue;
                }
                let face = &self.context.graph.faces[*face];
                let mut start = None;
                for (i, candidate) in face.edges.iter().enumerate() {
                    self.spend()?;
                    if *candidate == edge {
                        start = Some(i);
                        break;
                    }
                }
                let start = start.expect("incident face edge");
                for offset in 2..face.vertices.len() {
                    let vertex = face.vertices[(start + offset) % face.vertices.len()];
                    if self.improve(vertex, a, Some(b))? {
                        self.schedule(vertex, edge, false)?;
                    }
                }
            }
        }
        Ok(())
    }
}
pub(super) fn calculate(context: &Context, budget: usize) -> Result<Distances> {
    let values = context
        .selected
        .iter()
        .map(|v| if *v { 0. } else { f32::MAX })
        .collect();
    let origins = (0..context.positions.len()).collect();
    let loose = context
        .graph
        .edges
        .iter()
        .map(|edge| {
            edge.faces
                .iter()
                .all(|(face, _)| !context.face_visible[*face])
        })
        .collect();
    let mut queue: Vec<_> = context
        .graph
        .edges
        .iter()
        .enumerate()
        .filter(|(i, e)| {
            context.edge_visible[*i] && e.vertices.iter().any(|v| context.selected[*v])
        })
        .map(|(i, _)| i)
        .collect();
    let transformed = context
        .positions
        .iter()
        .map(|p| math::vector(context.object, *p))
        .collect::<Vec<_>>();
    if transformed.iter().flatten().any(|v| !v.is_finite()) {
        return Err(SceneError(
            "mesh surface frame arithmetic exceeded finite f32 range".into(),
        ));
    }
    let mut wave = Wave {
        context,
        transformed,
        distance: Distances { values, origins },
        loose,
        queued: vec![false; context.graph.edges.len()],
        next: Vec::new(),
        work_left: budget,
    };
    while !queue.is_empty() {
        while let Some(edge) = queue.pop() {
            wave.edge(edge)?;
        }
        for edge in &wave.next {
            wave.queued[*edge] = false;
        }
        std::mem::swap(&mut queue, &mut wave.next);
    }
    Ok(wave.distance)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn work_budget_rejects_propagation_without_changing_context() {
        let mut scene = crate::scene::Scene::default();
        let asset=serde_json::from_value(serde_json::json!({"vertices":{"a":[0,0,0],"b":[1,0,0]},"edges":{"edge":["a","b"]},"triangles":{},"material_slots":[],"editing":{"selected":{"vertices":["a"]}}})).unwrap();
        scene.mesh_assets.insert("mesh".into(), asset);
        scene.entities.insert("target".into(),serde_json::from_value(serde_json::json!({"name":"Target","parent":null,"transform":{"translation":[0,0,0],"rotation":[0,0,0,1],"scale":[1,1,1]},"content":{"kind":"mesh","geometry":{"kind":"asset","id":"mesh"},"material":null}})).unwrap());
        let request=serde_json::from_value(serde_json::json!({"entity":"target","change":{"kind":"translate","value":[0,0,1]},"proportional":{"radius":2,"falloff":"linear","connected":true}})).unwrap();
        let context = Context::new(&scene, &request).unwrap();
        let before = context.positions.clone();
        assert!(
            calculate(&context, 0)
                .err()
                .unwrap()
                .0
                .contains("work budget")
        );
        assert_eq!(context.positions, before);
        assert_eq!(calculate(&context, 100).unwrap().values, vec![0., 1.]);
    }
    #[test]
    fn virtual_source_crosses_triangle_interior_instead_of_walking_both_edges() {
        let d = 2_f32.sqrt();
        let result = triangle([2., 0., 0.], [1., 1., 0.], [1., -1., 0.], d, d).unwrap();
        assert!((result - 2.).abs() < 1e-6);
        assert!(result < 2. * d - 0.5);
        assert_eq!(
            triangle([2., 0., 0.], [1., 1., 0.], [1., -1., 0.], 0., d).unwrap(),
            d
        );
    }
    #[test]
    fn degenerate_triangle_falls_back_and_overflow_is_an_error() {
        assert_eq!(
            triangle([2., 0., 0.], [1., 0., 0.], [1., 0., 0.], 1., 1.).unwrap(),
            2.
        );
        assert!(triangle([1e30, 0., 0.], [0., 0., 0.], [0., 1., 0.], 1., 1.).is_err());
    }
}

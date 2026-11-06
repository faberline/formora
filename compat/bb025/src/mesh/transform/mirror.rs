// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
use super::{Request, Vector, context::Context, dot, sub};
use crate::mesh::MeshAsset;
use crate::scene::{Result, SceneError};
use std::collections::BTreeMap;

const EPSILON: f32 = 0.00002;

struct Search {
    index: usize,
    axis: usize,
    left: Option<Box<Search>>,
    right: Option<Box<Search>>,
}
impl Search {
    fn new(indices: &mut [usize], points: &[Vector], depth: usize) -> Option<Box<Self>> {
        if indices.is_empty() {
            return None;
        }
        let axis = depth % 3;
        let middle = indices.len() / 2;
        indices.select_nth_unstable_by(middle, |a, b| {
            points[*a][axis].total_cmp(&points[*b][axis]).then(a.cmp(b))
        });
        let index = indices[middle];
        let (left, right) = indices.split_at_mut(middle);
        Some(Box::new(Self {
            index,
            axis,
            left: Self::new(left, points, depth + 1),
            right: Self::new(&mut right[1..], points, depth + 1),
        }))
    }
    fn nearest(
        &self,
        points: &[Vector],
        query: Vector,
        best: &mut (f32, Option<usize>),
        work: &mut usize,
    ) -> Result<()> {
        spend(work)?;
        let delta = sub(query, points[self.index]);
        let distance = dot(delta, delta);
        if distance < best.0 || (distance == best.0 && best.1.is_some_and(|i| self.index < i)) {
            *best = (distance, Some(self.index));
        }
        let split = delta[self.axis];
        let (first, second) = if split <= 0. {
            (&self.left, &self.right)
        } else {
            (&self.right, &self.left)
        };
        if let Some(child) = first {
            child.nearest(points, query, best, work)?;
        }
        if split * split <= best.0 {
            if let Some(child) = second {
                child.nearest(points, query, best, work)?;
            }
        }
        Ok(())
    }
}
fn spend(work: &mut usize) -> Result<()> {
    *work = work
        .checked_sub(1)
        .ok_or_else(|| SceneError("mesh transform mirror exceeded its work budget".into()))?;
    Ok(())
}

fn topology(context: &Context, work: &mut usize) -> Result<Vec<Option<usize>>> {
    let graph = &context.graph;
    let mut hashes: Vec<u32> = graph.vertex_edges.iter().map(|e| e.len() as u32).collect();
    let mut previous = hashes.clone();
    let mut pass = 1u32;
    let mut last = None;
    loop {
        let mut different_edges = 0usize;
        for edge in &graph.edges {
            spend(work)?;
            let [a, b] = edge.vertices;
            hashes[a] = hashes[a].wrapping_add(previous[b].wrapping_mul(pass));
            hashes[b] = hashes[b].wrapping_add(previous[a].wrapping_mul(pass));
            different_edges += usize::from(hashes[a] != hashes[b]);
        }
        // The pinned qsort hash comparator orders element addresses. The
        // observed source array remains in its original order, not hash order.
        let transitions = 1 + hashes.windows(2).filter(|p| p[0] != p[1]).count();
        if last.is_some_and(|(a, b)| transitions <= a && different_edges <= b) {
            break;
        }
        spend(work)?;
        last = Some((transitions, different_edges));
        previous.clone_from(&hashes);
        pass = pass.wrapping_add(1);
    }
    let mut groups: BTreeMap<u32, Vec<usize>> = BTreeMap::new();
    for (index, hash) in hashes.into_iter().enumerate() {
        groups.entry(hash).or_default().push(index);
    }
    let mut pairs = vec![None; graph.vertex_ids.len()];
    for group in groups.values() {
        match group.as_slice() {
            [a, b] => {
                pairs[*a] = Some(*b);
                pairs[*b] = Some(*a);
            }
            [a] => pairs[*a] = Some(*a),
            _ => {}
        }
    }
    Ok(pairs)
}

pub(super) struct Plan {
    pub sources: Vec<Option<usize>>,
    pub plane: Vec<usize>,
    axis: usize,
}
impl Plan {
    pub fn new(context: &Context, request: &Request) -> Result<Self> {
        let Some(mirror) = &request.mirror else {
            return Ok(Self {
                sources: vec![None; context.positions.len()],
                plane: Vec::new(),
                axis: 0,
            });
        };
        let axis = mirror.axis.index();
        let mut work = request.max_components.saturating_mul(64);
        let select_only = request.proportional.is_none();
        let indices: Vec<_> = (0..context.positions.len())
            .filter(|i| context.visible[*i])
            .collect();
        let topology = if mirror.topology {
            Some(topology(context, &mut work)?)
        } else {
            None
        };
        let tree = if topology.is_none() {
            Search::new(&mut indices.clone(), &context.positions, 0)
        } else {
            None
        };
        let mut cache = vec![None; context.positions.len()];
        for &i in &indices {
            if select_only && !context.selected[i] {
                continue;
            }
            let candidate = if let Some(topology) = &topology {
                topology[i].filter(|j| context.visible[*j])
            } else {
                let mut query = context.positions[i];
                query[axis] *= -1.;
                let mut best = (EPSILON * EPSILON, None);
                if let Some(tree) = &tree {
                    tree.nearest(&context.positions, query, &mut best, &mut work)?;
                }
                best.1
            };
            if let Some(j) = candidate.filter(|j| *j != i) {
                cache[i] = Some(j);
                cache[j] = Some(i);
            } else {
                cache[i] = None;
            }
        }
        let sum = context
            .positions
            .iter()
            .zip(&context.selected)
            .filter(|(_, selected)| **selected)
            .fold(0f32, |sum, (p, _)| sum + p[axis]);
        if !sum.is_finite() {
            return Err(SceneError(
                "mesh transform mirror selection sum overflow".into(),
            ));
        }
        let sign = if sum >= 0. { 1. } else { -1. };
        let mut sources = vec![None; context.positions.len()];
        for &i in &indices {
            let Some(j) = cache[i] else { continue };
            if (select_only && !context.selected[i])
                || context.positions[i][axis] * sign < -EPSILON
                || sources[j].is_some()
                || sources[i].is_some()
            {
                continue;
            }
            sources[j] = Some(i);
        }
        let plane = indices
            .into_iter()
            .filter(|i| {
                sources[*i].is_none()
                    && (!select_only || context.selected[*i])
                    && context.positions[*i][axis].abs() < EPSILON
            })
            .collect();
        Ok(Self {
            sources,
            plane,
            axis,
        })
    }
    pub fn apply(&self, context: &Context, asset: &mut MeshAsset) {
        for &i in &self.plane {
            asset
                .vertices
                .get_mut(&context.graph.vertex_ids[i])
                .unwrap()[self.axis] = 0.;
        }
        for (destination, source) in self.sources.iter().enumerate() {
            if let Some(source) = source {
                let mut point = asset.vertices[&context.graph.vertex_ids[*source]];
                point[self.axis] *= -1.;
                asset
                    .vertices
                    .insert(context.graph.vertex_ids[destination].clone(), point);
            }
        }
    }
}

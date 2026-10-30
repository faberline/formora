// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
use super::{Cluster, Face, Method};
use crate::mesh::{MeshAsset, selection::Graph, snap};
use crate::scene::{Result, SceneError};
use std::collections::BTreeSet;

fn midpoint(values: impl Iterator<Item = [f32; 2]>) -> Option<[f32; 2]> {
    let mut min = [f32::MAX; 2];
    let mut max = [-f32::MAX; 2];
    let mut found = false;
    for value in values {
        found = true;
        for axis in 0..2 {
            min[axis] = min[axis].min(value[axis]);
            max[axis] = max[axis].max(value[axis]);
        }
    }
    found.then(|| std::array::from_fn(|axis| min[axis] * 0.5 + max[axis] * 0.5))
}

pub(super) fn apply(
    faces: &mut [Face],
    graph: &Graph,
    clusters: &[Cluster],
    method: Method,
    asset: &MeshAsset,
) -> Result<()> {
    let names: BTreeSet<_> = faces
        .iter()
        .flat_map(|face| face.uv.keys().cloned())
        .collect();
    for name in names {
        let loops: Vec<_> = faces
            .iter()
            .enumerate()
            .flat_map(|(fi, face)| (0..face.vertices.len()).map(move |corner| (fi, corner)))
            .collect();
        let mut values = loops
            .iter()
            .map(|(fi, corner)| {
                let p = faces[*fi]
                    .uv
                    .get(&name)
                    .map(|values| values[*corner])
                    .unwrap_or([0.; 2]);
                Ok([snap::finite(p[0])?, snap::finite(p[1])?])
            })
            .collect::<Result<Vec<_>>>()?;
        let vertices: Vec<_> = loops
            .iter()
            .map(|(fi, corner)| graph.vertex_index[&faces[*fi].vertices[*corner]])
            .collect();
        let edges: Vec<_> = loops
            .iter()
            .map(|(fi, corner)| graph.faces[*fi].edges[*corner])
            .collect();
        let mut offsets = Vec::new();
        let mut start = 0;
        for face in faces.iter() {
            offsets.push(start);
            start += face.vertices.len();
        }
        let next: Vec<_> = loops
            .iter()
            .map(|(fi, corner)| offsets[*fi] + (*corner + 1) % faces[*fi].vertices.len())
            .collect();
        let previous: Vec<_> = loops
            .iter()
            .map(|(fi, corner)| {
                offsets[*fi] + (*corner + faces[*fi].vertices.len() - 1) % faces[*fi].vertices.len()
            })
            .collect();
        if method != Method::Collapse {
            let selected: BTreeSet<_> = clusters
                .iter()
                .flat_map(|cluster| cluster.vertices.iter().copied())
                .collect();
            let selected_loops: Vec<_> = (0..loops.len())
                .filter(|i| selected.contains(&vertices[*i]))
                .collect();
            let target = if matches!(method, Method::Center | Method::Cursor) {
                midpoint(selected_loops.iter().map(|i| values[*i]))
            } else {
                let survivor = clusters[0].survivor;
                let target_loops: Vec<_> = (0..loops.len())
                    .filter(|i| vertices[*i] == survivor)
                    .collect();
                if target_loops.is_empty() {
                    None
                } else {
                    let factor = 1_f32 / target_loops.len() as f32;
                    let mut sum = [0_f32; 2];
                    for i in target_loops {
                        for (axis, value) in sum.iter_mut().enumerate() {
                            *value += values[i][axis] * factor;
                        }
                    }
                    Some(sum)
                }
            };
            if let Some(target) = target {
                for i in selected_loops {
                    values[i] = target;
                }
            }
        } else {
            let selected = &asset
                .editing
                .as_ref()
                .expect("collapse selection")
                .selected
                .edges;
            let marked: Vec<_> = graph
                .edges
                .iter()
                .map(|edge| selected.contains(&edge.id))
                .collect();
            let mut vertex_loops = vec![Vec::new(); graph.vertex_ids.len()];
            let mut radial = vec![Vec::new(); graph.edges.len()];
            for i in 0..loops.len() {
                vertex_loops[vertices[i]].push(i);
                radial[edges[i]].push(i);
            }
            let mut visited = vec![false; loops.len()];
            for seed in 0..loops.len() {
                if !marked[edges[seed]] || visited[seed] {
                    continue;
                }
                let mut pending = vec![seed];
                visited[seed] = true;
                let mut island = Vec::new();
                while let Some(current) = pending.pop() {
                    island.push(current);
                    if !marked[edges[current]] {
                        continue;
                    }
                    for pivot in [current, next[current]] {
                        for &first in &vertex_loops[vertices[pivot]] {
                            for &other in &radial[edges[first]] {
                                if visited[other] {
                                    continue;
                                }
                                if vertices[other] != vertices[pivot] && !marked[edges[other]] {
                                    continue;
                                }
                                let sample = if vertices[other] != vertices[pivot] {
                                    next[other]
                                } else {
                                    other
                                };
                                let delta = [
                                    values[pivot][0] - values[sample][0],
                                    values[pivot][1] - values[sample][1],
                                ];
                                if delta[0] * delta[0] + delta[1] * delta[1] >= 0.00001 {
                                    continue;
                                }
                                visited[other] = true;
                                pending.push(other);
                            }
                            let boundary = previous[first];
                            if radial[edges[boundary]].len() == 1
                                && marked[edges[boundary]]
                                && !visited[boundary]
                            {
                                visited[boundary] = true;
                                pending.push(boundary);
                            }
                        }
                    }
                }
                if let Some(target) = midpoint(island.iter().map(|i| values[*i])) {
                    for i in island {
                        values[i] = target;
                    }
                }
            }
        }
        if values.iter().flatten().any(|n| !n.is_finite()) {
            return Err(SceneError("merged UV exceeds finite f32 range".into()));
        }
        for ((fi, corner), value) in loops.into_iter().zip(values) {
            if let Some(values) = faces[fi].uv.get_mut(&name) {
                values[corner] = value.map(f64::from);
            }
        }
    }
    Ok(())
}

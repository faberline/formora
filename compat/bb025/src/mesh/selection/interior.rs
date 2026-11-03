// SPDX-FileCopyrightText: 2004 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
// Interior groups follow the pinned Blender area/angle cost rule.
use super::Graph;
use crate::scene::{Result, SceneError};
use std::cmp::Ordering;
use std::collections::{BTreeSet, BinaryHeap};

#[derive(Clone)]
struct Candidate {
    cost: f64,
    group: usize,
    generation: u64,
}
impl PartialEq for Candidate {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
    }
}
impl Eq for Candidate {}
impl PartialOrd for Candidate {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for Candidate {
    fn cmp(&self, other: &Self) -> Ordering {
        self.cost
            .total_cmp(&other.cost)
            .then_with(|| other.group.cmp(&self.group))
            .then(self.generation.cmp(&other.generation))
    }
}

fn normal_area(points: &[[f64; 3]]) -> ([f64; 3], f64) {
    let mut n = [0.; 3];
    for i in 0..points.len() {
        let a = points[i];
        let b = points[(i + 1) % points.len()];
        for j in 0..3 {
            n[j] += (a[(j + 1) % 3] - b[(j + 1) % 3]) * (a[(j + 2) % 3] + b[(j + 2) % 3]);
        }
    }
    let length = n.iter().map(|v| v * v).sum::<f64>().sqrt();
    (
        if length > 0. {
            n.map(|v| v / length)
        } else {
            [0.; 3]
        },
        length * 0.5,
    )
}

impl Graph {
    pub fn interior_faces(&self) -> Result<Vec<usize>> {
        let mut critical: Vec<_> = self.edges.iter().map(|edge| edge.faces.len() > 2).collect();
        if !critical.iter().any(|on| *on) {
            return Ok(Vec::new());
        }
        let mut owners = vec![None; self.faces.len()];
        let mut groups: Vec<BTreeSet<usize>> = Vec::new();
        for start in 0..self.faces.len() {
            if owners[start].is_some() {
                continue;
            }
            let group = groups.len();
            let mut members = BTreeSet::new();
            let mut pending = vec![start];
            owners[start] = Some(group);
            while let Some(f) = pending.pop() {
                members.insert(f);
                for &e in &self.faces[f].edges {
                    if !critical[e] {
                        for &(neighbor, _) in &self.edges[e].faces {
                            if owners[neighbor].is_none() {
                                owners[neighbor] = Some(group);
                                pending.push(neighbor);
                            }
                        }
                    }
                }
            }
            groups.push(members);
        }
        let geometry: Vec<_> = self
            .faces
            .iter()
            .map(|face| {
                normal_area(
                    &face
                        .vertices
                        .iter()
                        .map(|v| self.positions[*v])
                        .collect::<Vec<_>>(),
                )
            })
            .collect();
        let lengths: Vec<_> = self
            .edges
            .iter()
            .map(|edge| {
                let [a, b] = edge.vertices;
                self.positions[a]
                    .iter()
                    .zip(self.positions[b])
                    .map(|(a, b)| (a - b) * (a - b))
                    .sum::<f64>()
                    .sqrt()
            })
            .collect();
        let mut generations = vec![0u64; groups.len()];
        let mut heap = BinaryHeap::new();
        let cost = |group: usize,
                    groups: &[BTreeSet<usize>],
                    owners: &[Option<usize>],
                    critical: &[bool]|
         -> Result<Option<f64>> {
            let mut area = 0.;
            let mut score = 0.;
            let mut eligible = false;
            for &f in &groups[group] {
                area += geometry[f].1;
                for &e in &self.faces[f].edges {
                    if !critical[e] {
                        continue;
                    }
                    let mut count = 0;
                    let mut edge_cost = 0.;
                    for &(neighbor, _) in &self.edges[e].faces {
                        if owners[neighbor].is_none() || owners[neighbor] == Some(group) {
                            continue;
                        }
                        let dot = geometry[f]
                            .0
                            .iter()
                            .zip(geometry[neighbor].0)
                            .map(|(a, b)| a * b)
                            .sum::<f64>()
                            .abs()
                            .clamp(0., 1.);
                        edge_cost += lengths[e] * dot.acos();
                        count += 1;
                    }
                    if count >= 2 {
                        eligible = true;
                        score += edge_cost;
                    }
                }
            }
            if !eligible {
                return Ok(None);
            }
            let score = score / area;
            if !score.is_finite() {
                return Err(SceneError(
                    "undefined_interior_cost: degenerate non-manifold face group".into(),
                ));
            }
            Ok(Some(score))
        };
        for group in 0..groups.len() {
            if let Some(cost) = cost(group, &groups, &owners, &critical)? {
                heap.push(Candidate {
                    cost,
                    group,
                    generation: 0,
                });
            }
        }
        let mut selected = Vec::new();
        while let Some(candidate) = heap.pop() {
            let group = candidate.group;
            if generations[group] != candidate.generation || groups[group].is_empty() {
                continue;
            }
            let removed = std::mem::take(&mut groups[group]);
            let mut touched = BTreeSet::new();
            for &face in &removed {
                owners[face] = None;
                selected.push(face);
                touched.extend(self.faces[face].edges.iter().copied());
            }
            let mut affected = BTreeSet::new();
            for &edge in &touched {
                let remaining: Vec<_> = self.edges[edge]
                    .faces
                    .iter()
                    .filter_map(|(f, _)| owners[*f])
                    .collect();
                affected.extend(remaining.iter().copied());
                if remaining.len() == 2 {
                    critical[edge] = false;
                    let a = remaining[0].min(remaining[1]);
                    let b = remaining[0].max(remaining[1]);
                    if a != b {
                        let moved = std::mem::take(&mut groups[b]);
                        for &face in &moved {
                            owners[face] = Some(a);
                        }
                        groups[a].extend(moved);
                        generations[b] += 1;
                        affected.insert(a);
                    }
                }
            }
            // A group can merge again while another touched edge is processed.
            let mut current = BTreeSet::new();
            for edge in touched {
                for &(face, _) in &self.edges[edge].faces {
                    if let Some(group) = owners[face] {
                        current.insert(group);
                    }
                }
            }
            current.extend(affected.into_iter().filter(|g| !groups[*g].is_empty()));
            for group in current {
                generations[group] += 1;
                if let Some(cost) = cost(group, &groups, &owners, &critical)? {
                    heap.push(Candidate {
                        cost,
                        group,
                        generation: generations[group],
                    });
                }
            }
        }
        Ok(selected)
    }
}

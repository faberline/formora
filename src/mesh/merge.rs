// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
//! Persistent vertex merge from the selected topology, without reference data.
use super::{
    MeshAsset, frame_math,
    selection::{Component, Domain, Elements, FaceRef, Graph},
    snap,
};
use crate::scene::{EntityKind, Geometry, Result, Scene, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, VecDeque};

mod weld;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Method {
    Center,
    Cursor,
    Collapse,
    First,
    Last,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub entity: String,
    pub method: Method,
    #[serde(default)]
    pub uvs: bool,
    #[serde(default = "super::primitives::default_budget")]
    pub max_components: usize,
}

#[derive(Debug, Clone, Copy, Serialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Finished,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct Counts {
    pub vertices: usize,
    pub edges: usize,
    pub faces: usize,
    pub corners: usize,
}
impl Counts {
    fn of(graph: &Graph) -> Result<Self> {
        let corners = graph
            .faces
            .iter()
            .try_fold(0usize, |sum, face| sum.checked_add(face.vertices.len()))
            .ok_or_else(|| SceneError("merge corner count overflow".into()))?;
        Ok(Self {
            vertices: graph.vertex_ids.len(),
            edges: graph.edges.len(),
            faces: graph.faces.len(),
            corners,
        })
    }
    fn budget(&self, limit: usize) -> Result<()> {
        let count = self
            .vertices
            .checked_add(self.edges)
            .and_then(|n| n.checked_add(self.faces))
            .and_then(|n| n.checked_add(self.corners));
        if count.is_none_or(|n| n > limit) {
            return Err(SceneError("mesh merge exceeds its component budget".into()));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct FaceMapping {
    pub source: FaceRef,
    pub survivors: Vec<FaceRef>,
}
#[derive(Debug, Clone, Default, Serialize, JsonSchema)]
pub struct Lineage {
    pub vertices: BTreeMap<String, String>,
    pub edges: BTreeMap<String, String>,
    pub faces: Vec<FaceMapping>,
}
#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct Receipt {
    pub command_index: usize,
    pub entity: String,
    pub mesh_asset: String,
    pub shared_instances: Vec<String>,
    pub method: Method,
    pub uvs: bool,
    pub status: Status,
    pub reason: Option<String>,
    pub before: Counts,
    pub after: Counts,
    pub removed: Elements,
    pub created: Elements,
    pub changed: Elements,
    pub source_to_survivor: Lineage,
}

struct Cluster {
    survivor: usize,
    vertices: Vec<usize>,
    point: Option<[f32; 3]>,
}

fn clusters(
    graph: &Graph,
    asset: &MeshAsset,
    method: Method,
    cursor: Option<[f32; 3]>,
) -> Result<Vec<Cluster>> {
    let editing = asset.editing.as_ref();
    let selected: Vec<_> = graph
        .vertex_ids
        .iter()
        .enumerate()
        .filter_map(|(i, id)| {
            editing
                .is_some_and(|state| state.selected.vertices.contains(id))
                .then_some(i)
        })
        .collect();
    let endpoint = if matches!(method, Method::First | Method::Last) {
        let Some(state) = editing else {
            return Err(SceneError(
                "merge method unavailable without vertex history".into(),
            ));
        };
        let entry = if method == Method::First {
            state.history.first()
        } else {
            state.history.last()
        };
        if !state.mode.contains(&Domain::Vertex) || entry.is_none() {
            return Err(SceneError(
                "merge method unavailable without vertex history".into(),
            ));
        }
        match entry {
            Some(Component::Vertex { id }) if state.selected.vertices.contains(id) => {
                Some(graph.vertex_index[id])
            }
            _ => return Ok(Vec::new()),
        }
    } else {
        None
    };
    if selected.is_empty() {
        return Ok(Vec::new());
    }
    if method != Method::Collapse {
        let survivor = endpoint.unwrap_or(selected[0]);
        let point = match method {
            Method::Center => Some(snap::average(
                selected
                    .iter()
                    .map(|i| snap::point(graph.positions[*i]))
                    .collect::<Result<Vec<_>>>()?,
            )),
            Method::Cursor => Some(cursor.expect("cursor prepared from the actual scene")),
            // Explicit pointmerge does not write the target coordinate.
            _ => None,
        };
        let mut vertices = vec![survivor];
        vertices.extend(selected.into_iter().filter(|v| *v != survivor));
        return Ok(vec![Cluster {
            survivor,
            vertices,
            point,
        }]);
    }
    let editing = editing.expect("selected vertices require editing");
    let marked: Vec<_> = graph
        .edges
        .iter()
        .map(|edge| editing.selected.edges.contains(&edge.id))
        .collect();
    let mut visited = vec![false; graph.edges.len()];
    let mut result = Vec::new();
    // BMW_VERT_SHELL visits selected incident edges in breadth-first order.
    for seed in 0..graph.edges.len() {
        if !marked[seed] || visited[seed] {
            continue;
        }
        let mut queue = VecDeque::new();
        let enqueue = |v: usize, queue: &mut VecDeque<usize>, visited: &mut [bool]| {
            for &edge in &graph.vertex_edges[v] {
                if marked[edge] && !visited[edge] {
                    visited[edge] = true;
                    queue.push_back(edge);
                }
            }
        };
        enqueue(graph.edges[seed].vertices[0], &mut queue, &mut visited);
        let mut sum = [0_f32; 3];
        let mut count = 0usize;
        let mut vertices = BTreeSet::new();
        let mut survivor = graph.edges[seed].vertices[0];
        while let Some(edge) = queue.pop_front() {
            let edge = &graph.edges[edge];
            survivor = edge.vertices[0];
            for v in edge.vertices {
                sum = snap::add(sum, snap::point(graph.positions[v])?);
                count = count
                    .checked_add(1)
                    .ok_or_else(|| SceneError("merge endpoint count overflow".into()))?;
                vertices.insert(v);
                enqueue(v, &mut queue, &mut visited);
            }
        }
        let factor = 1_f32 / count as f32;
        result.push(Cluster {
            survivor,
            vertices: vertices.into_iter().collect(),
            point: Some(sum.map(|n| n * factor)),
        });
    }
    Ok(result)
}

pub fn execute(scene: &mut Scene, request: &Request) -> Result<Receipt> {
    let target = scene
        .entities
        .get(&request.entity)
        .ok_or_else(|| SceneError("unknown mesh merge entity".into()))?;
    let EntityKind::Mesh {
        geometry: Geometry::Asset { id },
        ..
    } = &target.content
    else {
        return Err(SceneError(
            "merge requires an entity with a shared mesh asset".into(),
        ));
    };
    let id = id.clone();
    let original = scene
        .mesh_assets
        .get(&id)
        .ok_or_else(|| SceneError("unknown mesh merge asset".into()))?;
    let graph = original.validated_topology()?;
    let before = Counts::of(&graph)?;
    before.budget(request.max_components)?;
    let cursor = if request.method == Method::Cursor {
        let world = frame_math::world(scene, &request.entity)?.map(|row| row.map(|n| n as f32));
        let inverse = super::creation::inverse4::inverse_or_zero(world)?;
        let cursor = snap::point(
            scene
                .authoring_context
                .as_ref()
                .map(|context| context.cursor_location)
                .unwrap_or([0.; 3]),
        )?;
        Some(std::array::from_fn(|r| {
            inverse[r][0] * cursor[0]
                + inverse[r][1] * cursor[1]
                + inverse[r][2] * cursor[2]
                + inverse[r][3]
        }))
    } else {
        None
    };
    let clusters = clusters(&graph, original, request.method, cursor)?;
    if clusters
        .iter()
        .any(|cluster| cluster.point.iter().flatten().any(|n| !n.is_finite()))
    {
        return Err(SceneError(
            "mesh merge result exceeds finite f32 range".into(),
        ));
    }
    let mut candidate = original.clone();
    let lineage = weld::apply(
        &mut candidate,
        &graph,
        &clusters,
        request.method,
        request.uvs,
    )?;
    let after_graph = candidate.validated_topology()?;
    let after = Counts::of(&after_graph)?;
    after.budget(request.max_components)?;
    let old = elements(&graph);
    let new = elements(&after_graph);
    let removed = difference(&old, &new);
    let created = difference(&new, &old);
    let changed = weld::changed(original, &candidate, &graph, &after_graph);
    let data_changed = candidate != *original;
    let reason = if clusters.is_empty() {
        Some("no_available_merge_target".into())
    } else if !data_changed {
        Some("unchanged".into())
    } else {
        None
    };
    if data_changed {
        if let Some(recipe) = &mut candidate.recipe {
            recipe.edited = true;
        }
    }
    let shared_instances = scene
        .entities
        .iter()
        .filter_map(|(entity, value)| match &value.content {
            EntityKind::Mesh {
                geometry: Geometry::Asset { id: other },
                ..
            } if other == &id => Some(entity.clone()),
            _ => None,
        })
        .collect();
    let receipt = Receipt {
        command_index: 0,
        entity: request.entity.clone(),
        mesh_asset: id.clone(),
        shared_instances,
        method: request.method,
        uvs: request.uvs,
        status: if clusters.is_empty()
            && original
                .editing
                .as_ref()
                .is_some_and(|state| !state.selected.vertices.is_empty())
            && matches!(request.method, Method::First | Method::Last)
        {
            Status::Cancelled
        } else {
            Status::Finished
        },
        reason,
        before,
        after,
        removed,
        created,
        changed,
        source_to_survivor: lineage,
    };
    scene.mesh_assets.insert(id, candidate);
    Ok(receipt)
}

fn elements(graph: &Graph) -> Elements {
    Elements {
        vertices: graph.vertex_ids.iter().cloned().collect(),
        edges: graph.edges.iter().map(|edge| edge.id.clone()).collect(),
        faces: graph.faces.iter().map(|face| face.key.clone()).collect(),
    }
}
fn difference(a: &Elements, b: &Elements) -> Elements {
    Elements {
        vertices: a.vertices.difference(&b.vertices).cloned().collect(),
        edges: a.edges.difference(&b.edges).cloned().collect(),
        faces: a.faces.difference(&b.faces).cloned().collect(),
    }
}

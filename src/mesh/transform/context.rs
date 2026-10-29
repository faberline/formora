// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
use super::{
    IDENTITY, Matrix, Orientation, Pivot, Request, Vector, add, finite, math, normalized, sub,
};
use crate::mesh::selection::{Component, Domain, Graph};
use crate::scene::{EntityKind, Geometry, Result, Scene, SceneError};
use std::collections::BTreeMap;

pub(super) struct Context {
    pub asset: String,
    pub instances: Vec<String>,
    pub graph: Graph,
    pub positions: Vec<Vector>,
    pub selected: Vec<bool>,
    pub visible: Vec<bool>,
    pub edge_visible: Vec<bool>,
    pub face_visible: Vec<bool>,
    pub island_member: Vec<bool>,
    pub object: Matrix,
    pub inverse: Matrix,
    pub basis: Matrix,
    pub basis_inverse: Matrix,
    pub pivot: Vector,
    pub centres: Vec<Vector>,
    pub world_positions: Vec<Vector>,
    pub view_axis: Vector,
}
fn axes(matrix: Matrix) -> Result<Matrix> {
    let columns = (0..3)
        .map(|i| normalized(std::array::from_fn(|j| matrix[j][i])))
        .collect::<Result<Vec<_>>>()?;
    Ok(std::array::from_fn(|r| {
        std::array::from_fn(|c| columns[c][r])
    }))
}
fn average(points: impl IntoIterator<Item = Vector>) -> Vector {
    let mut sum = [0.; 3];
    let mut count = 0;
    for p in points {
        sum = add(sum, p);
        count += 1;
    }
    if count > 0 {
        let inverse = 1. / count as f32;
        sum.map(|v| v * inverse)
    } else {
        sum
    }
}
fn root(parent: &mut [usize], index: usize) -> usize {
    let mut result = index;
    while parent[result] != result {
        result = parent[result];
    }
    let mut current = index;
    while parent[current] != current {
        let next = parent[current];
        parent[current] = result;
        current = next;
    }
    result
}
fn join(parent: &mut [usize], a: usize, b: usize) {
    let a = root(parent, a);
    let b = root(parent, b);
    if a != b {
        parent[a.max(b)] = a.min(b);
    }
}

impl Context {
    pub fn new(scene: &Scene, request: &Request) -> Result<Self> {
        let target = scene
            .entities
            .get(&request.entity)
            .ok_or_else(|| SceneError(format!("unknown transform entity: {}", request.entity)))?;
        let EntityKind::Mesh {
            geometry: Geometry::Asset { id },
            ..
        } = &target.content
        else {
            return Err(SceneError(
                "mesh transform requires an entity with a shared mesh asset".into(),
            ));
        };
        let asset = scene
            .mesh_assets
            .get(id)
            .ok_or_else(|| SceneError(format!("unknown transform mesh asset: {id}")))?;
        asset.validate()?;
        if request.max_components == 0 {
            return Err(SceneError(
                "mesh transform component budget must be positive".into(),
            ));
        }
        let corners = asset
            .polygons
            .values()
            .map(|f| f.vertices.len())
            .chain(asset.triangles.values().map(|_| 3))
            .try_fold(0usize, |a, b| a.checked_add(b))
            .ok_or_else(|| SceneError("mesh transform component count overflow".into()))?;
        let graph = Graph::new(asset)?;
        let count = [
            graph.vertex_ids.len(),
            graph.edges.len(),
            graph.faces.len(),
            corners,
        ]
        .into_iter()
        .try_fold(0usize, |a, b| a.checked_add(b))
        .ok_or_else(|| SceneError("mesh transform component count overflow".into()))?;
        if count > request.max_components {
            return Err(SceneError(
                "mesh transform exceeds its component budget".into(),
            ));
        }
        let editing = asset
            .editing
            .as_ref()
            .ok_or_else(|| SceneError("mesh transform requires persistent editing state".into()))?;
        let positions: Vec<_> = graph
            .positions
            .iter()
            .map(|p| p.map(|v| v as f32))
            .collect();
        if positions.iter().flatten().any(|v| !v.is_finite()) {
            return Err(SceneError(
                "mesh transform geometry must fit finite f32 values".into(),
            ));
        }
        let visible: Vec<_> = graph
            .vertex_ids
            .iter()
            .map(|id| !editing.hidden.vertices.contains(id))
            .collect();
        let selected: Vec<_> = graph
            .vertex_ids
            .iter()
            .zip(&visible)
            .map(|(id, visible)| *visible && editing.selected.vertices.contains(id))
            .collect();
        let edge_visible: Vec<_> = graph
            .edges
            .iter()
            .map(|e| {
                !editing.hidden.edges.contains(&e.id) && e.vertices.iter().all(|v| visible[*v])
            })
            .collect();
        let face_visible: Vec<_> = graph
            .faces
            .iter()
            .map(|f| {
                !editing.hidden.faces.contains(&f.key)
                    && f.vertices.iter().all(|v| visible[*v])
                    && f.edges.iter().all(|e| edge_visible[*e])
            })
            .collect();
        if !selected.iter().any(|v| *v) {
            return Err(SceneError(
                "mesh transform has no visible selected vertices".into(),
            ));
        }
        let world = math::world(scene, &request.entity)?;
        let object = std::array::from_fn(|i| std::array::from_fn(|j| world[i][j] as f32));
        let inverse = math::inverse(object)?;
        let translation = std::array::from_fn(|i| world[i][3] as f32);
        let world_positions: Vec<_> = positions
            .iter()
            .map(|p| add(math::vector(object, *p), translation))
            .collect();
        let authoring = scene.authoring_context.clone().unwrap_or_default();
        let view = math::euler(authoring.view_rotation, true);
        let basis = match &request.orientation {
            Orientation::Global => IDENTITY,
            Orientation::Local => axes(object)?,
            Orientation::Parent => match &target.parent {
                None => IDENTITY,
                Some(parent) => {
                    let w = math::world(scene, parent)?;
                    axes(std::array::from_fn(|i| {
                        std::array::from_fn(|j| w[i][j] as f32)
                    }))?
                }
            },
            Orientation::Cursor => math::euler(authoring.cursor_rotation, true),
            Orientation::View => view,
            Orientation::Custom { matrix } => {
                for row in matrix {
                    finite(row)?;
                }
                matrix.map(|r| r.map(|v| v as f32))
            }
            Orientation::Normal => {
                return Err(SceneError(
                    "mesh transform normal orientation is not implemented yet".into(),
                ));
            }
            Orientation::Gimbal => {
                return Err(SceneError(
                    "mesh transform gimbal orientation is not implemented yet".into(),
                ));
            }
        };
        let basis_inverse = math::inverse(basis)?;
        let mut local_islands = positions.clone();
        let mut island_member = vec![false; positions.len()];
        if request.pivot == Pivot::Individual {
            let mut parent: Vec<_> = (0..positions.len()).collect();
            let edge_mode =
                editing.mode.contains(&Domain::Vertex) || editing.mode.contains(&Domain::Edge);
            if edge_mode {
                for edge in &graph.edges {
                    if editing.selected.edges.contains(&edge.id)
                        && edge.vertices.iter().all(|v| selected[*v])
                    {
                        join(&mut parent, edge.vertices[0], edge.vertices[1]);
                    }
                }
            } else {
                for face in &graph.faces {
                    if editing.selected.faces.contains(&face.key)
                        && face.vertices.iter().all(|v| selected[*v])
                    {
                        for v in &face.vertices[1..] {
                            join(&mut parent, face.vertices[0], *v);
                        }
                    }
                }
            }
            let mut groups: BTreeMap<usize, Vec<Vector>> = BTreeMap::new();
            if edge_mode {
                for edge in &graph.edges {
                    if editing.selected.edges.contains(&edge.id)
                        && edge.vertices.iter().all(|v| selected[*v])
                    {
                        let centre = average(edge.vertices.map(|v| positions[v]));
                        groups
                            .entry(root(&mut parent, edge.vertices[0]))
                            .or_default()
                            .push(centre);
                    }
                }
            } else {
                for face in &graph.faces {
                    if editing.selected.faces.contains(&face.key)
                        && face.vertices.iter().all(|v| selected[*v])
                    {
                        let centre = average(face.vertices.iter().map(|v| positions[*v]));
                        groups
                            .entry(root(&mut parent, face.vertices[0]))
                            .or_default()
                            .push(centre);
                    }
                }
            }
            let groups: BTreeMap<_, _> =
                groups.into_iter().map(|(id, p)| (id, average(p))).collect();
            for (i, island) in local_islands.iter_mut().enumerate() {
                if let Some(centre) = groups.get(&root(&mut parent, i)) {
                    *island = *centre;
                    island_member[i] = true;
                } else if selected[i]
                    && editing.mode.contains(&Domain::Vertex)
                    && request.proportional.as_ref().is_some_and(|p| p.connected)
                {
                    island_member[i] = true;
                }
            }
        }
        let median = || {
            average(
                world_positions
                    .iter()
                    .zip(&selected)
                    .filter(|(_, s)| **s)
                    .map(|(p, _)| *p),
            )
        };
        let pivot = if let Some(point) = request.center_override {
            finite(&point)?;
            point.map(|v| v as f32)
        } else {
            match request.pivot {
                Pivot::Median => median(),
                Pivot::Bounds => {
                    let mut low = [f32::INFINITY; 3];
                    let mut high = [f32::NEG_INFINITY; 3];
                    for (p, s) in world_positions.iter().zip(&selected) {
                        if *s {
                            for i in 0..3 {
                                low[i] = low[i].min(p[i]);
                                high[i] = high[i].max(p[i]);
                            }
                        }
                    }
                    std::array::from_fn(|i| (low[i] + high[i]) * 0.5)
                }
                Pivot::Cursor => authoring.cursor_location.map(|v| v as f32),
                Pivot::Active => {
                    let component = if editing.mode.contains(&Domain::Face) {
                        editing
                            .active_face
                            .as_ref()
                            .map(|face| Component::Face { face: face.clone() })
                            .or_else(|| editing.history.last().cloned())
                    } else {
                        editing.history.last().cloned()
                    };
                    let local = match component {
                        Some(Component::Vertex { id }) => Some(positions[graph.vertex_index[&id]]),
                        Some(Component::Edge { id }) => Some(average(
                            graph.edges[graph.edge_index[&id]]
                                .vertices
                                .map(|v| positions[v]),
                        )),
                        Some(Component::Face { face }) => Some(average(
                            graph.faces[graph.face_index[&face]]
                                .vertices
                                .iter()
                                .map(|v| positions[*v]),
                        )),
                        None => None,
                    };
                    local
                        .map(|p| add(math::vector(object, p), translation))
                        .unwrap_or_else(median)
                }
                Pivot::Individual => average(
                    local_islands
                        .iter()
                        .zip(&selected)
                        .filter(|(_, s)| **s)
                        .map(|(p, _)| add(math::vector(object, *p), translation)),
                ),
            }
        };
        let local_pivot = math::vector(inverse, sub(pivot, translation));
        let centres = if request.pivot == Pivot::Individual {
            local_islands
        } else {
            vec![local_pivot; positions.len()]
        };
        if pivot
            .iter()
            .chain(centres.iter().flatten())
            .chain(world_positions.iter().flatten())
            .any(|v| !v.is_finite())
        {
            return Err(SceneError(
                "mesh transform frame arithmetic exceeded finite f32 range".into(),
            ));
        }
        let instances=scene.entities.iter().filter(|(_,e)|matches!(&e.content,EntityKind::Mesh {geometry:Geometry::Asset {id:asset},..} if asset==id)).map(|(id,_)|id.clone()).collect();
        Ok(Self {
            asset: id.clone(),
            instances,
            graph,
            positions,
            selected,
            visible,
            edge_visible,
            face_visible,
            island_member,
            object,
            inverse,
            basis,
            basis_inverse,
            pivot,
            centres,
            world_positions,
            view_axis: std::array::from_fn(|i| view[i][2]),
        })
    }
}

// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
//! Direct edit-mesh snapping from actual persistent scene state.
use super::{
    frame_math as math,
    selection::{Component, Domain, Editing, Elements, Graph},
    transform::Pivot,
};
use crate::scene::{EntityKind, Geometry, Result, Scene, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

type Vector = [f32; 3];
type Matrix = [[f32; 3]; 3];

fn enabled() -> bool {
    true
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Action {
    SelectedToGrid {
        spacing: f64,
    },
    SelectedToCursor {
        #[serde(default = "enabled")]
        use_offset: bool,
        #[serde(default)]
        use_rotation: bool,
    },
    SelectedToActive {},
    CursorToGrid {
        spacing: f64,
    },
    CursorToSelected {},
    CursorToActive {},
    CursorToCenter {},
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub entity: String,
    pub action: Action,
    #[serde(default)]
    pub pivot: Pivot,
    #[serde(default = "super::primitives::default_budget")]
    pub max_components: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Finished,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct Receipt {
    pub command_index: usize,
    pub entity: String,
    pub mesh_asset: String,
    pub shared_instances: Vec<String>,
    pub action: Action,
    pub status: Status,
    pub reason: Option<String>,
    pub grid_spacing_metres: Option<f64>,
    pub pivot: Pivot,
    pub pivot_world: Option<[f64; 3]>,
    pub target_world: Option<[f64; 3]>,
    pub changed: Elements,
    pub cursor_before: [f64; 3],
    pub cursor_after: [f64; 3],
    pub cursor_rotation_before: [f64; 3],
    pub cursor_rotation_after: [f64; 3],
    pub cursor_changed: bool,
    pub rotation_applied: bool,
}

pub(crate) fn finite(value: f64) -> Result<f32> {
    let result = value as f32;
    if result.is_finite() {
        Ok(result)
    } else {
        Err(SceneError(
            "mesh snap coordinates must fit finite f32 values".into(),
        ))
    }
}
pub(crate) fn point(value: [f64; 3]) -> Result<Vector> {
    Ok([finite(value[0])?, finite(value[1])?, finite(value[2])?])
}
pub(crate) fn add(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[i] + b[i])
}
pub(crate) fn sub(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[i] - b[i])
}
pub(crate) fn average(points: impl IntoIterator<Item = Vector>) -> Vector {
    let mut sum = [0.; 3];
    let mut count = 0;
    for p in points {
        sum = add(sum, p);
        count += 1;
    }
    if count > 0 {
        let factor = 1. / count as f32;
        sum.map(|v| v * factor)
    } else {
        sum
    }
}
pub(crate) fn grid(point: Vector, spacing: f32) -> Vector {
    point.map(|v| spacing * (0.5 + v / spacing).floor())
}

// The direct source ignores invert_m3_m3's false result and retains its
// adjugate. Its determinant expression/order differs from the safe inverse.
pub(crate) fn inverse(m: Matrix) -> Matrix {
    let [[a, b, c], [d, e, f], [g, h, i]] = m;
    let adj = [
        [e * i - f * h, -b * i + c * h, b * f - c * e],
        [-d * i + f * g, a * i - c * g, -a * f + c * d],
        [d * h - e * g, -a * h + b * g, a * e - b * d],
    ];
    let determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
    if determinant == 0. {
        adj
    } else {
        let factor = 1. / determinant;
        adj.map(|r| r.map(|v| v * factor))
    }
}

pub(crate) fn selected(graph: &Graph, editing: &Editing) -> Vec<bool> {
    let mut result = vec![false; graph.vertex_ids.len()];
    if editing.mode.contains(&Domain::Vertex) {
        for (i, id) in graph.vertex_ids.iter().enumerate() {
            result[i] =
                editing.selected.vertices.contains(id) && !editing.hidden.vertices.contains(id);
        }
    } else if editing.mode.contains(&Domain::Edge) {
        for edge in &graph.edges {
            if editing.selected.edges.contains(&edge.id) && !editing.hidden.edges.contains(&edge.id)
            {
                for i in edge.vertices {
                    result[i] = true;
                }
            }
        }
    } else {
        for face in &graph.faces {
            if editing.selected.faces.contains(&face.key)
                && !editing.hidden.faces.contains(&face.key)
            {
                for i in &face.vertices {
                    result[*i] = true;
                }
            }
        }
    }
    result
}

pub(crate) fn active(graph: &Graph, editing: &Editing, positions: &[Vector]) -> Option<Vector> {
    let face = editing
        .active_face
        .as_ref()
        .filter(|f| editing.selected.faces.contains(*f));
    let component = match editing.history.last() {
        Some(Component::Face { .. }) | None => face
            .map(|face| Component::Face { face: face.clone() })
            .or_else(|| editing.history.last().cloned()),
        value => value.cloned(),
    };
    match component {
        Some(Component::Vertex { id }) => Some(positions[graph.vertex_index[&id]]),
        Some(Component::Edge { id }) => {
            let [a, b] = graph.edges[graph.edge_index[&id]].vertices;
            Some(add(positions[a], positions[b]).map(|v| v * 0.5))
        }
        Some(Component::Face { face }) => Some(average(
            graph.faces[graph.face_index[&face]]
                .vertices
                .iter()
                .map(|i| positions[*i]),
        )),
        None => None,
    }
}

/// Compute privately. Editor and Session provide revision, batch and save rollback.
pub fn execute(scene: &mut Scene, request: &Request) -> Result<Receipt> {
    execute_with_targets(scene, request, None, None)
}

/// A scene operation freezes one centre/active target across unique edit data.
/// These values come only from actual scene state, never from an agent request.
pub(crate) fn execute_with_targets(
    scene: &mut Scene,
    request: &Request,
    targets: Option<(Option<Vector>, Option<Vector>)>,
    prepared: Option<&Graph>,
) -> Result<Receipt> {
    let target = scene
        .entities
        .get(&request.entity)
        .ok_or_else(|| SceneError("unknown mesh snap entity".into()))?;
    let EntityKind::Mesh {
        geometry: Geometry::Asset { id },
        ..
    } = &target.content
    else {
        return Err(SceneError(
            "mesh snap requires an entity with a shared mesh asset".into(),
        ));
    };
    let id = id.clone();
    let asset = scene
        .mesh_assets
        .get(&id)
        .ok_or_else(|| SceneError("unknown mesh snap asset".into()))?;
    let owned_graph;
    let graph = if let Some(graph) = prepared {
        graph
    } else {
        owned_graph = asset.validated_topology()?;
        &owned_graph
    };
    let corners = graph
        .faces
        .iter()
        .try_fold(0usize, |count, face| count.checked_add(face.vertices.len()))
        .ok_or_else(|| SceneError("mesh snap component count overflow".into()))?;
    let count = [
        graph.vertex_ids.len(),
        graph.edges.len(),
        graph.faces.len(),
        corners,
    ]
    .into_iter()
    .try_fold(0usize, |a, b| a.checked_add(b))
    .ok_or_else(|| SceneError("mesh snap component count overflow".into()))?;
    if request.max_components == 0 || count > request.max_components {
        return Err(SceneError("mesh snap exceeds its component budget".into()));
    }
    let editing = asset
        .editing
        .as_ref()
        .ok_or_else(|| SceneError("mesh snap requires persistent editing state".into()))?;
    let spacing = match request.action {
        Action::SelectedToGrid { spacing } | Action::CursorToGrid { spacing } => {
            let value = finite(spacing)?;
            if value <= 0. {
                return Err(SceneError("mesh snap grid spacing must be positive".into()));
            }
            Some(value)
        }
        _ => None,
    };
    let positions = graph
        .positions
        .iter()
        .copied()
        .map(point)
        .collect::<Result<Vec<_>>>()?;
    let selected = selected(graph, editing);
    let world = math::world(scene, &request.entity)?;
    let basis: Matrix = std::array::from_fn(|i| std::array::from_fn(|j| world[i][j] as f32));
    let translation = std::array::from_fn(|i| world[i][3] as f32);
    let inverse = inverse(basis);
    let to_world = |p| add(math::vector(basis, p), translation);
    let points = positions
        .iter()
        .zip(&selected)
        .filter(|(_, s)| **s)
        .map(|(p, _)| to_world(*p))
        .collect::<Vec<_>>();
    let center = if points.is_empty() {
        None
    } else if request.pivot == Pivot::Bounds {
        let mut low = points[0];
        let mut high = points[0];
        for p in &points[1..] {
            for i in 0..3 {
                low[i] = low[i].min(p[i]);
                high[i] = high[i].max(p[i]);
            }
        }
        Some(add(low, high).map(|v| v * 0.5))
    } else {
        Some(average(points))
    };
    let active = active(graph, editing, &positions).map(to_world);
    let (center, active) = targets.unwrap_or((center, active));
    let mut authoring = scene.authoring_context.clone().unwrap_or_default();
    authoring.validate()?;
    let before = point(authoring.cursor_location)?;
    let rotation_before = point(authoring.cursor_rotation)?;
    let mut cursor = before;
    let mut cursor_rotation = rotation_before;
    let mut next = asset.clone();
    let mut pivot = None;
    let mut target_world = None;
    let mut status = Status::Finished;
    let mut reason = None;
    let mut changed = Elements::default();
    match request.action {
        Action::CursorToCenter {} => {
            cursor = [0.; 3];
            cursor_rotation = [0.; 3];
            target_world = Some(cursor);
        }
        Action::CursorToGrid { .. } => {
            cursor = grid(cursor, spacing.unwrap());
            target_world = Some(cursor);
        }
        Action::CursorToSelected {} | Action::CursorToActive {} => {
            let target = if matches!(request.action, Action::CursorToSelected {}) {
                center
            } else {
                active
            };
            if let Some(target) = target {
                cursor = target;
                target_world = Some(target);
            } else {
                status = Status::Cancelled;
                reason = Some("no effective selected or active mesh element".into());
            }
        }
        Action::SelectedToActive {}
        | Action::SelectedToCursor { .. }
        | Action::SelectedToGrid { .. } => {
            let target = match request.action {
                Action::SelectedToActive {} => Some(
                    active
                        .ok_or_else(|| SceneError("mesh snap: no active element found".into()))?,
                ),
                Action::SelectedToCursor { .. } => Some(before),
                _ => None,
            };
            target_world = target;
            let offset = if matches!(
                request.action,
                Action::SelectedToCursor {
                    use_offset: true,
                    ..
                }
            ) {
                pivot = if request.pivot == Pivot::Active {
                    active.or(center)
                } else {
                    center
                };
                pivot.map(|p| math::vector(inverse, sub(before, p)))
            } else {
                None
            };
            let local_target = target.map(|p| math::vector(inverse, sub(p, translation)));
            for (i, p) in positions.iter().enumerate() {
                if !selected[i] {
                    continue;
                }
                let new = match request.action {
                    Action::SelectedToGrid { .. } => math::vector(
                        inverse,
                        sub(grid(to_world(*p), spacing.unwrap()), translation),
                    ),
                    Action::SelectedToCursor {
                        use_offset: true, ..
                    } => add(
                        *p,
                        offset.ok_or_else(|| {
                            SceneError("mesh snap selected centre is missing".into())
                        })?,
                    ),
                    _ => local_target.unwrap(),
                };
                point(new.map(f64::from))?;
                if new.map(f64::from) != graph.positions[i] {
                    let name = &graph.vertex_ids[i];
                    next.vertices.insert(name.clone(), new.map(f64::from));
                    changed.vertices.insert(name.clone());
                }
            }
        }
    }
    point(cursor.map(f64::from))?;
    point(cursor_rotation.map(f64::from))?;
    if !changed.vertices.is_empty() {
        for edge in &graph.edges {
            if edge
                .vertices
                .iter()
                .any(|i| changed.vertices.contains(&graph.vertex_ids[*i]))
            {
                changed.edges.insert(edge.id.clone());
            }
        }
        for face in &graph.faces {
            if face
                .vertices
                .iter()
                .any(|i| changed.vertices.contains(&graph.vertex_ids[*i]))
            {
                changed.faces.insert(face.key.clone());
            }
        }
        if let Some(recipe) = &mut next.recipe {
            recipe.edited = true;
        }
        super::normals::apply_automatic(&mut next)?;
    }
    next.validate()?;
    let writes_cursor = status == Status::Finished
        && matches!(
            request.action,
            Action::CursorToGrid { .. }
                | Action::CursorToSelected {}
                | Action::CursorToActive {}
                | Action::CursorToCenter {}
        );
    let cursor_after = if writes_cursor {
        cursor.map(f64::from)
    } else {
        authoring.cursor_location
    };
    let cursor_rotation_after = if matches!(request.action, Action::CursorToCenter {}) {
        [0.; 3]
    } else {
        authoring.cursor_rotation
    };
    let cursor_changed = cursor_after != authoring.cursor_location
        || cursor_rotation_after != authoring.cursor_rotation;
    let shared_instances = scene
        .entities
        .iter()
        .filter_map(|(name, entity)| match &entity.content {
            EntityKind::Mesh {
                geometry: Geometry::Asset { id: other },
                ..
            } if other == &id => Some(name.clone()),
            _ => None,
        })
        .collect();
    let receipt = Receipt {
        command_index: 0,
        entity: request.entity.clone(),
        mesh_asset: id.clone(),
        shared_instances,
        action: request.action.clone(),
        status,
        reason,
        grid_spacing_metres: spacing.map(f64::from),
        pivot: request.pivot,
        pivot_world: pivot.map(|p| p.map(f64::from)),
        target_world: target_world.map(|p| p.map(f64::from)),
        changed,
        cursor_before: authoring.cursor_location,
        cursor_after,
        cursor_rotation_before: authoring.cursor_rotation,
        cursor_rotation_after,
        cursor_changed,
        rotation_applied: false,
    };
    if cursor_changed {
        authoring.cursor_location = receipt.cursor_after;
        authoring.cursor_rotation = receipt.cursor_rotation_after;
        scene.authoring_context = Some(authoring);
    }
    scene.mesh_assets.insert(id, next);
    Ok(receipt)
}

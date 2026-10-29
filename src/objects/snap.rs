// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
//! Direct snapping from actual object and unique edit-mesh state.
use super::{Context, math, mesh_id};
use crate::mesh::{
    frame_math,
    snap::{self, Action, Status, add, finite, grid, point, sub},
    transform::Pivot,
};
use crate::rotation::{RotationAngles, TransformRotation};
use crate::scene::{Result, Scene, SceneError};
use crate::transforms::Matrix;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

fn object_budget() -> usize {
    10_000
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub action: Action,
    #[serde(default)]
    pub pivot: Pivot,
    #[serde(default = "crate::mesh::primitives::default_budget")]
    pub max_components: usize,
    #[serde(default = "object_budget")]
    pub max_objects: usize,
}

#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct ObjectChange {
    pub entity: String,
    pub transform_before: crate::scene::Transform,
    pub transform_after: crate::scene::Transform,
    pub parent_inverse_before: Matrix,
    pub parent_inverse_after: Matrix,
}
#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct MeshChange {
    pub mesh_asset: String,
    pub representative: String,
    pub shared_instances: Vec<String>,
    pub changed: crate::mesh::selection::Elements,
}
#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct Receipt {
    pub command_index: usize,
    pub action: Action,
    pub status: Status,
    pub reason: Option<String>,
    pub pivot_world: Option<[f64; 3]>,
    pub target_world: Option<[f64; 3]>,
    pub objects: Vec<ObjectChange>,
    pub meshes: Vec<MeshChange>,
    pub edit_meshes: Vec<snap::Receipt>,
    pub cursor_before: [f64; 3],
    pub cursor_after: [f64; 3],
    pub cursor_rotation_before: [f64; 3],
    pub cursor_rotation_after: [f64; 3],
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cursor_orientation_before: Option<crate::rotation::Channels>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cursor_orientation_after: Option<crate::rotation::Channels>,
    pub cursor_changed: bool,
}

fn unique_edit_objects(scene: &Scene, context: &Context) -> Result<Vec<String>> {
    let mut seen = BTreeSet::new();
    let mut objects = Vec::new();
    let order = context
        .active
        .iter()
        .map(String::as_str)
        .chain(context.ordered(scene));
    for id in order {
        if context.edit_objects.contains(id) && seen.insert(mesh_id(scene, id)?) {
            objects.push(id.to_owned());
        }
    }
    Ok(objects)
}

fn selected_points(
    scene: &Scene,
    context: &Context,
    edit: &[String],
    graphs: &BTreeMap<String, crate::mesh::selection::Graph>,
) -> Result<Vec<[f32; 3]>> {
    let mut points = Vec::new();
    if context.edit_objects.is_empty() {
        for id in context.ordered(scene) {
            if context.selected.contains(id) {
                points.push(math::location(math::world(scene, id)?));
            }
        }
    } else {
        for id in edit {
            let asset = &scene.mesh_assets[mesh_id(scene, id)?];
            let graph = &graphs[mesh_id(scene, id)?];
            let mask = snap::selected(
                graph,
                asset.editing.as_ref().expect("validated edit context"),
            );
            let world = math::world(scene, id)?;
            for (p, selected) in graph.positions.iter().zip(mask) {
                if selected {
                    points.push(add(
                        frame_math::vector(math::basis(world), point(*p)?),
                        math::location(world),
                    ));
                }
            }
        }
    }
    Ok(points)
}

fn active_center(
    scene: &Scene,
    context: &Context,
    selected_only: bool,
    graphs: &BTreeMap<String, crate::mesh::selection::Graph>,
) -> Result<Option<[f32; 3]>> {
    let Some(id) = &context.active else {
        return Ok(None);
    };
    if context.edit_objects.is_empty() {
        return if selected_only && !context.selected.contains(id) {
            Ok(None)
        } else {
            Ok(Some(math::location(math::world(scene, id)?)))
        };
    }
    let asset = &scene.mesh_assets[mesh_id(scene, id)?];
    let graph = &graphs[mesh_id(scene, id)?];
    let positions = graph
        .positions
        .iter()
        .copied()
        .map(point)
        .collect::<Result<Vec<_>>>()?;
    let active = snap::active(
        graph,
        asset.editing.as_ref().expect("validated edit context"),
        &positions,
    );
    let world = math::world(scene, id)?;
    Ok(active.map(|p| {
        add(
            frame_math::vector(math::basis(world), p),
            math::location(world),
        )
    }))
}

fn prepare(
    scene: &Scene,
    request: &Request,
    context: &Context,
    edit: &[String],
) -> Result<BTreeMap<String, crate::mesh::selection::Graph>> {
    if request.max_objects == 0 || scene.entities.len() > request.max_objects {
        return Err(SceneError("scene snap exceeds its object budget".into()));
    }
    if request.max_components == 0 {
        return Err(SceneError("scene snap exceeds its component budget".into()));
    }
    let mut assets = BTreeSet::new();
    for id in edit {
        assets.insert(mesh_id(scene, id)?);
    }
    if context.edit_objects.is_empty() && context.origins_only {
        for id in &context.selected {
            if let Ok(asset) = mesh_id(scene, id) {
                assets.insert(asset);
            }
        }
    }
    let mut total = 0usize;
    let mut graphs = BTreeMap::new();
    for id in assets {
        let graph = scene
            .mesh_assets
            .get(id)
            .ok_or_else(|| SceneError("unknown scene snap mesh asset".into()))?
            .validated_topology()?;
        for n in [graph.vertex_ids.len(), graph.edges.len(), graph.faces.len()]
            .into_iter()
            .chain(graph.faces.iter().map(|f| f.vertices.len()))
        {
            total = total
                .checked_add(n)
                .ok_or_else(|| SceneError("scene snap component count overflow".into()))?;
            if total > request.max_components {
                return Err(SceneError("scene snap exceeds its component budget".into()));
            }
        }
        graphs.insert(id.to_owned(), graph);
    }
    Ok(graphs)
}

fn selected_ancestor(scene: &Scene, id: &str, selected: &BTreeSet<String>) -> bool {
    let mut parent = scene.entities[id].parent.as_deref();
    while let Some(id) = parent {
        if selected.contains(id) {
            return true;
        }
        parent = scene.entities[id].parent.as_deref();
    }
    false
}

fn set_rotation(
    scene: &mut Scene,
    context: &Context,
    id: &str,
    basis: [[f32; 3]; 3],
    cursor: crate::rotation::Channels,
) -> Result<()> {
    let entity = scene.entities.get_mut(id).unwrap();
    let original = entity.transform.rotation;
    let mut target = crate::rotation::Channels::from_rotation(original);
    let state = context.state(id);
    crate::rotation::source::assign(
        &mut target,
        cursor,
        basis,
        entity.parent.is_none(),
        state.lock_rotation,
        state.lock_rotation_w,
    )?;
    let updated = match original {
        TransformRotation::Authored(RotationAngles::Euler { order, .. }) => {
            TransformRotation::Authored(RotationAngles::Euler {
                angles: target.euler,
                order,
            })
        }
        TransformRotation::Authored(RotationAngles::AxisAngle { .. }) => {
            TransformRotation::Authored(RotationAngles::AxisAngle {
                axis: [
                    target.axis_angle[1],
                    target.axis_angle[2],
                    target.axis_angle[3],
                ],
                radians: target.axis_angle[0],
            })
        }
        TransformRotation::Quaternion(_) => {
            let [w, x, y, z] = target.quaternion_wxyz;
            TransformRotation::Quaternion([x, y, z, w])
        }
        _ => TransformRotation::Authored(RotationAngles::Channels { channels: target }),
    };
    // A protected raw assignment can cease to be a legacy unit quaternion.
    // Preserve those channels explicitly instead of weakening legacy validity.
    entity.transform.rotation = if updated.valid() {
        updated
    } else {
        TransformRotation::Authored(RotationAngles::Channels { channels: target })
    };
    Ok(())
}

// Apply the source's skip-child parent-inverse compensation, without changing
// the child's authored translation/rotation/scale channels.
fn skip_children(scene: &mut Scene, before: &Scene, context: &Context) -> Result<()> {
    let mut changes = Vec::new();
    for id in context.ordered(before) {
        let Some(parent) = &before.entities[id].parent else {
            continue;
        };
        let p0 = math::world(before, parent)?;
        let pi = math::inverse(p0)?;
        let d = if !context.selected.contains(id) && context.selected.contains(parent) {
            Some(math::inverse(math::mul(pi, math::world(scene, parent)?)?)?)
        } else if context.selected.contains(id)
            && !context.selected.contains(parent)
            && selected_ancestor(before, id, &context.selected)
        {
            let mut ancestor = parent.as_str();
            while !context.selected.contains(ancestor) {
                ancestor = before.entities[ancestor]
                    .parent
                    .as_deref()
                    .expect("selected ancestor");
            }
            let mut delta = math::mul(
                math::world(before, ancestor)?,
                math::inverse(math::world(scene, ancestor)?)?,
            )?;
            delta = math::inverse(delta)?;
            let original = math::mul(pi, math::world(before, id)?)?;
            let calculated = math::mul(pi, math::mul(delta, math::world(before, id)?)?)?;
            Some(math::mul(calculated, math::inverse(original)?)?)
        } else {
            None
        };
        if let Some(d) = d {
            let original = context
                .state(id)
                .parent_inverse
                .unwrap_or_else(super::identity);
            changes.push((id.to_owned(), math::mul(d, original)?));
        }
    }
    if let Some(context) = &mut scene.object_context {
        for (id, matrix) in changes {
            context.states.entry(id).or_default().parent_inverse = Some(matrix);
        }
    }
    Ok(())
}

fn origin_meshes(
    scene: &mut Scene,
    before: &Scene,
    representatives: &BTreeMap<String, String>,
    graphs: &BTreeMap<String, crate::mesh::selection::Graph>,
) -> Result<Vec<MeshChange>> {
    let mut receipts = Vec::new();
    for (asset_id, id) in representatives {
        let delta = math::inverse(math::mul(
            math::inverse(math::world(before, id)?)?,
            math::world(scene, id)?,
        )?)?;
        let original = &before.mesh_assets[asset_id];
        let mut next = original.clone();
        let mut changed = crate::mesh::selection::Elements::default();
        for (name, p) in &original.vertices {
            // Native data_xform uses source float transform_point (three
            // products summed in float, followed by translation).
            let p = point(*p)?;
            let q = add(
                frame_math::vector(math::basis(delta), p),
                math::location(delta),
            );
            let q = point(q.map(f64::from))?.map(f64::from);
            if q != original.vertices[name] {
                next.vertices.insert(name.clone(), q);
                changed.vertices.insert(name.clone());
            }
        }
        if !changed.vertices.is_empty() {
            // Positions changed; topology, identities and editing did not.
            // Reuse the validated input graph only for incidence/changed IDs.
            let graph = &graphs[asset_id];
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
            crate::mesh::normals::apply_automatic_with_topology(&mut next, graph)?;
        }
        // The command's mandatory Scene::validate checks this private candidate
        // before any result, revision, undo entry or saved file is published.
        scene.mesh_assets.insert(asset_id.clone(), next);
        let shared_instances = scene
            .entities
            .keys()
            .filter(|id| mesh_id(scene, id).is_ok_and(|a| a == asset_id))
            .cloned()
            .collect();
        receipts.push(MeshChange {
            mesh_asset: asset_id.clone(),
            representative: id.clone(),
            shared_instances,
            changed,
        });
    }
    Ok(receipts)
}

/// Editor owns the private candidate and publishes only after validation/save.
pub(crate) fn execute(scene: &mut Scene, request: &Request) -> Result<Receipt> {
    let context = scene
        .object_context
        .clone()
        .ok_or_else(|| SceneError("scene snap requires persistent object context".into()))?;
    context.validate(scene)?;
    let edit = unique_edit_objects(scene, &context)?;
    let graphs = prepare(scene, request, &context, &edit)?;
    let spacing = match request.action {
        Action::SelectedToGrid { spacing } | Action::CursorToGrid { spacing } => {
            let spacing = finite(spacing)?;
            if spacing <= 0. {
                return Err(SceneError(
                    "scene snap grid spacing must be positive".into(),
                ));
            }
            Some(spacing)
        }
        _ => None,
    };
    let before = scene.clone();
    let mut authoring = scene.authoring_context.clone().unwrap_or_default();
    authoring.validate()?;
    let cursor = point(authoring.cursor_location)?;
    let needs_center = matches!(
        request.action,
        Action::CursorToSelected {}
            | Action::SelectedToCursor {
                use_offset: true,
                ..
            }
    );
    let needs_active = matches!(
        request.action,
        Action::CursorToActive {} | Action::SelectedToActive {}
    ) || (needs_center && request.pivot == Pivot::Active);
    let center = if needs_center {
        math::center(
            &selected_points(scene, &context, &edit, &graphs)?,
            request.pivot == Pivot::Bounds,
        )
    } else {
        None
    };
    let active = if needs_active {
        active_center(scene, &context, false, &graphs)?
    } else {
        None
    };
    let pivot = if needs_center && request.pivot == Pivot::Active {
        active_center(scene, &context, true, &graphs)?.or(center)
    } else {
        center
    };
    let mut status = Status::Finished;
    let mut reason = None;
    let target;
    let mut edit_meshes = Vec::new();
    let mut meshes = Vec::new();
    match request.action {
        Action::CursorToCenter {} => {
            authoring.cursor_location = [0.; 3];
            authoring.clear_cursor_rotation();
            target = Some([0.; 3]);
        }
        Action::CursorToGrid { .. } => {
            let p = grid(cursor, spacing.unwrap());
            authoring.cursor_location = p.map(f64::from);
            target = Some(p);
        }
        Action::CursorToSelected {} | Action::CursorToActive {} => {
            target = if matches!(request.action, Action::CursorToSelected {}) {
                center
            } else {
                active
            };
            if let Some(p) = target {
                authoring.cursor_location = p.map(f64::from);
            } else {
                status = Status::Cancelled;
                reason = Some("no effective selected or active element".into());
            }
        }
        _ => {
            target = match request.action {
                Action::SelectedToActive {} => Some(
                    active
                        .ok_or_else(|| SceneError("scene snap: no active element found".into()))?,
                ),
                Action::SelectedToCursor { .. } => Some(cursor),
                _ => None,
            };
            if !context.edit_objects.is_empty() {
                for id in edit {
                    edit_meshes.push(snap::execute_with_targets(
                        scene,
                        &snap::Request {
                            entity: id.clone(),
                            action: request.action.clone(),
                            pivot: request.pivot,
                            max_components: request.max_components,
                        },
                        Some((center, active)),
                        Some(&graphs[mesh_id(&before, &id)?]),
                    )?);
                }
            } else {
                let offset = matches!(
                    request.action,
                    Action::SelectedToCursor {
                        use_offset: true,
                        ..
                    }
                );
                let rotate = matches!(
                    request.action,
                    Action::SelectedToCursor {
                        use_rotation: true,
                        ..
                    }
                );
                let rotation = authoring.cursor_matrix(false)?;
                let mut representatives = BTreeMap::new();
                // Native origin data is captured for every selected data block,
                // including selected descendants omitted by offset suppression.
                if context.origins_only {
                    for id in context.ordered(&before) {
                        if context.selected.contains(id) {
                            if let Ok(asset) = mesh_id(&before, id) {
                                representatives
                                    .entry(asset.to_owned())
                                    .or_insert_with(|| id.to_owned());
                            }
                        }
                    }
                }
                // The native dependency graph is evaluated on entry and again
                // at the explicit parent-conversion points. Later siblings see
                // that evaluated snapshot, not an always-live or frozen frame.
                let mut evaluated = before
                    .entities
                    .keys()
                    .map(|id| Ok((id.clone(), math::world(&before, id)?)))
                    .collect::<Result<BTreeMap<_, _>>>()?;
                for id in context.ordered(&before) {
                    if !context.selected.contains(id)
                        || (offset && selected_ancestor(&before, id, &context.selected))
                    {
                        continue;
                    }
                    let is_grid = matches!(request.action, Action::SelectedToGrid { .. });
                    let old_world = if is_grid {
                        math::world(&before, id)?
                    } else {
                        evaluated[id]
                    };
                    let old_location = math::location(old_world);
                    let destination = if matches!(request.action, Action::SelectedToGrid { .. }) {
                        grid(old_location, spacing.unwrap())
                    } else if offset {
                        let mut p = add(
                            old_location,
                            sub(
                                target.unwrap(),
                                pivot.ok_or_else(|| {
                                    SceneError("scene snap selected centre is missing".into())
                                })?,
                            ),
                        );
                        if rotate {
                            p = add(
                                frame_math::vector(rotation, sub(p, target.unwrap())),
                                target.unwrap(),
                            );
                        }
                        p
                    } else {
                        target.unwrap()
                    };
                    let mut delta = sub(destination, old_location);
                    let mut target_rotation = rotation;
                    if before.entities[id].parent.is_some() {
                        let parent = if is_grid {
                            math::parent_space(scene, id)?
                        } else {
                            for (id, matrix) in &mut evaluated {
                                *matrix = math::world(scene, id)?;
                            }
                            let parent = before.entities[id].parent.as_ref().unwrap();
                            math::mul(
                                evaluated[parent],
                                context
                                    .state(id)
                                    .parent_inverse
                                    .unwrap_or_else(super::identity),
                            )?
                        };
                        let inverse = snap::inverse(math::basis(parent));
                        delta = frame_math::vector(inverse, delta);
                        target_rotation = frame_math::multiply(inverse, rotation);
                    }
                    let old = point(before.entities[id].transform.translation)?;
                    let next = point(add(old, delta).map(f64::from))?;
                    let locks = context.state(id).lock_location;
                    let entity = scene.entities.get_mut(id).unwrap();
                    for i in 0..3 {
                        if !locks[i] {
                            entity.transform.translation[i] = f64::from(next[i]);
                        }
                    }
                    if rotate {
                        set_rotation(
                            scene,
                            &context,
                            id,
                            target_rotation,
                            authoring.cursor_channels(),
                        )?;
                    }
                }
                if context.skip_children {
                    skip_children(scene, &before, &context)?;
                }
                if context.origins_only {
                    meshes = origin_meshes(scene, &before, &representatives, &graphs)?;
                }
            }
        }
    }
    if authoring != before.authoring_context.clone().unwrap_or_default() {
        scene.authoring_context = Some(authoring.clone());
    }
    let mut objects = Vec::new();
    for id in context.ordered(&before) {
        let old = &before.entities[id].transform;
        let new = &scene.entities[id].transform;
        let pi_before = context
            .state(id)
            .parent_inverse
            .unwrap_or_else(super::identity);
        let pi_after = scene
            .object_context
            .as_ref()
            .unwrap()
            .state(id)
            .parent_inverse
            .unwrap_or_else(super::identity);
        if old != new || pi_before != pi_after {
            objects.push(ObjectChange {
                entity: id.to_owned(),
                transform_before: old.clone(),
                transform_after: new.clone(),
                parent_inverse_before: pi_before,
                parent_inverse_after: pi_after,
            });
        }
    }
    let original = before.authoring_context.unwrap_or_default();
    Ok(Receipt {
        command_index: 0,
        action: request.action.clone(),
        status,
        reason,
        pivot_world: if matches!(
            request.action,
            Action::SelectedToCursor {
                use_offset: true,
                ..
            }
        ) {
            pivot.map(|p| p.map(f64::from))
        } else {
            None
        },
        target_world: target.map(|p| p.map(f64::from)),
        objects,
        meshes,
        edit_meshes,
        cursor_before: original.cursor_location,
        cursor_after: authoring.cursor_location,
        cursor_rotation_before: original.cursor_rotation,
        cursor_rotation_after: authoring.cursor_rotation,
        cursor_orientation_before: original.cursor_orientation,
        cursor_orientation_after: authoring.cursor_orientation,
        cursor_changed: original.cursor_location != authoring.cursor_location
            || original.cursor_rotation != authoring.cursor_rotation
            || original.cursor_orientation != authoring.cursor_orientation,
    })
}

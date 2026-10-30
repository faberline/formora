//! Context-wide edit merging. Editor owns the atomic scene transaction.
use super::{Counts, Method, Receipt as MeshReceipt, Request as MeshRequest, Status};
use crate::mesh::selection::{Component, Domain};
use crate::scene::{EntityKind, Geometry, Result, Scene, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub method: Method,
    #[serde(default)]
    pub uvs: bool,
    #[serde(default = "crate::mesh::primitives::default_budget")]
    pub max_components: usize,
}

#[derive(Debug, Clone, Copy, Serialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Merged,
    Unchanged,
    SkippedEmptySelection,
    NotProcessedAfterSuccess,
    SkippedHistoryEndpoint,
}

#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct Provider {
    pub entity: String,
    pub mesh_asset: String,
    pub shared_instances: Vec<String>,
    pub outcome: Outcome,
    pub merge: Option<MeshReceipt>,
}

#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct Receipt {
    pub command_index: usize,
    pub active_entity: String,
    pub method: Method,
    pub uvs: bool,
    pub status: Status,
    pub provider_order: Vec<String>,
    pub before: Counts,
    pub after: Counts,
    pub providers: Vec<Provider>,
}

fn asset_id<'a>(scene: &'a Scene, entity: &str) -> Result<&'a str> {
    match scene.entities.get(entity).map(|value| &value.content) {
        Some(EntityKind::Mesh {
            geometry: Geometry::Asset { id },
            ..
        }) => Ok(id),
        _ => Err(SceneError(
            "edit merge provider requires a mesh asset".into(),
        )),
    }
}

fn zero() -> Counts {
    Counts {
        vertices: 0,
        edges: 0,
        faces: 0,
        corners: 0,
    }
}

fn add(total: &mut Counts, value: &Counts) -> Result<()> {
    fn checked(a: usize, b: usize) -> Result<usize> {
        a.checked_add(b)
            .ok_or_else(|| SceneError("edit merge component budget overflow".into()))
    }
    total.vertices = checked(total.vertices, value.vertices)?;
    total.edges = checked(total.edges, value.edges)?;
    total.faces = checked(total.faces, value.faces)?;
    total.corners = checked(total.corners, value.corners)?;
    Ok(())
}

pub(crate) fn execute(scene: &mut Scene, request: &Request) -> Result<Receipt> {
    let context = scene
        .object_context
        .as_ref()
        .ok_or_else(|| SceneError("edit merge requires an active mesh edit context".into()))?;
    context.validate(scene)?;
    let active = context
        .active
        .as_ref()
        .filter(|id| context.edit_objects.contains(*id))
        .ok_or_else(|| SceneError("edit merge requires an active mesh edit context".into()))?
        .clone();
    if matches!(request.method, Method::First | Method::Last) {
        let editing = scene.mesh_assets[asset_id(scene, &active)?]
            .editing
            .as_ref()
            .expect("validated edit owner");
        let endpoint = if request.method == Method::First {
            editing.history.first()
        } else {
            editing.history.last()
        };
        let available = editing.mode.contains(&Domain::Vertex)
            && matches!(endpoint, Some(Component::Vertex { id }) if editing.selected.vertices.contains(id));
        if !available {
            return Err(SceneError(
                "merge method unavailable in the active edit mesh".into(),
            ));
        }
    }
    let mut seen = BTreeSet::new();
    let mut plans = Vec::new();
    let mut before = zero();
    for entity in std::iter::once(active.as_str()).chain(context.ordered(scene)) {
        if !context.edit_objects.contains(entity) {
            continue;
        }
        let id = asset_id(scene, entity)?;
        if !seen.insert(id.to_owned()) {
            continue;
        }
        let asset = &scene.mesh_assets[id];
        let counts = Counts::of(&asset.validated_topology()?)?;
        add(&mut before, &counts)?;
        let empty = asset
            .editing
            .as_ref()
            .expect("validated edit owner")
            .selected
            .vertices
            .is_empty();
        let shared_instances = scene
            .entities
            .iter()
            .filter_map(|(name, value)| match &value.content {
                EntityKind::Mesh {
                    geometry: Geometry::Asset { id: other },
                    ..
                } if other == id => Some(name.clone()),
                _ => None,
            })
            .collect();
        plans.push((
            entity.to_owned(),
            id.to_owned(),
            counts,
            empty,
            shared_instances,
        ));
    }
    before.budget(request.max_components)?;
    let provider_order = plans.iter().map(|(entity, ..)| entity.clone()).collect();
    let mut after = zero();
    let mut providers = Vec::new();
    let mut stopped = false;
    for (entity, mesh_asset, counts, empty, shared_instances) in plans {
        let (outcome, merge) = if stopped {
            add(&mut after, &counts)?;
            (Outcome::NotProcessedAfterSuccess, None)
        } else if empty {
            add(&mut after, &counts)?;
            (Outcome::SkippedEmptySelection, None)
        } else {
            let receipt = super::execute(
                scene,
                &MeshRequest {
                    entity: entity.clone(),
                    method: request.method,
                    uvs: request.uvs,
                    max_components: request.max_components,
                },
            )?;
            add(&mut after, &receipt.after)?;
            let outcome = if matches!(receipt.status, Status::Cancelled) {
                Outcome::SkippedHistoryEndpoint
            } else {
                stopped = matches!(request.method, Method::First | Method::Last);
                if receipt.reason.is_some() {
                    Outcome::Unchanged
                } else {
                    Outcome::Merged
                }
            };
            (outcome, Some(receipt))
        };
        providers.push(Provider {
            entity,
            mesh_asset,
            shared_instances,
            outcome,
            merge,
        });
    }
    after.budget(request.max_components)?;
    Ok(Receipt {
        command_index: 0,
        active_entity: active,
        method: request.method,
        uvs: request.uvs,
        status: Status::Finished,
        provider_order,
        before,
        after,
        providers,
    })
}

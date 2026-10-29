//! Persistent object interaction and parent-inverse authoring state.
use crate::scene::{EntityKind, Geometry, Result, Scene, SceneError, unique_map, unique_set};
use crate::transforms::Matrix;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

mod math;
pub mod snap;

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct State {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent_inverse: Option<Matrix>,
    #[serde(default)]
    pub lock_location: [bool; 3],
    #[serde(default)]
    pub lock_rotation: [bool; 3],
    #[serde(default, skip_serializing_if = "is_false")]
    pub lock_rotation_w: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub lock_rotations_4d: bool,
}

fn is_false(value: &bool) -> bool {
    !value
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Context {
    /// Authored scene order. New objects absent from it follow in ID order.
    #[serde(default)]
    pub order: Vec<String>,
    #[serde(default, deserialize_with = "unique_set")]
    pub selected: BTreeSet<String>,
    #[serde(default)]
    pub active: Option<String>,
    #[serde(default, deserialize_with = "unique_set")]
    pub edit_objects: BTreeSet<String>,
    #[serde(default, deserialize_with = "unique_map")]
    pub states: BTreeMap<String, State>,
    #[serde(default)]
    pub skip_children: bool,
    #[serde(default)]
    pub origins_only: bool,
}

pub fn identity() -> Matrix {
    std::array::from_fn(|r| std::array::from_fn(|c| if r == c { 1. } else { 0. }))
}

#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct Frames {
    pub matrix_basis: Matrix,
    pub matrix_local: Matrix,
    pub matrix_parent_inverse: Matrix,
    pub selected: bool,
    pub edit_mode: bool,
    pub lock_location: [bool; 3],
    pub lock_rotation: [bool; 3],
    #[serde(default, skip_serializing_if = "is_false")]
    pub lock_rotation_w: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub lock_rotations_4d: bool,
}

/// Query the same parent-inverse frames used by rendering and authoring.
pub fn frames(scene: &Scene, id: &str) -> Result<Frames> {
    let entity = scene
        .entities
        .get(id)
        .ok_or_else(|| SceneError(format!("unknown object: {id}")))?;
    let context = scene.object_context.as_ref();
    let state = context.map(|c| c.state(id)).unwrap_or_default();
    let basis = crate::transforms::local(&entity.transform)?;
    let local = if let Some(parent) = &entity.parent {
        if entity.transform.precision == crate::transforms::Precision::F32 {
            math::mul(
                math::inverse(math::world(scene, parent)?)?,
                math::world(scene, id)?,
            )?
        } else {
            // The authored parent-inverse is an actual affine local frame.
            crate::transforms::compose(
                state.parent_inverse.unwrap_or_else(identity),
                basis,
                entity.transform.precision,
            )?
        }
    } else {
        basis
    };
    Ok(Frames {
        matrix_basis: basis,
        matrix_local: local,
        matrix_parent_inverse: state.parent_inverse.unwrap_or_else(identity),
        selected: context.is_some_and(|c| c.selected.contains(id)),
        edit_mode: context.is_some_and(|c| c.edit_objects.contains(id)),
        lock_location: state.lock_location,
        lock_rotation: state.lock_rotation,
        lock_rotation_w: state.lock_rotation_w,
        lock_rotations_4d: state.lock_rotations_4d,
    })
}

impl Context {
    pub fn validate(&self, scene: &Scene) -> Result<()> {
        let mut seen = BTreeSet::new();
        if self.order.iter().any(|id| !seen.insert(id)) {
            return Err(SceneError("duplicate object iteration ID".into()));
        }
        for id in self
            .order
            .iter()
            .chain(&self.selected)
            .chain(&self.edit_objects)
            .chain(self.active.iter())
            .chain(self.states.keys())
        {
            if !scene.entities.contains_key(id) {
                return Err(SceneError(format!("unknown object context entity: {id}")));
            }
        }
        if !self.edit_objects.is_empty() {
            if !self
                .active
                .as_ref()
                .is_some_and(|id| self.edit_objects.contains(id))
            {
                return Err(SceneError(
                    "active object must belong to the edit objects".into(),
                ));
            }
            let mut edit_assets = BTreeSet::new();
            for id in &self.edit_objects {
                if !self.selected.contains(id) {
                    return Err(SceneError("edit objects must be selected".into()));
                }
                let asset = mesh_id(scene, id)?;
                if !edit_assets.insert(asset) {
                    return Err(SceneError(
                        "linked mesh users cannot both own edit mode".into(),
                    ));
                }
                if scene
                    .mesh_assets
                    .get(asset)
                    .and_then(|a| a.editing.as_ref())
                    .is_none()
                {
                    return Err(SceneError(
                        "edit objects require persistent mesh editing state".into(),
                    ));
                }
            }
        }
        for state in self.states.values() {
            if let Some(matrix) = state.parent_inverse {
                if matrix
                    .iter()
                    .flatten()
                    .any(|v| !v.is_finite() || !(*v as f32).is_finite())
                    || matrix[3]
                        .iter()
                        .zip([0., 0., 0., 1.])
                        .any(|(v, expected)| (v - expected).abs() > 1e-6)
                {
                    return Err(SceneError(
                        "object parent inverse must be a finite affine matrix".into(),
                    ));
                }
            }
        }
        Ok(())
    }

    pub fn ordered<'a>(&'a self, scene: &'a Scene) -> Vec<&'a str> {
        let mut result: Vec<_> = self.order.iter().map(String::as_str).collect();
        let declared: BTreeSet<_> = result.iter().copied().collect();
        result.extend(
            scene
                .entities
                .keys()
                .map(String::as_str)
                .filter(|id| !declared.contains(id)),
        );
        result
    }

    pub fn state(&self, id: &str) -> State {
        self.states.get(id).cloned().unwrap_or_default()
    }
}

pub(crate) fn mesh_id<'a>(scene: &'a Scene, id: &str) -> Result<&'a str> {
    match &scene
        .entities
        .get(id)
        .ok_or_else(|| SceneError(format!("unknown object: {id}")))?
        .content
    {
        EntityKind::Mesh {
            geometry: Geometry::Asset { id },
            ..
        } => Ok(id),
        _ => Err(SceneError("object requires a shared mesh asset".into())),
    }
}

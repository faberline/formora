//! Owned scene data with atomic typed updates and private validation proofs.
use crate::mesh::MeshAsset;
use crate::scene::{Annotation, Door, Entity, Material, Result, Scene, SceneError, Transform};
use std::collections::BTreeMap;
use std::sync::Arc;

/// Opaque identity for one core-owned value. Compare stamps; never construct them.
/// A submitted value receives a fresh stamp even if its fields compare equal.
#[derive(Clone, Debug)]
pub struct ValueStamp(Arc<()>);
impl PartialEq for ValueStamp {
    fn eq(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.0, &other.0)
    }
}
impl Eq for ValueStamp {}
impl ValueStamp {
    fn new() -> Self {
        Self(Arc::new(()))
    }
}

/// Atomic changes. Map values of None remove entries. Transforms apply after entity
/// replacements. Outer settings None leaves the setting unchanged.
#[derive(Default)]
pub struct SceneUpdate {
    pub entities: BTreeMap<String, Option<Entity>>,
    pub transforms: BTreeMap<String, Transform>,
    pub mesh_assets: BTreeMap<String, Option<MeshAsset>>,
    pub materials: BTreeMap<String, Option<Material>>,
    pub schema_version: Option<u32>,
    pub revision: Option<u64>,
    pub time_seconds: Option<f64>,
    pub doors: Option<BTreeMap<String, Door>>,
    pub active_camera: Option<Option<String>>,
    pub annotations: Option<Vec<Annotation>>,
    pub authoring_context: Option<Option<crate::mesh::creation::AuthoringContext>>,
    pub object_context: Option<Option<crate::objects::Context>>,
}

/// Validated ownership boundary. No mutable Scene reference escapes this type.
/// This type deliberately does not implement Clone or Deserialize.
pub struct SceneStore {
    scene: Scene,
    entities: BTreeMap<String, ValueStamp>,
    mesh_assets: BTreeMap<String, ValueStamp>,
    materials: BTreeMap<String, ValueStamp>,
    settings: ValueStamp,
    stamp: ValueStamp,
}
fn stamps<T>(values: &BTreeMap<String, T>) -> BTreeMap<String, ValueStamp> {
    values
        .keys()
        .map(|id| (id.clone(), ValueStamp::new()))
        .collect()
}
// Move old payloads into the undo map. In particular, do not clone mesh assets.
fn swap_entries<T>(values: &mut BTreeMap<String, T>, changes: &mut BTreeMap<String, Option<T>>) {
    for (id, value) in changes {
        let old = match value.take() {
            Some(new) => values.insert(id.clone(), new),
            None => values.remove(id),
        };
        *value = old;
    }
}
fn refresh<T>(
    values: &BTreeMap<String, T>,
    changed: &BTreeMap<String, Option<T>>,
    tokens: &mut BTreeMap<String, ValueStamp>,
) {
    for id in changed.keys() {
        if values.contains_key(id) {
            tokens.insert(id.clone(), ValueStamp::new());
        } else {
            tokens.remove(id);
        }
    }
}
impl SceneStore {
    /// Validate every input value before taking ownership.
    pub fn new(scene: Scene) -> Result<Self> {
        scene.validate()?;
        Ok(Self {
            entities: stamps(&scene.entities),
            mesh_assets: stamps(&scene.mesh_assets),
            materials: stamps(&scene.materials),
            scene,
            settings: ValueStamp::new(),
            stamp: ValueStamp::new(),
        })
    }
    pub fn scene(&self) -> &Scene {
        &self.scene
    }
    pub fn into_scene(self) -> Scene {
        self.scene
    }
    pub fn stamp(&self) -> ValueStamp {
        self.stamp.clone()
    }
    pub fn settings_stamp(&self) -> ValueStamp {
        self.settings.clone()
    }
    pub fn entity_stamp(&self, id: &str) -> Option<ValueStamp> {
        self.entities.get(id).cloned()
    }
    pub fn mesh_stamp(&self, id: &str) -> Option<ValueStamp> {
        self.mesh_assets.get(id).cloned()
    }
    pub fn material_stamp(&self, id: &str) -> Option<ValueStamp> {
        self.materials.get(id).cloned()
    }
    /// A failed load keeps all old data and stamps.
    pub fn replace_all(&mut self, scene: Scene) -> Result<()> {
        let replacement = Self::new(scene)?;
        *self = replacement;
        Ok(())
    }
    /// Recheck all cross-field rules. Only immutable, owned mesh validation can be reused.
    pub(crate) fn validate_for_prepare(&self) -> Result<()> {
        self.scene.validate_with_mesh_assets(|_, asset| {
            if asset.recipe.is_some() || asset.vertex_weights.is_some() {
                asset.validate()
            } else {
                Ok(())
            }
        })
    }
    /// Apply one validated transaction. A nonempty accepted batch gets fresh stamps.
    /// Revision is ordinary scene data. It is neither trusted nor implicitly changed.
    pub fn apply(&mut self, mut update: SceneUpdate) -> Result<bool> {
        for (id, transform) in std::mem::take(&mut update.transforms) {
            if !update.entities.contains_key(&id) {
                let entity = self
                    .scene
                    .entities
                    .get(&id)
                    .ok_or_else(|| SceneError(format!("missing transform entity: {id}")))?
                    .clone();
                update.entities.insert(id.clone(), Some(entity));
            }
            let entity = update
                .entities
                .get_mut(&id)
                .and_then(Option::as_mut)
                .ok_or_else(|| SceneError(format!("missing transform entity: {id}")))?;
            entity.transform = transform;
        }
        let settings_changed = update.schema_version.is_some()
            || update.revision.is_some()
            || update.time_seconds.is_some()
            || update.doors.is_some()
            || update.active_camera.is_some()
            || update.annotations.is_some()
            || update.authoring_context.is_some()
            || update.object_context.is_some();
        if update.entities.is_empty()
            && update.mesh_assets.is_empty()
            && update.materials.is_empty()
            && !settings_changed
        {
            return Ok(false);
        }
        swap_entries(&mut self.scene.entities, &mut update.entities);
        swap_entries(&mut self.scene.mesh_assets, &mut update.mesh_assets);
        swap_entries(&mut self.scene.materials, &mut update.materials);
        if let Some(value) = &mut update.schema_version {
            std::mem::swap(value, &mut self.scene.schema_version);
        }
        if let Some(value) = &mut update.revision {
            std::mem::swap(value, &mut self.scene.revision);
        }
        if let Some(value) = &mut update.time_seconds {
            std::mem::swap(value, &mut self.scene.time_seconds);
        }
        if let Some(value) = &mut update.doors {
            std::mem::swap(value, &mut self.scene.doors);
        }
        if let Some(value) = &mut update.active_camera {
            std::mem::swap(value, &mut self.scene.active_camera);
        }
        if let Some(value) = &mut update.annotations {
            std::mem::swap(value, &mut self.scene.annotations);
        }
        if let Some(value) = &mut update.authoring_context {
            std::mem::swap(value, &mut self.scene.authoring_context);
        }
        if let Some(value) = &mut update.object_context {
            std::mem::swap(value, &mut self.scene.object_context);
        }
        let result = self.scene.validate_with_mesh_assets(|id, asset| {
            if update.mesh_assets.contains_key(id)
                || asset.recipe.is_some()
                || asset.vertex_weights.is_some()
            {
                asset.validate()
            } else {
                Ok(())
            }
        });
        if let Err(error) = result {
            swap_entries(&mut self.scene.entities, &mut update.entities);
            swap_entries(&mut self.scene.mesh_assets, &mut update.mesh_assets);
            swap_entries(&mut self.scene.materials, &mut update.materials);
            if let Some(value) = &mut update.schema_version {
                std::mem::swap(value, &mut self.scene.schema_version);
            }
            if let Some(value) = &mut update.revision {
                std::mem::swap(value, &mut self.scene.revision);
            }
            if let Some(value) = &mut update.time_seconds {
                std::mem::swap(value, &mut self.scene.time_seconds);
            }
            if let Some(value) = &mut update.doors {
                std::mem::swap(value, &mut self.scene.doors);
            }
            if let Some(value) = &mut update.active_camera {
                std::mem::swap(value, &mut self.scene.active_camera);
            }
            if let Some(value) = &mut update.annotations {
                std::mem::swap(value, &mut self.scene.annotations);
            }
            if let Some(value) = &mut update.authoring_context {
                std::mem::swap(value, &mut self.scene.authoring_context);
            }
            if let Some(value) = &mut update.object_context {
                std::mem::swap(value, &mut self.scene.object_context);
            }
            return Err(error);
        }
        refresh(&self.scene.entities, &update.entities, &mut self.entities);
        refresh(
            &self.scene.mesh_assets,
            &update.mesh_assets,
            &mut self.mesh_assets,
        );
        refresh(
            &self.scene.materials,
            &update.materials,
            &mut self.materials,
        );
        if settings_changed {
            self.settings = ValueStamp::new();
        }
        self.stamp = ValueStamp::new();
        Ok(true)
    }
}

//! Shared, locked, persist-on-success operations for agent interfaces.
use crate::scene::{Command, Editor, Result, Scene, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{File, OpenOptions};
use std::path::{Path, PathBuf};

#[derive(Debug, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ApplyRequest {
    pub expected_revision: u64,
    pub commands: Vec<Command>,
}

#[derive(Debug, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct UndoRequest {
    pub expected_revision: u64,
}

#[derive(Debug, Serialize)]
pub struct ApplyResult {
    pub revision: u64,
    #[serde(skip_serializing_if = "BTreeMap::is_empty")]
    pub generation_diagnostics: BTreeMap<String, Vec<String>>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub selection: Vec<crate::mesh::selection::CommandOutcome>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub creation: Vec<crate::mesh::creation::CreationReceipt>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub transforms: Vec<crate::mesh::transform::Receipt>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub snaps: Vec<crate::mesh::snap::Receipt>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub scene_snaps: Vec<crate::objects::snap::Receipt>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub merges: Vec<crate::mesh::merge::Receipt>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub edit_merges: Vec<crate::mesh::merge::context::Receipt>,
}

#[derive(Debug, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct InspectRequest {
    pub entity: Option<String>,
    pub mesh_asset: Option<String>,
    #[serde(default)]
    pub tessellate: bool,
    #[serde(default)]
    pub selection_topology: bool,
    #[serde(default)]
    pub normals: bool,
    #[serde(default)]
    pub world: bool,
    #[serde(default)]
    pub object_state: bool,
}

#[derive(Serialize)]
struct FullInspection<'a> {
    revision: u64,
    scene: &'a Scene,
    #[serde(skip_serializing_if = "Option::is_none")]
    cursor_matrix: Option<[[f64; 4]; 4]>,
}
fn full_inspection(scene: &Scene) -> Result<FullInspection<'_>> {
    let cursor_matrix = scene
        .authoring_context
        .as_ref()
        .filter(|c| c.cursor_orientation.is_some())
        .map(|c| c.cursor_world_matrix())
        .transpose()?;
    Ok(FullInspection {
        revision: scene.revision,
        scene,
        cursor_matrix,
    })
}

impl InspectRequest {
    /// Serialize a full read without constructing a second owned scene tree.
    /// Filtered reads retain exactly the existing inspect validation and values.
    pub fn write_json(&self, scene: &Scene, output: impl std::io::Write) -> Result<()> {
        if self.entity.is_none()
            && self.mesh_asset.is_none()
            && !self.tessellate
            && !self.selection_topology
            && !self.normals
            && !self.world
            && !self.object_state
        {
            serde_json::to_writer(output, &full_inspection(scene)?)
                .map_err(|e| SceneError(e.to_string()))
        } else {
            serde_json::to_writer(output, &self.inspect(scene)?)
                .map_err(|e| SceneError(e.to_string()))
        }
    }

    /// The CLI can inspect a saved scene without taking the writer lock.
    pub fn inspect(&self, scene: &Scene) -> Result<serde_json::Value> {
        if self.object_state {
            if self.entity.is_none()
                || self.mesh_asset.is_some()
                || self.world
                || self.tessellate
                || self.selection_topology
                || self.normals
            {
                return Err(SceneError(
                    "object state query requires only an entity".into(),
                ));
            }
            let id = self.entity.as_ref().unwrap();
            let entity = scene
                .entities
                .get(id)
                .ok_or_else(|| SceneError(format!("unknown entity: {id}")))?;
            let state = scene
                .object_context
                .as_ref()
                .map(|c| c.state(id))
                .unwrap_or_default();
            let mut value = serde_json::to_value(&state).map_err(|e| SceneError(e.to_string()))?;
            // Stored default flags remain omitted for compatibility. The explicit
            // metadata query must report the actual value even without a context.
            value["lock_scale"] = serde_json::json!(state.lock_scale);
            return Ok(
                serde_json::json!({"revision":scene.revision,"id":id,"entity":entity,"object_state":value}),
            );
        }
        if self.world {
            if self.entity.is_none()
                || self.mesh_asset.is_some()
                || self.tessellate
                || self.selection_topology
                || self.normals
            {
                return Err(SceneError("world query requires only an entity".into()));
            }
            let id = self.entity.as_ref().unwrap();
            let entity = scene
                .entities
                .get(id)
                .ok_or_else(|| SceneError(format!("unknown entity: {id}")))?;
            let matrix = crate::transforms::world(scene, id)?;
            let mut result = serde_json::json!({"revision":scene.revision,"id":id,"entity":entity,"world_matrix":matrix});
            if scene.object_context.is_some() {
                result["object_frames"] = serde_json::to_value(crate::objects::frames(scene, id)?)
                    .map_err(|e| SceneError(e.to_string()))?;
            }
            if let crate::scene::EntityKind::Mesh { geometry, .. } = &entity.content {
                let vertices: BTreeMap<String, [f64; 3]> = match geometry {
                    crate::scene::Geometry::Asset { id } => scene
                        .mesh_assets
                        .get(id)
                        .ok_or_else(|| SceneError(format!("unknown mesh asset: {id}")))?
                        .vertices
                        .clone(),
                    crate::scene::Geometry::Cube { size } => (0..8)
                        .map(|i| {
                            (
                                format!("builtin_v{i:06}"),
                                std::array::from_fn(|j| {
                                    size[j] * if i & (1 << j) == 0 { -0.5 } else { 0.5 }
                                }),
                            )
                        })
                        .collect(),
                    crate::scene::Geometry::Plane { size } => (0..4)
                        .map(|i| {
                            (
                                format!("builtin_v{i:06}"),
                                [
                                    size[0] * if i & 1 == 0 { -0.5 } else { 0.5 },
                                    size[1] * if i & 2 == 0 { -0.5 } else { 0.5 },
                                    0.,
                                ],
                            )
                        })
                        .collect(),
                };
                let vertices: BTreeMap<_, _> = vertices
                    .into_iter()
                    .map(|(id, p)| {
                        Ok((
                            id,
                            crate::transforms::point(matrix, p, entity.transform.precision)?,
                        ))
                    })
                    .collect::<Result<_>>()?;
                result["world_vertices"] =
                    serde_json::to_value(vertices).map_err(|e| SceneError(e.to_string()))?;
            }
            return Ok(result);
        }
        if self.tessellate && (self.mesh_asset.is_none() || self.entity.is_some()) {
            return Err(SceneError("tessellate requires only mesh_asset".into()));
        }
        if self.selection_topology && (self.mesh_asset.is_none() || self.entity.is_some()) {
            return Err(SceneError(
                "selection_topology requires only mesh_asset".into(),
            ));
        }
        if self.normals && (self.mesh_asset.is_none() || self.entity.is_some()) {
            return Err(SceneError("normals requires only mesh_asset".into()));
        }
        if self.tessellate || self.selection_topology || self.normals {
            let id = self.mesh_asset.as_ref().expect("checked mesh asset");
            let asset = scene
                .mesh_assets
                .get(id)
                .ok_or_else(|| SceneError(format!("unknown mesh asset: {id}")))?;
            let mut result =
                serde_json::json!({"revision":scene.revision,"id":id,"mesh_asset":asset});
            if self.tessellate {
                result["tessellation"] = serde_json::to_value(asset.tessellate()?)
                    .map_err(|e| SceneError(e.to_string()))?;
            }
            if self.selection_topology {
                result["selection_topology"] =
                    serde_json::to_value(crate::mesh::selection::topology(asset)?)
                        .map_err(|e| SceneError(e.to_string()))?;
            }
            if self.normals {
                result["normals"] = serde_json::to_value(crate::mesh::normals::resolved(asset)?)
                    .map_err(|e| SceneError(e.to_string()))?;
            }
            return Ok(result);
        }
        match (&self.entity, &self.mesh_asset) {
            (Some(_), Some(_)) => Err(SceneError("inspect accepts either entity or mesh_asset".into())),
            (Some(id), None) => scene.entities.get(id).map(|entity| serde_json::json!({"revision":scene.revision,"id":id,"entity":entity})).ok_or_else(|| SceneError(format!("unknown entity: {id}"))),
            (None, Some(id)) => scene.mesh_assets.get(id).map(|asset| serde_json::json!({"revision":scene.revision,"id":id,"mesh_asset":asset})).ok_or_else(|| SceneError(format!("unknown mesh asset: {id}"))),
            (None, None) => {
                serde_json::to_value(full_inspection(scene)?).map_err(|e| SceneError(e.to_string()))
            },
        }
    }
}

pub struct Session {
    editor: Editor,
    path: PathBuf,
    _lock: File,
}

impl Drop for Session {
    fn drop(&mut self) {
        // A concurrent fork may keep an inherited descriptor alive until exec.
        // Release ownership explicitly instead of waiting for its last close.
        let _ = fs2::FileExt::unlock(&self._lock);
    }
}

fn lock_path(path: &Path) -> Result<(PathBuf, File)> {
    let path = if path.exists() {
        path.canonicalize().map_err(|e| SceneError(e.to_string()))?
    } else {
        let parent = path
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        parent
            .canonicalize()
            .map_err(|e| SceneError(e.to_string()))?
            .join(
                path.file_name()
                    .ok_or_else(|| SceneError("scene path needs a filename".into()))?,
            )
    };
    let name = path
        .file_name()
        .ok_or_else(|| SceneError("scene path needs a filename".into()))?
        .to_string_lossy();
    let lock = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path.with_file_name(format!(".{name}.formora.lock")))
        .map_err(|e| SceneError(e.to_string()))?;
    fs2::FileExt::try_lock_exclusive(&lock)
        .map_err(|e| SceneError(format!("cannot lock scene for writing: {e}")))?;
    Ok((path, lock))
}

impl Session {
    pub fn open(path: &Path) -> Result<Self> {
        let (path, lock) = lock_path(path)?;
        let editor = Editor::new(Scene::load(&path)?)?;
        Ok(Self {
            editor,
            path,
            _lock: lock,
        })
    }

    pub fn create(path: &Path, scene: Scene) -> Result<Self> {
        let (path, lock) = lock_path(path)?;
        if path.exists() {
            return Err(SceneError(
                "scene already exists; initialization never overwrites a scene".into(),
            ));
        }
        let editor = Editor::new(scene)?;
        editor.scene().save(&path)?;
        Ok(Self {
            editor,
            path,
            _lock: lock,
        })
    }

    pub fn scene(&self) -> &Scene {
        self.editor.scene()
    }

    pub fn inspect(&self, request: InspectRequest) -> Result<serde_json::Value> {
        request.inspect(self.scene())
    }

    pub fn apply(&mut self, request: ApplyRequest) -> Result<u64> {
        let mut candidate = self.editor.clone();
        let revision = candidate.apply(&request.commands, Some(request.expected_revision))?;
        candidate.scene().save(&self.path)?;
        self.editor = candidate;
        Ok(revision)
    }

    /// Return warnings only after the successful batch has been saved.
    pub fn apply_with_result(&mut self, request: ApplyRequest) -> Result<ApplyResult> {
        let mut generated: BTreeSet<_> = request
            .commands
            .iter()
            .filter_map(|command| match command {
                Command::CreateMeshPrimitive { id, .. }
                | Command::RegenerateMeshPrimitive { id, .. } => Some(id.clone()),
                _ => None,
            })
            .collect();
        let mut candidate = self.editor.clone();
        let applied =
            candidate.apply_with_outcomes(&request.commands, Some(request.expected_revision))?;
        generated.extend(
            applied
                .creation
                .iter()
                .map(|receipt| receipt.mesh_asset.clone()),
        );
        candidate.scene().save(&self.path)?;
        self.editor = candidate;
        let generation_diagnostics = generated
            .into_iter()
            .filter_map(|id| {
                self.scene()
                    .mesh_assets
                    .get(&id)
                    .filter(|asset| !asset.diagnostics.is_empty())
                    .map(|asset| (id, asset.diagnostics.clone()))
            })
            .collect();
        Ok(ApplyResult {
            revision: applied.revision,
            generation_diagnostics,
            selection: applied.selection,
            creation: applied.creation,
            transforms: applied.transforms,
            snaps: applied.snaps,
            scene_snaps: applied.scene_snaps,
            merges: applied.merges,
            edit_merges: applied.edit_merges,
        })
    }

    pub fn undo(&mut self, request: UndoRequest) -> Result<u64> {
        let mut candidate = self.editor.clone();
        let revision = candidate.undo(Some(request.expected_revision))?;
        candidate.scene().save(&self.path)?;
        self.editor = candidate;
        Ok(revision)
    }
}

#[cfg(test)]
mod inspect_serialization_tests {
    use super::*;
    #[test]
    fn direct_json_equals_inspection_values_and_errors() {
        let scene = Scene {
            revision: 17,
            ..Scene::default()
        };
        let request: ApplyRequest =
            serde_json::from_str(include_str!("../baseline/static-usd/rock/create.json")).unwrap();
        let mut editor = Editor::new(scene).unwrap();
        editor.apply(&request.commands, Some(17)).unwrap();
        let scene = editor.scene();
        for request in [
            InspectRequest::default(),
            InspectRequest {
                entity: Some("rock".into()),
                ..InspectRequest::default()
            },
            InspectRequest {
                entity: Some("absent".into()),
                ..InspectRequest::default()
            },
            InspectRequest {
                world: true,
                ..InspectRequest::default()
            },
        ] {
            let expected = request.inspect(scene);
            let mut bytes = Vec::new();
            match expected {
                Ok(expected) => {
                    request.write_json(scene, &mut bytes).unwrap();
                    let actual: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
                    assert_eq!(actual, expected);
                    if request.entity.is_none() && !request.world {
                        assert_eq!(actual["revision"], 18);
                        assert_eq!(actual["scene"], serde_json::to_value(scene).unwrap());
                        assert!(actual.get("cursor_matrix").is_none());
                    }
                }
                Err(expected) => assert_eq!(
                    request.write_json(scene, &mut bytes).unwrap_err().0,
                    expected.0
                ),
            }
        }
        let mut scene = scene.clone();
        scene.authoring_context = Some(crate::mesh::creation::AuthoringContext {
            cursor_location: [0.125, -0.25, 0.5],
            cursor_orientation: Some(crate::rotation::Channels::from_rotation(
                crate::rotation::TransformRotation::Quaternion([0., 0., 0., 1.]),
            )),
            ..crate::mesh::creation::AuthoringContext::default()
        });
        scene.validate().unwrap();
        let request = InspectRequest::default();
        let mut bytes = Vec::new();
        request.write_json(&scene, &mut bytes).unwrap();
        let actual: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(actual, request.inspect(&scene).unwrap());
        assert_eq!(
            actual["cursor_matrix"],
            serde_json::json!([
                [1., 0., 0., 0.125],
                [0., 1., 0., -0.25],
                [0., 0., 1., 0.5],
                [0., 0., 0., 1.]
            ])
        );
    }
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;

    #[test]
    fn closing_session_releases_lock_even_if_a_child_inherited_its_descriptor() {
        let root = std::env::temp_dir().join(format!(
            "formora-inherited-lock-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("scene.json");
        let session = Session::create(&path, Scene::default()).unwrap();
        // dup shares an open-file description, just as the fork/exec window does.
        let inherited = session._lock.try_clone().unwrap();
        drop(session);
        let next =
            Session::open(&path).expect("the ended session must release ownership immediately");
        drop(next);
        drop(inherited);
        std::fs::remove_dir_all(root).unwrap();
    }
}

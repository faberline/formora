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
}

impl InspectRequest {
    /// The CLI can inspect a saved scene without taking the writer lock.
    pub fn inspect(&self, scene: &Scene) -> Result<serde_json::Value> {
        if self.tessellate && (self.mesh_asset.is_none() || self.entity.is_some()) {
            return Err(SceneError("tessellate requires only mesh_asset".into()));
        }
        if self.selection_topology && (self.mesh_asset.is_none() || self.entity.is_some()) {
            return Err(SceneError(
                "selection_topology requires only mesh_asset".into(),
            ));
        }
        if self.tessellate || self.selection_topology {
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
            return Ok(result);
        }
        match (&self.entity, &self.mesh_asset) {
            (Some(_), Some(_)) => Err(SceneError("inspect accepts either entity or mesh_asset".into())),
            (Some(id), None) => scene.entities.get(id).map(|entity| serde_json::json!({"revision":scene.revision,"id":id,"entity":entity})).ok_or_else(|| SceneError(format!("unknown entity: {id}"))),
            (None, Some(id)) => scene.mesh_assets.get(id).map(|asset| serde_json::json!({"revision":scene.revision,"id":id,"mesh_asset":asset})).ok_or_else(|| SceneError(format!("unknown mesh asset: {id}"))),
            (None, None) => Ok(serde_json::json!({"revision":scene.revision,"scene":scene})),
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

//! Shared, locked, persist-on-success operations for agent interfaces.
use crate::scene::{Command, Editor, Result, Scene, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
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

#[derive(Debug, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct InspectRequest {
    pub entity: Option<String>,
    pub mesh_asset: Option<String>,
}

impl InspectRequest {
    /// The CLI can inspect a saved scene without taking the writer lock.
    pub fn inspect(&self, scene: &Scene) -> Result<serde_json::Value> {
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

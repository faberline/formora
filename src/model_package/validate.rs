use super::*;
use crate::scene::{EntityKind, Geometry, Scene};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug)]
pub struct PreparedPackage {
    pub manifest: Manifest,
    pub counts: Counts,
    pub manifest_sha256: String,
    pub scene_sha256: String,
    pub(crate) manifest_bytes: Vec<u8>,
    pub(crate) scene_bytes: Vec<u8>,
}

pub(crate) fn parse_manifest(bytes: &[u8], expected: &str) -> Result<(Manifest, String), Failure> {
    let observed = sha256(bytes);
    let fail = |code, stage, message: String| {
        let mut error = Failure::new(code, stage, message);
        error.observed_manifest_sha256 = Some(observed.clone());
        error
    };
    if !valid_hash(expected) {
        return Err(fail(
            ErrorCode::InvalidRequest,
            Stage::Request,
            "Expected manifest hash must be 64 lowercase hexadecimal digits".into(),
        ));
    }
    if expected != observed {
        return Err(fail(
            ErrorCode::HashMismatch,
            Stage::ManifestHash,
            "Manifest bytes differ from the selected manifest hash".into(),
        ));
    }
    let value = crate::json::value_from_slice(bytes)
        .map_err(|e| fail(ErrorCode::InvalidManifest, Stage::Manifest, e.to_string()))?;
    let manifest: Manifest = serde_json::from_value(value)
        .map_err(|e| fail(ErrorCode::InvalidManifest, Stage::Manifest, e.to_string()))?;
    if manifest.manifest_schema_version != 1 || manifest.scene_schema_version != 1 {
        return Err(fail(
            ErrorCode::UnsupportedSchema,
            Stage::Profile,
            "Only manifest and native scene schema 1 are supported".into(),
        ));
    }
    if manifest.scene_profile != PROFILE {
        return Err(fail(
            ErrorCode::UnsupportedProfile,
            Stage::Profile,
            "This validator supports only the static main triangle profile".into(),
        ));
    }
    if manifest.producer_commit != PRODUCER {
        return Err(fail(
            ErrorCode::UnsupportedProducer,
            Stage::Profile,
            "Producer revision is outside this profile's compatibility set".into(),
        ));
    }
    if manifest.meters_per_unit != 1.0
        || manifest.up_axis != "Z"
        || manifest.coordinate_system != "right_handed"
    {
        return Err(fail(
            ErrorCode::UnsupportedUnits,
            Stage::Profile,
            "This profile requires explicit metres, right-handed coordinates, and Z-up".into(),
        ));
    }
    if manifest.scene_file != "model.scene.json" || !valid_hash(&manifest.scene_sha256) {
        return Err(fail(
            ErrorCode::InvalidManifest,
            Stage::Manifest,
            "scene_file must be model.scene.json with a lowercase SHA-256".into(),
        ));
    }
    if !manifest.display_exports.is_empty() {
        return Err(fail(ErrorCode::UnsupportedFeature, Stage::Profile, "Display exports require a later validated profile; this slice accepts source JSON only".into()));
    }
    if manifest.roots.is_empty()
        || manifest.roots.iter().collect::<BTreeSet<_>>().len() != manifest.roots.len()
    {
        return Err(fail(
            ErrorCode::InvalidRoots,
            Stage::Manifest,
            "Model roots must be nonempty and distinct".into(),
        ));
    }
    if manifest.capabilities.iter().collect::<BTreeSet<_>>().len() != manifest.capabilities.len() {
        return Err(fail(
            ErrorCode::InvalidManifest,
            Stage::Manifest,
            "Capabilities must be distinct".into(),
        ));
    }
    Ok((manifest, observed))
}

/// Validate independent byte inputs. No files, processes, GPU, or game state are accessed.
pub fn validate_bytes(
    manifest_bytes: &[u8],
    expected: &str,
    scene_bytes: &[u8],
) -> Result<PreparedPackage, Failure> {
    let (manifest, manifest_hash) = parse_manifest(manifest_bytes, expected)?;
    let scene_hash = sha256(scene_bytes);
    let fail = |code, stage, message: String| {
        let mut error = Failure::new(code, stage, message);
        error.observed_manifest_sha256 = Some(manifest_hash.clone());
        error.observed_scene_sha256 = Some(scene_hash.clone());
        error
    };
    if scene_hash != manifest.scene_sha256 {
        return Err(fail(
            ErrorCode::HashMismatch,
            Stage::SceneHash,
            "Scene bytes differ from the manifest hash".into(),
        ));
    }
    let value = crate::json::value_from_slice(scene_bytes)
        .map_err(|e| fail(ErrorCode::InvalidScene, Stage::Scene, e.to_string()))?;
    let scene: Scene = serde_json::from_value(value)
        .map_err(|e| fail(ErrorCode::InvalidScene, Stage::Scene, e.to_string()))?;
    scene
        .validate()
        .map_err(|e| fail(ErrorCode::InvalidScene, Stage::Scene, e.to_string()))?;
    if scene.time_seconds != 0.0
        || !scene.doors.is_empty()
        || scene.active_camera.is_some()
        || !scene.annotations.is_empty()
    {
        return Err(fail(
            ErrorCode::UnsupportedSceneState,
            Stage::Profile,
            "Static model packages do not contain playback, doors, cameras, or annotations".into(),
        ));
    }

    let mut children: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for (id, entity) in &scene.entities {
        if let Some(parent) = &entity.parent {
            children.entry(parent).or_default().push(id);
        }
    }
    let mut selected = BTreeSet::new();
    let mut pending = Vec::new();
    for root in &manifest.roots {
        let entity = scene.entities.get(root).ok_or_else(|| {
            fail(
                ErrorCode::InvalidRoots,
                Stage::Closure,
                format!("Missing model root: {root}"),
            )
        })?;
        if entity.parent.is_some() {
            return Err(fail(
                ErrorCode::InvalidRoots,
                Stage::Closure,
                format!("Model root must be top-level: {root}"),
            ));
        }
        pending.push(root.as_str());
    }
    while let Some(id) = pending.pop() {
        if selected.insert(id) {
            if let Some(items) = children.get(id) {
                pending.extend(items);
            }
        }
    }
    if selected != scene.entities.keys().map(String::as_str).collect() {
        return Err(fail(
            ErrorCode::ClosureMismatch,
            Stage::Closure,
            "Scene contains entities outside the declared roots".into(),
        ));
    }
    let mut meshes = BTreeSet::new();
    let mut materials = BTreeSet::new();
    let mut capabilities = BTreeSet::from([Capability::TriangleMeshes]);
    for entity in scene.entities.values() {
        if entity.parent.is_some() {
            capabilities.insert(Capability::Hierarchy);
        }
        match &entity.content {
            EntityKind::Empty => {}
            EntityKind::Mesh {
                geometry: Geometry::Asset { id },
                material,
            } => {
                meshes.insert(id.as_str());
                if let Some(material) = material {
                    materials.insert(material.as_str());
                }
            }
            _ => {
                return Err(fail(
                    ErrorCode::UnsupportedFeature,
                    Stage::Profile,
                    "Only empty entities and asset mesh entities are supported".into(),
                ));
            }
        }
    }
    if meshes != scene.mesh_assets.keys().map(String::as_str).collect() {
        return Err(fail(
            ErrorCode::ClosureMismatch,
            Stage::Closure,
            "Scene mesh assets must match the full model resource closure".into(),
        ));
    }
    let mut counts = Counts {
        entities: scene.entities.len(),
        mesh_assets: scene.mesh_assets.len(),
        materials: scene.materials.len(),
        ..Counts::default()
    };
    for mesh in scene.mesh_assets.values() {
        counts.vertices += mesh.vertices.len();
        counts.triangles += mesh.triangles.len();
        for material in mesh.material_slots.iter().flatten() {
            materials.insert(material.as_str());
        }
        for triangle in mesh.triangles.values() {
            if !triangle.uv_layers.is_empty() {
                capabilities.insert(Capability::CornerUvs);
            }
            if triangle.corner_normals.is_some() {
                capabilities.insert(Capability::CornerNormals);
            }
        }
    }
    if materials != scene.materials.keys().map(String::as_str).collect() {
        return Err(fail(
            ErrorCode::ClosureMismatch,
            Stage::Closure,
            "Scene materials must include all and only entity and slot references".into(),
        ));
    }
    if counts.triangles == 0 {
        return Err(fail(
            ErrorCode::UnsupportedFeature,
            Stage::Profile,
            "A model package needs a referenced triangle mesh".into(),
        ));
    }
    if !materials.is_empty() {
        capabilities.insert(Capability::SolidColorMaterials);
    }
    if capabilities != manifest.capabilities.iter().cloned().collect() {
        return Err(fail(
            ErrorCode::UnsupportedFeature,
            Stage::Profile,
            "Declared capabilities differ from the actual source features".into(),
        ));
    }
    Ok(PreparedPackage {
        manifest,
        counts,
        manifest_sha256: manifest_hash,
        scene_sha256: scene_hash,
        manifest_bytes: manifest_bytes.to_vec(),
        scene_bytes: scene_bytes.to_vec(),
    })
}

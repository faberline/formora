use super::*;
use formora_native_bb025::scene::{EntityKind, Geometry, Scene};
use std::collections::{BTreeMap, BTreeSet};

pub struct PreparedProject {
    pub(crate) project: Project,
    pub(crate) scene: Scene,
    pub(crate) project_bytes: Vec<u8>,
    pub(crate) files: BTreeMap<String, Vec<u8>>,
    pub(crate) decoded: BTreeMap<String, image::Image>,
}

pub(crate) fn parse_project(bytes: &[u8], expected: &str) -> Result<Project, Failure> {
    if !valid_hash(expected) {
        return Err(Failure::new(
            ErrorCode::InvalidRequest,
            "request",
            "Expected project hash must be 64 lowercase hex digits",
        ));
    }
    if sha256(bytes) != expected {
        return Err(Failure::new(
            ErrorCode::HashMismatch,
            "project_hash",
            "Project bytes differ from the selected hash",
        ));
    }
    let p: Project = serde_json::from_value(
        crate::json::value_from_slice(bytes)
            .map_err(|e| Failure::new(ErrorCode::InvalidProject, "project", e))?,
    )
    .map_err(|e| Failure::new(ErrorCode::InvalidProject, "project", e))?;
    if p.project_schema_version != 1
        || p.project_profile != PROJECT_PROFILE
        || ![SOURCE_PROFILE, SOURCE_PROFILE_V2].contains(&p.scene_profile.as_str())
    {
        return Err(Failure::new(
            ErrorCode::UnsupportedProfile,
            "project",
            "Unsupported project schema or source profile",
        ));
    }
    if p.producer_commit != PRODUCER {
        return Err(Failure::new(
            ErrorCode::UnsupportedProducer,
            "project",
            "Only the exact bb025 source producer is admitted",
        ));
    }
    resource_path(&p.scene.path)?;
    if !valid_hash(&p.scene.sha256)
        || p.roots.is_empty()
        || p.roots.iter().collect::<BTreeSet<_>>().len() != p.roots.len()
    {
        return Err(Failure::new(
            ErrorCode::InvalidProject,
            "project",
            "Require a scene hash and distinct nonempty roots",
        ));
    }
    if p.images.is_empty() || p.bindings.is_empty() {
        return Err(Failure::new(
            ErrorCode::InvalidBinding,
            "project",
            "Require at least one image and material binding",
        ));
    }
    let mut paths = BTreeSet::from([p.scene.path.as_str()]);
    for (id, image) in &p.images {
        resource_path(&image.path)?;
        if id.is_empty()
            || !valid_hash(&image.sha256)
            || image.color_space != "srgb"
            || !paths.insert(&image.path)
        {
            return Err(Failure::new(
                ErrorCode::InvalidProject,
                "project",
                "Images require distinct paths, IDs, hashes and explicit srgb",
            ));
        }
    }
    for path in &paths {
        if paths
            .iter()
            .any(|other| other.starts_with(&format!("{path}/")))
        {
            return Err(Failure::new(
                ErrorCode::InvalidPath,
                "project",
                "A resource file cannot also be a directory",
            ));
        }
    }
    for binding in p.bindings.values() {
        if !p.images.contains_key(&binding.image)
            || binding.uv_layer.is_empty()
            || binding.filter != "nearest"
            || binding.address_mode != "clamp_to_edge"
        {
            return Err(Failure::new(
                ErrorCode::InvalidBinding,
                "project",
                "Require an image, named UV layer, nearest and clamp_to_edge",
            ));
        }
    }
    let used: BTreeSet<_> = p.bindings.values().map(|b| b.image.as_str()).collect();
    if used != p.images.keys().map(String::as_str).collect() {
        return Err(Failure::new(
            ErrorCode::ClosureMismatch,
            "project",
            "Image set must equal binding references",
        ));
    }
    Ok(p)
}

/// Validate raw resources in memory. No filesystem, subprocess or GPU access.
pub fn validate_bytes(
    project_bytes: &[u8],
    expected: &str,
    files: &BTreeMap<String, Vec<u8>>,
) -> Result<PreparedProject, Failure> {
    let result = (|| {
        let project = parse_project(project_bytes, expected)?;
        let source = files.get(&project.scene.path).ok_or_else(|| {
            Failure::new(
                ErrorCode::SceneMissing,
                "scene",
                "Source resource is missing",
            )
        })?;
        if sha256(source) != project.scene.sha256 {
            return Err(Failure::new(
                ErrorCode::HashMismatch,
                "scene_hash",
                "Source bytes differ from the project hash",
            ));
        }
        let wanted: BTreeSet<_> = std::iter::once(&project.scene.path)
            .chain(project.images.values().map(|i| &i.path))
            .collect();
        if files.keys().any(|name| !wanted.contains(name)) {
            return Err(Failure::new(
                ErrorCode::ClosureMismatch,
                "resources",
                "Unexpected resource bytes",
            ));
        }
        let mut decoded = BTreeMap::new();
        for (id, img) in &project.images {
            let bytes = files
                .get(&img.path)
                .ok_or_else(|| Failure::new(ErrorCode::ImageMissing, "image", &img.path))?;
            if sha256(bytes) != img.sha256 {
                return Err(Failure::new(
                    ErrorCode::HashMismatch,
                    "image_hash",
                    &img.path,
                ));
            }
            decoded.insert(id.clone(), image::Image::decode(bytes)?);
        }
        let scene: Scene = serde_json::from_value(
            crate::json::value_from_slice(source)
                .map_err(|e| Failure::new(ErrorCode::InvalidScene, "scene", e))?,
        )
        .map_err(|e| Failure::new(ErrorCode::InvalidScene, "scene", e))?;
        // Check named UV presence first, so an absent layer has its own error even
        // when the upstream native validator would report a layout mismatch.
        check_bindings(&project, &scene)?;
        scene
            .validate()
            .map_err(|e| Failure::new(ErrorCode::InvalidScene, "scene", e))?;
        check_closure(&project, &scene)?;
        Ok(PreparedProject {
            project,
            scene,
            project_bytes: project_bytes.to_vec(),
            files: files.clone(),
            decoded,
        })
    })();
    result.map_err(|mut error: Failure| {
        error.observed_project_sha256 = Some(sha256(project_bytes));
        error
    })
}

fn check_bindings(project: &Project, scene: &Scene) -> Result<(), Failure> {
    let mut used = BTreeSet::new();
    for material in project.bindings.keys() {
        if !scene.materials.contains_key(material) {
            return Err(Failure::new(
                ErrorCode::InvalidBinding,
                "bindings",
                "Unknown material",
            ));
        }
    }
    for entity in scene.entities.values() {
        if let EntityKind::Mesh {
            geometry: Geometry::Asset { id },
            material,
        } = &entity.content
        {
            let Some(mesh) = scene.mesh_assets.get(id) else {
                continue;
            };
            let faces = mesh
                .polygons
                .values()
                .map(|f| (f.material_slot, &f.uv_layers))
                .map(|(slot, layers)| (slot, layers.keys().collect::<BTreeSet<_>>()))
                .chain(
                    mesh.triangles
                        .values()
                        .map(|f| (f.material_slot, f.uv_layers.keys().collect())),
                );
            for (slot, layers) in faces {
                let mat = material.as_deref().or_else(|| {
                    slot.and_then(|s| mesh.material_slots.get(s))
                        .and_then(Option::as_deref)
                });
                if let Some((mat, binding)) = mat.and_then(|m| project.bindings.get_key_value(m)) {
                    used.insert(mat);
                    if !layers.contains(&binding.uv_layer) {
                        return Err(Failure::new(
                            ErrorCode::MissingUv,
                            "bindings",
                            format!("Missing UV layer {} on mesh {id}", binding.uv_layer),
                        ));
                    }
                }
            }
        }
    }
    if used != project.bindings.keys().collect() {
        return Err(Failure::new(
            ErrorCode::InvalidBinding,
            "bindings",
            "Every texture binding must be used by a source face",
        ));
    }
    Ok(())
}

fn check_closure(project: &Project, scene: &Scene) -> Result<(), Failure> {
    if scene.time_seconds != 0.0
        || !scene.doors.is_empty()
        || scene.active_camera.is_some()
        || !scene.annotations.is_empty()
    {
        return Err(Failure::new(
            ErrorCode::UnsupportedSceneState,
            "scene",
            "This is a static model source profile",
        ));
    }
    let mut selected = BTreeSet::new();
    let mut pending = Vec::new();
    for id in &project.roots {
        if scene.entities.get(id).is_none_or(|e| e.parent.is_some()) {
            return Err(Failure::new(
                ErrorCode::InvalidRoots,
                "closure",
                "Roots must exist and be top-level",
            ));
        }
        pending.push(id.as_str());
    }
    while let Some(id) = pending.pop() {
        if selected.insert(id) {
            pending.extend(
                scene
                    .entities
                    .iter()
                    .filter(|(_, e)| e.parent.as_deref() == Some(id))
                    .map(|(id, _)| id.as_str()),
            );
        }
    }
    let mut meshes = BTreeSet::new();
    let mut materials = BTreeSet::new();
    for e in scene.entities.values() {
        match &e.content {
            EntityKind::Empty => {}
            EntityKind::Mesh {
                geometry: Geometry::Asset { id },
                material,
            } => {
                meshes.insert(id.as_str());
                materials.extend(material.as_deref());
            }
            _ => {
                return Err(Failure::new(
                    ErrorCode::UnsupportedSceneState,
                    "scene",
                    "Only empty and asset-mesh entities are supported",
                ));
            }
        }
    }
    for m in scene.mesh_assets.values() {
        materials.extend(m.material_slots.iter().filter_map(Option::as_deref));
    }
    let definitions: BTreeSet<_> = scene.materials.keys().map(String::as_str).collect();
    // V1 retains its original exact material-set rule. V2 adds preservation of
    // valid native palettes; it never relaxes references or external image use.
    let material_set_valid = if project.scene_profile == SOURCE_PROFILE_V2 {
        materials.is_subset(&definitions)
    } else {
        materials == definitions
    };
    if selected != scene.entities.keys().map(String::as_str).collect()
        || meshes != scene.mesh_assets.keys().map(String::as_str).collect()
        || !material_set_valid
    {
        return Err(Failure::new(
            ErrorCode::ClosureMismatch,
            "closure",
            "Entity/mesh closure and the selected profile's native material rule must hold",
        ));
    }
    Ok(())
}

impl PreparedProject {
    pub fn resource_bytes(&self, path: &str) -> Option<&[u8]> {
        self.files.get(path).map(Vec::as_slice)
    }
    pub fn project_bytes(&self) -> &[u8] {
        &self.project_bytes
    }

    pub fn inspect(&self) -> Success {
        Success {
            receipt_schema_version: 1,
            ok: Flag,
            operation: Operation::Inspect,
            project_sha256: sha256(&self.project_bytes),
            scene_sha256: self.project.scene.sha256.clone(),
            project_profile: PROJECT_PROFILE.into(),
            scene_profile: self.project.scene_profile.clone(),
            producer_commit: PRODUCER.into(),
            validator_revision: validator_revision(),
            roots: self.project.roots.clone(),
            entities: self.scene.entities.len(),
            mesh_assets: self.scene.mesh_assets.len(),
            polygons: self
                .scene
                .mesh_assets
                .values()
                .map(|m| m.polygons.len())
                .sum(),
            triangles: self
                .scene
                .mesh_assets
                .values()
                .map(|m| m.triangles.len())
                .sum(),
            images: self
                .decoded
                .iter()
                .map(|(id, image)| {
                    (
                        id.clone(),
                        ImageInfo {
                            sha256: self.project.images[id].sha256.clone(),
                            width: image.width,
                            height: image.height,
                            color_space: "srgb".into(),
                        },
                    )
                })
                .collect(),
            samples: Vec::new(),
            saved_location: None,
        }
    }

    pub fn samples(&self, queries: &[Query]) -> Result<Success, Failure> {
        let invalid = || {
            Failure::new(
                ErrorCode::InvalidSample,
                "sample",
                "Select an existing textured entity and source face",
            )
        };
        if queries.is_empty() {
            return Err(invalid());
        }
        let mut result = self.inspect();
        result.operation = Operation::Sample;
        for query in queries {
            let entity = self.scene.entities.get(&query.entity).ok_or_else(invalid)?;
            let EntityKind::Mesh {
                geometry: Geometry::Asset { id },
                material,
            } = &entity.content
            else {
                return Err(invalid());
            };
            let mesh = &self.scene.mesh_assets[id];
            let slot = match &query.face {
                Face::Polygon { id } => mesh.polygons.get(id).ok_or_else(invalid)?.material_slot,
                Face::Triangle { id } => mesh.triangles.get(id).ok_or_else(invalid)?.material_slot,
            };
            let mat = material
                .as_deref()
                .or_else(|| slot.and_then(|s| mesh.material_slots[s].as_deref()))
                .ok_or_else(invalid)?;
            let binding = self.project.bindings.get(mat).ok_or_else(invalid)?;
            let texel = self.decoded[&binding.image].sample(query.uv)?;
            result.samples.push(Sample {
                query: query.clone(),
                material: mat.into(),
                image: binding.image.clone(),
                texel: texel.position,
                rgba8: texel.rgba8,
                linear_rgba: texel.linear_rgba,
            });
        }
        Ok(result)
    }
}

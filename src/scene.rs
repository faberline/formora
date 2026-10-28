//! Versioned scene data and transactional authoring commands.
use schemars::JsonSchema;
use serde::{Deserialize, Deserializer, Serialize, de};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};

pub type Result<T> = std::result::Result<T, SceneError>;
pub type Rotation = [f64; 4];
static NEXT_SAVE: AtomicU64 = AtomicU64::new(0);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SceneError(pub String);

impl fmt::Display for SceneError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(f)
    }
}
impl std::error::Error for SceneError {}

fn fail<T>(message: impl Into<String>) -> Result<T> {
    Err(SceneError(message.into()))
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Transform {
    pub translation: [f64; 3],
    /// Unit quaternion, x/y/z/w order. Coordinates use metres and a right-handed Z-up space.
    pub rotation: Rotation,
    pub scale: [f64; 3],
}

impl Default for Transform {
    fn default() -> Self {
        Self {
            translation: [0.0; 3],
            rotation: [0.0, 0.0, 0.0, 1.0],
            scale: [1.0; 3],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Geometry {
    Cube { size: [f64; 3] },
    Plane { size: [f64; 2] },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum EntityKind {
    Empty,
    Mesh {
        geometry: Geometry,
        material: Option<String>,
    },
    Camera {
        vertical_fov_degrees: f64,
        near: f64,
        far: f64,
    },
    Light {
        color: [f64; 3],
        intensity: f64,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Entity {
    pub name: String,
    pub parent: Option<String>,
    pub transform: Transform,
    pub content: EntityKind,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Material {
    pub base_color: [f64; 4],
    pub roughness: f64,
    pub metallic: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Door {
    pub entity: String,
    pub closed_rotation: Rotation,
    pub open_rotation: Rotation,
    pub duration_seconds: f64,
    pub progress: f64,
    pub target_open: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Annotation {
    pub entity: Option<String>,
    pub position: [f64; 3],
    pub text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Scene {
    pub schema_version: u32,
    pub revision: u64,
    pub time_seconds: f64,
    #[serde(deserialize_with = "unique_map")]
    pub entities: BTreeMap<String, Entity>,
    #[serde(deserialize_with = "unique_map")]
    pub materials: BTreeMap<String, Material>,
    #[serde(deserialize_with = "unique_map")]
    pub doors: BTreeMap<String, Door>,
    pub active_camera: Option<String>,
    pub annotations: Vec<Annotation>,
}

impl Default for Scene {
    fn default() -> Self {
        Self {
            schema_version: 1,
            revision: 0,
            time_seconds: 0.0,
            entities: BTreeMap::new(),
            materials: BTreeMap::new(),
            doors: BTreeMap::new(),
            active_camera: None,
            annotations: Vec::new(),
        }
    }
}

fn unique_map<'de, D, T>(deserializer: D) -> std::result::Result<BTreeMap<String, T>, D::Error>
where
    D: Deserializer<'de>,
    T: Deserialize<'de>,
{
    struct Visitor<T>(std::marker::PhantomData<T>);
    impl<'de, T: Deserialize<'de>> de::Visitor<'de> for Visitor<T> {
        type Value = BTreeMap<String, T>;
        fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
            formatter.write_str("a map with unique IDs")
        }
        fn visit_map<A: de::MapAccess<'de>>(
            self,
            mut access: A,
        ) -> std::result::Result<Self::Value, A::Error> {
            let mut values = BTreeMap::new();
            while let Some((key, value)) = access.next_entry::<String, T>()? {
                if values.insert(key.clone(), value).is_some() {
                    return Err(de::Error::custom(format!("duplicate ID: {key}")));
                }
            }
            Ok(values)
        }
    }
    deserializer.deserialize_map(Visitor(std::marker::PhantomData))
}

fn valid_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 128
        && id
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'-' || c == b'_')
}
fn finite(values: &[f64]) -> bool {
    values.iter().all(|n| n.is_finite())
}
fn unit_rotation(q: &Rotation) -> bool {
    finite(q) && (q.iter().map(|n| n * n).sum::<f64>() - 1.0).abs() <= 1e-6
}
fn interpolate_rotation(a: Rotation, b: Rotation, progress: f64) -> Rotation {
    let sign = if a.iter().zip(b).map(|(a, b)| a * b).sum::<f64>() < 0.0 {
        -1.0
    } else {
        1.0
    };
    let mut q = [0.0; 4];
    for i in 0..4 {
        q[i] = a[i] * (1.0 - progress) + b[i] * sign * progress;
    }
    let length = q.iter().map(|n| n * n).sum::<f64>().sqrt();
    for n in &mut q {
        *n /= length;
    }
    q
}

impl Scene {
    pub fn validate(&self) -> Result<()> {
        if self.schema_version != 1 {
            return fail("unsupported scene schema version");
        }
        if !self.time_seconds.is_finite() || self.time_seconds < 0.0 {
            return fail("scene time must be finite and nonnegative");
        }
        for (id, entity) in &self.entities {
            if !valid_id(id) {
                return fail(format!("invalid entity ID: {id}"));
            }
            let t = &entity.transform;
            if !finite(&t.translation) || !finite(&t.scale) || !unit_rotation(&t.rotation) {
                return fail(format!("invalid transform: {id}"));
            }
            let mut seen = BTreeSet::from([id.as_str()]);
            let mut parent = entity.parent.as_deref();
            while let Some(p) = parent {
                if !seen.insert(p) {
                    return fail(format!("parent cycle: {id}"));
                }
                parent = self
                    .entities
                    .get(p)
                    .ok_or_else(|| SceneError(format!("missing parent: {p}")))?
                    .parent
                    .as_deref();
            }
            match &entity.content {
                EntityKind::Empty => {}
                EntityKind::Mesh { geometry, material } => {
                    let sizes: &[f64] = match geometry {
                        Geometry::Cube { size } => size,
                        Geometry::Plane { size } => size,
                    };
                    if !finite(sizes) || sizes.iter().any(|n| *n <= 0.0) {
                        return fail(format!("invalid geometry size: {id}"));
                    }
                    if material
                        .as_ref()
                        .is_some_and(|m| !self.materials.contains_key(m))
                    {
                        return fail(format!("missing material: {id}"));
                    }
                }
                EntityKind::Camera {
                    vertical_fov_degrees,
                    near,
                    far,
                } => {
                    if !finite(&[*vertical_fov_degrees, *near, *far])
                        || *vertical_fov_degrees <= 0.0
                        || *vertical_fov_degrees >= 180.0
                        || *near <= 0.0
                        || *far <= *near
                    {
                        return fail(format!("invalid camera: {id}"));
                    }
                }
                EntityKind::Light { color, intensity } => {
                    if !finite(color)
                        || color.iter().any(|n| *n < 0.0)
                        || !intensity.is_finite()
                        || *intensity < 0.0
                    {
                        return fail(format!("invalid light: {id}"));
                    }
                }
            }
        }
        for (id, material) in &self.materials {
            if !valid_id(id)
                || !finite(&material.base_color)
                || material.base_color.iter().any(|v| !(0.0..=1.0).contains(v))
                || ![material.roughness, material.metallic]
                    .iter()
                    .all(|v| v.is_finite() && (0.0..=1.0).contains(v))
            {
                return fail(format!("invalid material: {id}"));
            }
        }
        if let Some(id) = &self.active_camera {
            if !matches!(
                self.entities.get(id).map(|e| &e.content),
                Some(EntityKind::Camera { .. })
            ) {
                return fail("active camera must refer to a camera entity");
            }
        }
        let mut controlled = BTreeSet::new();
        for (id, door) in &self.doors {
            if !valid_id(id)
                || !controlled.insert(&door.entity)
                || !unit_rotation(&door.closed_rotation)
                || !unit_rotation(&door.open_rotation)
                || !door.duration_seconds.is_finite()
                || door.duration_seconds <= 0.0
                || !door.progress.is_finite()
                || !(0.0..=1.0).contains(&door.progress)
            {
                return fail(format!("invalid door: {id}"));
            }
            let entity = self
                .entities
                .get(&door.entity)
                .ok_or_else(|| SceneError(format!("missing door entity: {id}")))?;
            let expected =
                interpolate_rotation(door.closed_rotation, door.open_rotation, door.progress);
            let alignment = expected
                .iter()
                .zip(entity.transform.rotation)
                .map(|(a, b)| a * b)
                .sum::<f64>()
                .abs();
            if (alignment - 1.0).abs() > 1e-6 {
                return fail(format!("door rotation disagrees with progress: {id}"));
            }
        }
        for note in &self.annotations {
            if note.text.trim().is_empty()
                || !finite(&note.position)
                || note
                    .entity
                    .as_ref()
                    .is_some_and(|id| !self.entities.contains_key(id))
            {
                return fail("invalid annotation");
            }
        }
        Ok(())
    }

    pub fn load(path: &Path) -> Result<Self> {
        let raw = fs::read(path).map_err(|e| SceneError(e.to_string()))?;
        let scene: Self = serde_json::from_slice(&raw).map_err(|e| SceneError(e.to_string()))?;
        scene.validate()?;
        Ok(scene)
    }

    pub fn save(&self, path: &Path) -> Result<()> {
        self.validate()?;
        let parent = path
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        let name = path
            .file_name()
            .ok_or_else(|| SceneError("scene path needs a filename".into()))?
            .to_string_lossy();
        let temporary = parent.join(format!(
            ".{name}.formora-{}-{}.tmp",
            std::process::id(),
            NEXT_SAVE.fetch_add(1, Ordering::Relaxed)
        ));
        let mut bytes = serde_json::to_vec_pretty(self).map_err(|e| SceneError(e.to_string()))?;
        bytes.push(b'\n');
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .map_err(|e| SceneError(e.to_string()))?;
        let saved = (|| {
            file.write_all(&bytes)?;
            file.sync_all()?;
            drop(file);
            fs::rename(&temporary, path)
        })()
        .map_err(|e: std::io::Error| SceneError(e.to_string()));
        if saved.is_err() {
            let _ = fs::remove_file(&temporary);
        }
        saved
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "operation", rename_all = "snake_case", deny_unknown_fields)]
pub enum Command {
    CreateEntity {
        id: String,
        entity: Entity,
    },
    SetTransform {
        id: String,
        transform: Transform,
    },
    DeleteEntity {
        id: String,
    },
    SetMaterial {
        id: String,
        material: Material,
    },
    SetActiveCamera {
        id: Option<String>,
    },
    CreateDoor {
        id: String,
        entity: String,
        closed_rotation: Rotation,
        open_rotation: Rotation,
        duration_seconds: f64,
    },
    SetDoorDuration {
        id: String,
        duration_seconds: f64,
    },
    TriggerDoor {
        id: String,
        open: bool,
    },
    Advance {
        seconds: f64,
    },
    Annotate {
        annotation: Annotation,
    },
}

impl Command {
    fn apply(&self, scene: &mut Scene) -> Result<()> {
        match self {
            Self::CreateEntity { id, entity } => {
                if scene.entities.contains_key(id) {
                    return fail(format!("entity exists: {id}"));
                }
                scene.entities.insert(id.clone(), entity.clone());
            }
            Self::SetTransform { id, transform } => {
                scene
                    .entities
                    .get_mut(id)
                    .ok_or_else(|| SceneError(format!("unknown entity: {id}")))?
                    .transform = transform.clone()
            }
            Self::DeleteEntity { id } => {
                if scene.entities.remove(id).is_none() {
                    return fail(format!("unknown entity: {id}"));
                }
            }
            Self::SetMaterial { id, material } => {
                scene.materials.insert(id.clone(), material.clone());
            }
            Self::SetActiveCamera { id } => scene.active_camera = id.clone(),
            Self::CreateDoor {
                id,
                entity,
                closed_rotation,
                open_rotation,
                duration_seconds,
            } => {
                if scene.doors.contains_key(id) {
                    return fail(format!("door exists: {id}"));
                }
                scene
                    .entities
                    .get_mut(entity)
                    .ok_or_else(|| SceneError(format!("unknown entity: {entity}")))?
                    .transform
                    .rotation = *closed_rotation;
                scene.doors.insert(
                    id.clone(),
                    Door {
                        entity: entity.clone(),
                        closed_rotation: *closed_rotation,
                        open_rotation: *open_rotation,
                        duration_seconds: *duration_seconds,
                        progress: 0.0,
                        target_open: false,
                    },
                );
            }
            Self::SetDoorDuration {
                id,
                duration_seconds,
            } => {
                scene
                    .doors
                    .get_mut(id)
                    .ok_or_else(|| SceneError(format!("unknown door: {id}")))?
                    .duration_seconds = *duration_seconds
            }
            Self::TriggerDoor { id, open } => {
                scene
                    .doors
                    .get_mut(id)
                    .ok_or_else(|| SceneError(format!("unknown door: {id}")))?
                    .target_open = *open
            }
            Self::Advance { seconds } => {
                if !seconds.is_finite() || *seconds < 0.0 {
                    return fail("time step must be finite and nonnegative");
                }
                scene.time_seconds += seconds;
                for door in scene.doors.values_mut() {
                    let delta = seconds / door.duration_seconds;
                    door.progress = if door.target_open {
                        (door.progress + delta).min(1.0)
                    } else {
                        (door.progress - delta).max(0.0)
                    };
                    scene
                        .entities
                        .get_mut(&door.entity)
                        .ok_or_else(|| SceneError("missing door entity".into()))?
                        .transform
                        .rotation = interpolate_rotation(
                        door.closed_rotation,
                        door.open_rotation,
                        door.progress,
                    );
                }
            }
            Self::Annotate { annotation } => scene.annotations.push(annotation.clone()),
        }
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct Editor {
    scene: Scene,
    undo: Vec<Scene>,
}

impl Editor {
    pub fn new(scene: Scene) -> Result<Self> {
        scene.validate()?;
        Ok(Self {
            scene,
            undo: Vec::new(),
        })
    }
    pub fn scene(&self) -> &Scene {
        &self.scene
    }
    fn next_revision(&self, expected: Option<u64>) -> Result<u64> {
        if expected.is_some_and(|r| r != self.scene.revision) {
            return fail("stale scene revision");
        }
        self.scene
            .revision
            .checked_add(1)
            .ok_or_else(|| SceneError("scene revision exhausted".into()))
    }
    /// A batch commits once. Any invalid command leaves both scene and undo history unchanged.
    pub fn apply(&mut self, commands: &[Command], expected_revision: Option<u64>) -> Result<u64> {
        if commands.is_empty() {
            return fail("empty command batch");
        }
        let revision = self.next_revision(expected_revision)?;
        let mut candidate = self.scene.clone();
        for command in commands {
            command.apply(&mut candidate)?;
            candidate.validate()?;
        }
        candidate.revision = revision;
        self.undo
            .push(std::mem::replace(&mut self.scene, candidate));
        Ok(revision)
    }
    pub fn undo(&mut self, expected_revision: Option<u64>) -> Result<u64> {
        let revision = self.next_revision(expected_revision)?;
        let mut restored = self
            .undo
            .pop()
            .ok_or_else(|| SceneError("nothing to undo".into()))?;
        restored.revision = revision;
        self.scene = restored;
        Ok(revision)
    }
}

/// A small room with a hinged door. Rendering and input consume this same scene.
pub fn room_demo() -> Result<Scene> {
    let mut commands = Vec::new();
    for (id, color) in [
        ("floor_material", [0.35, 0.38, 0.42, 1.0]),
        ("wall_material", [0.75, 0.75, 0.7, 1.0]),
        ("door_material", [0.8, 0.35, 0.12, 1.0]),
    ] {
        commands.push(Command::SetMaterial {
            id: id.into(),
            material: Material {
                base_color: color,
                roughness: 0.7,
                metallic: 0.0,
            },
        });
    }
    let parts = [
        ("floor", [0.0, 0.0, -0.1], [8.0, 6.0, 0.2], "floor_material"),
        (
            "north_wall",
            [0.0, 3.0, 1.5],
            [8.0, 0.2, 3.0],
            "wall_material",
        ),
        (
            "west_wall",
            [-4.0, 0.0, 1.5],
            [0.2, 6.0, 3.0],
            "wall_material",
        ),
        (
            "east_wall",
            [4.0, 0.0, 1.5],
            [0.2, 6.0, 3.0],
            "wall_material",
        ),
        (
            "south_left",
            [-2.3, -3.0, 1.5],
            [3.4, 0.2, 3.0],
            "wall_material",
        ),
        (
            "south_right",
            [2.3, -3.0, 1.5],
            [3.4, 0.2, 3.0],
            "wall_material",
        ),
        (
            "door_header",
            [0.0, -3.0, 2.7],
            [1.2, 0.2, 0.6],
            "wall_material",
        ),
    ];
    for (id, translation, size, material) in parts {
        commands.push(Command::CreateEntity {
            id: id.into(),
            entity: Entity {
                name: id.into(),
                parent: None,
                transform: Transform {
                    translation,
                    ..Transform::default()
                },
                content: EntityKind::Mesh {
                    geometry: Geometry::Cube { size },
                    material: Some(material.into()),
                },
            },
        });
    }
    commands.push(Command::CreateEntity {
        id: "door_hinge".into(),
        entity: Entity {
            name: "Door hinge".into(),
            parent: None,
            transform: Transform {
                translation: [-0.6, -3.0, 0.0],
                ..Transform::default()
            },
            content: EntityKind::Empty,
        },
    });
    commands.push(Command::CreateEntity {
        id: "door_panel".into(),
        entity: Entity {
            name: "Door".into(),
            parent: Some("door_hinge".into()),
            transform: Transform {
                translation: [0.6, 0.0, 1.2],
                ..Transform::default()
            },
            content: EntityKind::Mesh {
                geometry: Geometry::Cube {
                    size: [1.2, 0.12, 2.4],
                },
                material: Some("door_material".into()),
            },
        },
    });
    let (sin, cos) = (std::f64::consts::FRAC_PI_4).sin_cos();
    commands.push(Command::CreateDoor {
        id: "front_door".into(),
        entity: "door_hinge".into(),
        closed_rotation: Transform::default().rotation,
        open_rotation: [0.0, 0.0, sin, cos],
        duration_seconds: 1.0,
    });
    let (sin, cos) = (8.0_f64.atan2(2.5) / 2.0).sin_cos();
    commands.push(Command::CreateEntity {
        id: "camera".into(),
        entity: Entity {
            name: "Preview camera".into(),
            parent: None,
            transform: Transform {
                translation: [0.0, -8.0, 4.0],
                rotation: [sin, 0.0, 0.0, cos],
                ..Transform::default()
            },
            content: EntityKind::Camera {
                vertical_fov_degrees: 60.0,
                near: 0.1,
                far: 1000.0,
            },
        },
    });
    commands.push(Command::SetActiveCamera {
        id: Some("camera".into()),
    });
    commands.push(Command::CreateEntity {
        id: "light".into(),
        entity: Entity {
            name: "Room light".into(),
            parent: None,
            transform: Transform {
                translation: [0.0, 0.0, 5.0],
                ..Transform::default()
            },
            content: EntityKind::Light {
                color: [1.0, 0.95, 0.85],
                intensity: 100.0,
            },
        },
    });
    let mut editor = Editor::new(Scene::default())?;
    editor.apply(&commands, Some(0))?;
    Ok(editor.scene)
}

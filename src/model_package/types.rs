use schemars::{JsonSchema, Schema, SchemaGenerator, json_schema};
use serde::{Deserialize, Deserializer, Serialize, Serializer, de};
use std::{borrow::Cow, path::PathBuf};

/// A JSON boolean with one permitted value, including in the public schema.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Flag<const VALUE: bool>;

impl<const VALUE: bool> Serialize for Flag<VALUE> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_bool(VALUE)
    }
}

impl<'de, const VALUE: bool> Deserialize<'de> for Flag<VALUE> {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        if bool::deserialize(deserializer)? == VALUE {
            Ok(Self)
        } else {
            Err(de::Error::custom(format!("expected {VALUE}")))
        }
    }
}

impl<const VALUE: bool> JsonSchema for Flag<VALUE> {
    fn schema_name() -> Cow<'static, str> {
        if VALUE { "TrueFlag" } else { "FalseFlag" }.into()
    }

    fn json_schema(_: &mut SchemaGenerator) -> Schema {
        json_schema!({"type":"boolean", "const": VALUE})
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum Capability {
    TriangleMeshes,
    Hierarchy,
    CornerUvs,
    CornerNormals,
    SolidColorMaterials,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DisplayExport {
    pub format: String,
    pub relative_path: String,
    pub sha256: String,
    pub scope: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub manifest_schema_version: u32,
    pub scene_file: String,
    pub scene_sha256: String,
    pub scene_schema_version: u32,
    pub scene_profile: String,
    pub producer_commit: String,
    pub roots: Vec<String>,
    pub meters_per_unit: f64,
    pub up_axis: String,
    pub coordinate_system: String,
    pub capabilities: Vec<Capability>,
    #[serde(default)]
    pub display_exports: Vec<DisplayExport>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ImportRequest {
    pub manifest: PathBuf,
    pub expected_manifest_sha256: String,
    pub output: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SchemaRequest {}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, JsonSchema, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    InvalidRequest,
    ManifestMissing,
    InvalidManifest,
    HashMismatch,
    UnsupportedSchema,
    UnsupportedProfile,
    UnsupportedProducer,
    UnsupportedUnits,
    UnsupportedFeature,
    SceneMissing,
    InvalidScene,
    InvalidRoots,
    ClosureMismatch,
    UnsupportedSceneState,
    OutputExists,
    IoError,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, JsonSchema, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Stage {
    Request,
    ReadManifest,
    ManifestHash,
    Manifest,
    Profile,
    ReadScene,
    SceneHash,
    Scene,
    Closure,
    StageOutput,
    SaveModel,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ErrorDetail {
    pub code: ErrorCode,
    pub stage: Stage,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Failure {
    pub receipt_schema_version: u32,
    pub ok: Flag<false>,
    pub error: ErrorDetail,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub observed_manifest_sha256: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub observed_scene_sha256: Option<String>,
}

impl Failure {
    pub(crate) fn new(code: ErrorCode, stage: Stage, message: impl Into<String>) -> Self {
        Self {
            receipt_schema_version: 1,
            ok: Flag,
            error: ErrorDetail {
                code,
                stage,
                message: message.into(),
            },
            observed_manifest_sha256: None,
            observed_scene_sha256: None,
        }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Counts {
    pub entities: usize,
    pub mesh_assets: usize,
    pub vertices: usize,
    pub triangles: usize,
    pub materials: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Imported {
    pub receipt_schema_version: u32,
    pub ok: Flag<true>,
    pub manifest_sha256: String,
    pub scene_sha256: String,
    pub scene_profile: String,
    pub producer_commit: String,
    /// SHA-256 of the validator's compiled-in source inputs, not a build attestation.
    pub validator_revision: String,
    pub roots: Vec<String>,
    pub meters_per_unit: f64,
    pub up_axis: String,
    pub coordinate_system: String,
    pub counts: Counts,
    pub saved_location: PathBuf,
    pub conversion_report: Vec<String>,
    pub loss_report: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(untagged)]
pub enum Receipt {
    Imported(Box<Imported>),
    Failed(Failure),
}

impl Receipt {
    pub fn is_ok(&self) -> bool {
        matches!(self, Self::Imported(_))
    }
}

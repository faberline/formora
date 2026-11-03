use crate::model_package::Flag;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, path::PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Resource {
    pub path: String,
    pub sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ImageResource {
    pub path: String,
    pub sha256: String,
    pub color_space: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Binding {
    pub image: String,
    pub uv_layer: String,
    pub filter: String,
    pub address_mode: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Project {
    pub project_schema_version: u32,
    pub project_profile: String,
    pub scene_profile: String,
    pub producer_commit: String,
    pub scene: Resource,
    pub roots: Vec<String>,
    pub images: BTreeMap<String, ImageResource>,
    pub bindings: BTreeMap<String, Binding>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct InspectRequest {
    pub project: PathBuf,
    pub expected_project_sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ImportRequest {
    pub project: PathBuf,
    pub expected_project_sha256: String,
    pub output: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Face {
    Polygon { id: String },
    Triangle { id: String },
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Query {
    pub entity: String,
    pub face: Face,
    /// Texture-space coordinates, not a world-space or projected pixel position.
    pub uv: [f64; 2],
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SampleRequest {
    pub project: PathBuf,
    pub expected_project_sha256: String,
    pub samples: Vec<Query>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, JsonSchema, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    InvalidRequest,
    ProjectMissing,
    InvalidProject,
    HashMismatch,
    UnsupportedProfile,
    UnsupportedProducer,
    InvalidPath,
    SceneMissing,
    InvalidScene,
    InvalidRoots,
    ClosureMismatch,
    UnsupportedSceneState,
    InvalidBinding,
    MissingUv,
    ImageMissing,
    InvalidImage,
    UnsupportedImage,
    InvalidSample,
    OutputExists,
    IoError,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Failure {
    pub receipt_schema_version: u32,
    pub ok: Flag<false>,
    pub code: ErrorCode,
    pub stage: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub observed_project_sha256: Option<String>,
}

impl Failure {
    pub(crate) fn new(code: ErrorCode, stage: &str, message: impl ToString) -> Self {
        Self {
            receipt_schema_version: 1,
            ok: Flag,
            code,
            stage: stage.into(),
            message: message.to_string(),
            observed_project_sha256: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ImageInfo {
    pub sha256: String,
    pub width: u32,
    pub height: u32,
    pub color_space: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Sample {
    pub query: Query,
    pub material: String,
    pub image: String,
    pub texel: [u32; 2],
    pub rgba8: [u8; 4],
    pub linear_rgba: [f64; 4],
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Operation {
    Inspect,
    Sample,
    Import,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Success {
    pub receipt_schema_version: u32,
    pub ok: Flag<true>,
    pub operation: Operation,
    pub project_sha256: String,
    pub scene_sha256: String,
    pub project_profile: String,
    pub scene_profile: String,
    pub producer_commit: String,
    pub validator_revision: String,
    pub roots: Vec<String>,
    pub entities: usize,
    pub mesh_assets: usize,
    pub polygons: usize,
    pub triangles: usize,
    pub images: BTreeMap<String, ImageInfo>,
    pub samples: Vec<Sample>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub saved_location: Option<PathBuf>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(untagged)]
pub enum Receipt {
    Success(Box<Success>),
    Failure(Failure),
}

impl Receipt {
    pub fn is_ok(&self) -> bool {
        matches!(self, Self::Success(_))
    }
}

//! Immutable derived render data. The editable project remains the source of truth.
mod geometry;
mod reference;
pub use reference::{Frame, ReferencePixel};

use super::{Face, PreparedProject};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, fmt};

pub const RENDER_PROFILE: &str = "formora-unlit-texture-bb025-v1";
pub const PROTOCOL: &str = include_str!("../../../protocols/material-render-v1.json");

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenderError {
    pub code: String,
    pub message: String,
}
impl RenderError {
    pub(crate) fn new(code: &str, message: impl ToString) -> Self {
        Self {
            code: code.into(),
            message: message.to_string(),
        }
    }
}
impl fmt::Display for RenderError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}
impl std::error::Error for RenderError {}

#[repr(C)]
#[derive(Debug, Clone, Copy, Serialize)]
#[cfg_attr(feature = "render", derive(bytemuck::Pod, bytemuck::Zeroable))]
pub struct Vertex {
    pub position: [f32; 3],
    pub uv: [f32; 2],
}

#[derive(Debug, Clone, Serialize)]
pub struct TriangleSource {
    pub entity: String,
    pub mesh: String,
    pub face: Face,
    pub corners: [usize; 3],
    pub vertex_ids: [String; 3],
    /// Exact authored values before conversion to the derived GPU f32 buffer.
    pub source_uvs: Option<[[f64; 2]; 3]>,
}

pub struct Batch {
    pub(crate) material: Option<String>,
    pub(crate) image: Option<String>,
    pub(crate) factor: [f32; 4],
    pub(crate) vertices: Vec<Vertex>,
    pub(crate) sources: Vec<TriangleSource>,
}
impl Batch {
    pub fn material(&self) -> Option<&str> {
        self.material.as_deref()
    }
    pub fn image(&self) -> Option<&str> {
        self.image.as_deref()
    }
    pub fn factor(&self) -> [f32; 4] {
        self.factor
    }
    pub fn vertices(&self) -> &[Vertex] {
        &self.vertices
    }
    pub fn sources(&self) -> &[TriangleSource] {
        &self.sources
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct RenderIdentity {
    pub render_profile: String,
    pub render_revision: String,
    pub project_sha256: String,
    pub scene_sha256: String,
    pub source_profile: String,
    pub producer_commit: String,
    pub encoded_image_sha256: BTreeMap<String, String>,
    pub vertices: usize,
    pub triangles: usize,
}

/// Borrows the immutable checked project. This is not a replacement editable file.
pub struct RenderScene<'a> {
    pub(crate) project: &'a PreparedProject,
    pub(crate) batches: Vec<Batch>,
}
impl<'a> RenderScene<'a> {
    pub fn from_project(project: &'a PreparedProject) -> Result<Self, RenderError> {
        geometry::prepare(project)
    }
    pub fn batches(&self) -> &[Batch] {
        &self.batches
    }
    pub fn identity(&self) -> RenderIdentity {
        let source = self.project.inspect();
        let mut digest = Sha256::new();
        digest.update(source.validator_revision.as_bytes());
        for bytes in [
            include_bytes!("mod.rs").as_slice(),
            include_bytes!("geometry.rs").as_slice(),
            include_bytes!("reference.rs").as_slice(),
            include_bytes!("../../material_renderer/mod.rs").as_slice(),
            include_bytes!("../../material_renderer/shader.wgsl").as_slice(),
            PROTOCOL.as_bytes(),
        ] {
            digest.update((bytes.len() as u64).to_le_bytes());
            digest.update(bytes);
        }
        RenderIdentity {
            render_profile: RENDER_PROFILE.into(),
            render_revision: format!("sha256:{:x}", digest.finalize()),
            project_sha256: source.project_sha256,
            scene_sha256: source.scene_sha256,
            source_profile: source.scene_profile,
            producer_commit: source.producer_commit,
            encoded_image_sha256: source
                .images
                .into_iter()
                .map(|(id, i)| (id, i.sha256))
                .collect(),
            vertices: self.batches.iter().map(|b| b.vertices.len()).sum(),
            triangles: self.batches.iter().map(|b| b.sources.len()).sum(),
        }
    }
}

#[cfg(test)]
mod tests;

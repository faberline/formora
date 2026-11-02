//! Read-only CPU diagnostics. No window, GPU, session, file access or scene edits.
use crate::geometry;
use crate::scene::{Result, Scene, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::io::Write;
use std::time::Instant;

fn width() -> u32 {
    1280
}
fn height() -> u32 {
    800
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DebugRequest {
    /// Prepare the same f32 vertices used by the preview, without a GPU.
    #[serde(default)]
    pub geometry: bool,
    /// Include row-major world matrices. The default report includes their digest only.
    #[serde(default)]
    pub include_world: bool,
    #[serde(default = "width")]
    pub width: u32,
    #[serde(default = "height")]
    pub height: u32,
}

impl Default for DebugRequest {
    fn default() -> Self {
        Self {
            geometry: false,
            include_world: false,
            width: width(),
            height: height(),
        }
    }
}

fn stage<T>(
    checks: &mut Vec<Value>,
    name: &str,
    operation: impl FnOnce() -> Result<T>,
) -> Option<T> {
    let start = Instant::now();
    let result = operation();
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    match result {
        Ok(value) => {
            checks.push(json!({"name":name,"status":"passed","elapsed_ms":elapsed_ms}));
            Some(value)
        }
        Err(error) => {
            checks.push(json!({"name":name,"status":"failed","elapsed_ms":elapsed_ms,"error":error.to_string()}));
            None
        }
    }
}

fn finish(
    mut report: Value,
    mut checks: Vec<Value>,
    request: &DebugRequest,
    passed: bool,
) -> Value {
    for name in [
        "request",
        "validation",
        "fingerprint",
        "transforms",
        "camera",
        "geometry",
    ] {
        if !checks.iter().any(|c| c["name"] == name) {
            let status = if name == "geometry" && !request.geometry {
                "not_requested"
            } else {
                "skipped"
            };
            checks.push(json!({"name":name,"status":status}));
        }
    }
    report["passed"] = json!(passed);
    report["checks"] = json!(checks);
    report
}

struct HashWriter<'a>(&'a mut Sha256);
impl Write for HashWriter<'_> {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.0.update(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

/// Diagnoses one immutable in-memory scene. `passed` covers requested checks only.
/// Elapsed times are diagnostic CPU wall times, not a frame-rate qualification.
/// Digests exclude timings. Geometry is the preview's f32 projection, not native f64 data.
pub fn diagnose(scene: &Scene, request: &DebugRequest) -> Value {
    let start = Instant::now();
    let mut report = diagnose_inner(scene, request);
    report["elapsed_ms"] = json!(start.elapsed().as_secs_f64() * 1000.0);
    report
}

fn diagnose_inner(scene: &Scene, request: &DebugRequest) -> Value {
    let mut report = json!({"schema_version":1,"mode":"headless_cpu","passed":false,
        "request":request,"revision":scene.revision,"scene_sha256":null,
        "world_sha256":null,"world_matrices":null,"camera":null,"geometry":null,
        "counts":{"entities":scene.entities.len(),"mesh_assets":scene.mesh_assets.len(),
            "materials":scene.materials.len(),"annotations":scene.annotations.len(),
            "asset_vertices":scene.mesh_assets.values().map(|a|a.vertices.len()).sum::<usize>(),
            "asset_triangles":scene.mesh_assets.values().map(|a|a.triangles.len()).sum::<usize>(),
            "asset_polygons":scene.mesh_assets.values().map(|a|a.polygons.len()).sum::<usize>()}});
    let mut checks = Vec::new();
    if stage(&mut checks, "request", || {
        if request.width == 0 || request.height == 0 {
            Err(SceneError("diagnostic dimensions must be nonzero".into()))
        } else {
            Ok(())
        }
    })
    .is_none()
    {
        return finish(report, checks, request, false);
    }
    if stage(&mut checks, "validation", || scene.validate()).is_none() {
        return finish(report, checks, request, false);
    }
    let Some(digest) = stage(&mut checks, "fingerprint", || {
        let mut hash = Sha256::new();
        serde_json::to_writer(HashWriter(&mut hash), scene)
            .map_err(|e| SceneError(e.to_string()))?;
        Ok(format!("{:x}", hash.finalize()))
    }) else {
        return finish(report, checks, request, false);
    };
    report["scene_sha256"] = json!(digest);
    let Some(world) = stage(&mut checks, "transforms", || {
        geometry::world_transforms(scene)
    }) else {
        return finish(report, checks, request, false);
    };
    let mut hash = Sha256::new();
    hash.update(b"formora-headless-world-v1");
    let mut matrices = serde_json::Map::new();
    for (id, matrix) in &world {
        hash.update((id.len() as u64).to_le_bytes());
        hash.update(id.as_bytes());
        let columns = matrix.to_cols_array_2d();
        let rows: [[f64; 4]; 4] = std::array::from_fn(|r| std::array::from_fn(|c| columns[c][r]));
        for value in rows.iter().flatten() {
            hash.update(value.to_bits().to_le_bytes());
        }
        if request.include_world {
            matrices.insert(id.clone(), json!(rows));
        }
    }
    report["world_sha256"] = json!(format!("{:x}", hash.finalize()));
    if request.include_world {
        report["world_matrices"] = Value::Object(matrices);
    }
    let Some(camera) = stage(&mut checks, "camera", || {
        geometry::camera(scene, request.width, request.height)
    }) else {
        return finish(report, checks, request, false);
    };
    report["camera"] = json!({"position":camera.position.to_array(),"view_projection_columns":camera.view_projection.to_cols_array_2d()});
    if request.geometry {
        let Some(vertices) = stage(&mut checks, "geometry", || geometry::vertices(scene)) else {
            return finish(report, checks, request, false);
        };
        let mut hash = Sha256::new();
        hash.update(b"formora-headless-vertices-v1");
        let mut min = [f32::INFINITY; 3];
        let mut max = [f32::NEG_INFINITY; 3];
        for vertex in &vertices {
            for axis in 0..3 {
                min[axis] = min[axis].min(vertex.position[axis]);
                max[axis] = max[axis].max(vertex.position[axis]);
            }
            for value in vertex
                .position
                .into_iter()
                .chain(vertex.normal)
                .chain(vertex.color)
                .chain(vertex.surface)
            {
                hash.update(value.to_bits().to_le_bytes());
            }
        }
        let bounds = if vertices.is_empty() {
            Value::Null
        } else {
            json!({"min":min,"max":max})
        };
        report["geometry"] = json!({"precision":"f32_preview_projection","vertices":vertices.len(),
            "triangles":vertices.len()/3,"bounds":bounds,"sha256":format!("{:x}",hash.finalize())});
    }
    finish(report, checks, request, true)
}

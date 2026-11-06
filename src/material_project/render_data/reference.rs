use super::*;

/// Column-major matrices, as in WGSL. Per-instance data changes GPU memory only.
#[repr(C)]
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
#[cfg_attr(feature = "render", derive(bytemuck::Pod, bytemuck::Zeroable))]
pub struct Frame {
    pub view_projection: [[f32; 4]; 4],
    pub model_to_world: [[f32; 4]; 4],
}
impl Default for Frame {
    fn default() -> Self {
        let identity =
            std::array::from_fn(|c| std::array::from_fn(|r| if r == c { 1.0 } else { 0.0 }));
        Self {
            view_projection: identity,
            model_to_world: identity,
        }
    }
}
impl Frame {
    pub fn diagnostic_panel() -> Self {
        Self {
            view_projection: [
                [1.0 / 0.75, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0 / 9.9, 0.0],
                [0.0, 1.0 / 0.75, 0.0, 0.0],
                [0.0, -0.5 / 0.75, 1.9 / 9.9, 1.0],
            ],
            ..Default::default()
        }
    }
    pub fn validate(&self) -> Result<(), RenderError> {
        if self
            .view_projection
            .iter()
            .chain(self.model_to_world.iter())
            .flatten()
            .all(|v| v.is_finite())
        {
            Ok(())
        } else {
            Err(RenderError::new(
                "invalid_frame",
                "Frame matrices must be finite",
            ))
        }
    }
}
#[derive(Debug, Clone, Serialize)]
pub struct ReferencePixel {
    pub xy: [u32; 2],
    pub source: TriangleSource,
    pub uv: Option<[f64; 2]>,
    pub depth: f64,
    pub minimum_barycentric: f64,
    pub linear_rgba: [f64; 4],
    pub rgba8: [u8; 4],
}
fn multiply(m: [[f32; 4]; 4], v: [f64; 4]) -> [f64; 4] {
    std::array::from_fn(|r| (0..4).map(|c| f64::from(m[c][r]) * v[c]).sum())
}
fn encode(c: f64) -> u8 {
    let c = c.clamp(0.0, 1.0);
    let s = if c <= 0.0031308 {
        12.92 * c
    } else {
        1.055 * c.powf(1.0 / 2.4) - 0.055
    };
    (s * 255.0).round().clamp(0.0, 255.0) as u8
}

impl RenderScene<'_> {
    /// Interior-pixel oracle for affine/orthographic frames only. No GPU or file access.
    /// Edge fill rules, perspective clipping and lighting are outside this oracle.
    pub fn reference_pixel(
        &self,
        frame: &Frame,
        width: u32,
        height: u32,
        x: u32,
        y: u32,
    ) -> Result<Option<ReferencePixel>, RenderError> {
        frame.validate()?;
        if width == 0 || height == 0 || x >= width || y >= height {
            return Err(RenderError::new(
                "invalid_pixel",
                "Pixel must be inside a nonzero target",
            ));
        }
        for m in [frame.view_projection, frame.model_to_world] {
            if [m[0][3], m[1][3], m[2][3], m[3][3]] != [0.0, 0.0, 0.0, 1.0] {
                return Err(RenderError::new(
                    "unsupported_reference_camera",
                    "CPU oracle accepts affine orthographic frames only",
                ));
            }
        }
        let pixel = [
            2.0 * (f64::from(x) + 0.5) / f64::from(width) - 1.0,
            1.0 - 2.0 * (f64::from(y) + 0.5) / f64::from(height),
        ];
        let mut best = None;
        let mut best_depth = 1.0;
        for batch in &self.batches {
            for (vertices, source) in batch.vertices.chunks_exact(3).zip(&batch.sources) {
                let p: [[_; 4]; 3] = std::array::from_fn(|i| {
                    multiply(
                        frame.view_projection,
                        multiply(
                            frame.model_to_world,
                            [
                                f64::from(vertices[i].position[0]),
                                f64::from(vertices[i].position[1]),
                                f64::from(vertices[i].position[2]),
                                1.0,
                            ],
                        ),
                    )
                });
                let denominator = (p[1][1] - p[2][1]) * (p[0][0] - p[2][0])
                    + (p[2][0] - p[1][0]) * (p[0][1] - p[2][1]);
                if denominator == 0.0 {
                    continue;
                }
                let a = ((p[1][1] - p[2][1]) * (pixel[0] - p[2][0])
                    + (p[2][0] - p[1][0]) * (pixel[1] - p[2][1]))
                    / denominator;
                let b = ((p[2][1] - p[0][1]) * (pixel[0] - p[2][0])
                    + (p[0][0] - p[2][0]) * (pixel[1] - p[2][1]))
                    / denominator;
                let w = [a, b, 1.0 - a - b];
                let min = w.into_iter().fold(f64::INFINITY, f64::min);
                if min < 0.0 {
                    continue;
                }
                let depth = (0..3).map(|i| w[i] * p[i][2]).sum::<f64>();
                if !(0.0..=1.0).contains(&depth) || depth >= best_depth {
                    continue;
                }
                let uv = batch.image.as_ref().map(|_| {
                    std::array::from_fn(|c| {
                        (0..3).map(|i| w[i] * f64::from(vertices[i].uv[c])).sum()
                    })
                });
                let image_linear = match (&batch.image, uv) {
                    (Some(id), Some(uv)) => {
                        self.project.decoded[id]
                            .sample(uv)
                            .map_err(|e| RenderError::new("sample", e.message))?
                            .linear_rgba
                    }
                    _ => [1.0; 4],
                };
                let linear_rgba =
                    std::array::from_fn(|i| image_linear[i] * f64::from(batch.factor[i]));
                let rgba8 = [
                    encode(linear_rgba[0]),
                    encode(linear_rgba[1]),
                    encode(linear_rgba[2]),
                    255,
                ];
                best = Some(ReferencePixel {
                    xy: [x, y],
                    source: source.clone(),
                    uv,
                    depth,
                    minimum_barycentric: min,
                    linear_rgba,
                    rgba8,
                });
                best_depth = depth;
            }
        }
        Ok(best)
    }
}

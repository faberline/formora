//! Procedural assets. Runtime generation uses only Rust parameters and arithmetic.
use super::{MeshAsset, Polygon, UvLayout};
use crate::scene::{Result, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

mod legacy;
mod legacy_tables;
mod rotational;
pub use rotational::TorusMode;

pub const DEFAULT_MAX_COMPONENTS: usize = 1_000_000;
const MAX_DIMENSION: f64 = 999_999_995_904.;
const MAX_DIVISIONS: u32 = 10_000_000;
pub fn default_budget() -> usize {
    DEFAULT_MAX_COMPONENTS
}
fn size() -> f64 {
    2.
}
fn radius() -> f64 {
    1.
}
fn divisions() -> u32 {
    10
}
fn circle_vertices() -> u32 {
    32
}
fn enabled() -> bool {
    true
}
fn zero_rotation() -> [f64; 3] {
    [0.; 3]
}
fn unit_scale() -> [f64; 3] {
    [1.; 3]
}

#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum CircleFill {
    #[default]
    Nothing,
    Ngon,
    Trifan,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Primitive {
    IcoSphere {
        #[serde(default = "legacy::subdivisions")]
        #[schemars(range(min = 1, max = 10))]
        subdivisions: u32,
        #[serde(default = "radius")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        radius: f64,
        #[serde(default = "enabled")]
        calc_uvs: bool,
        #[serde(default = "unit_scale")]
        scale: [f64; 3],
        #[serde(default = "zero_rotation")]
        creation_rotation: [f64; 3],
    },
    Monkey {
        #[serde(default = "size")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        size: f64,
        #[serde(default = "enabled")]
        calc_uvs: bool,
        #[serde(default = "zero_rotation")]
        creation_rotation: [f64; 3],
    },
    Plane {
        #[serde(default = "size")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        size: f64,
        #[serde(default = "enabled")]
        calc_uvs: bool,
    },
    Cube {
        #[serde(default = "size")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        size: f64,
        #[serde(default = "unit_scale")]
        scale: [f64; 3],
        #[serde(default = "enabled")]
        calc_uvs: bool,
    },
    Grid {
        #[serde(default = "size")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        size: f64,
        #[serde(default = "divisions")]
        #[schemars(range(min = 1, max = MAX_DIVISIONS))]
        x_subdivisions: u32,
        #[serde(default = "divisions")]
        #[schemars(range(min = 1, max = MAX_DIVISIONS))]
        y_subdivisions: u32,
        #[serde(default = "enabled")]
        calc_uvs: bool,
    },
    Circle {
        #[serde(default = "radius")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        radius: f64,
        #[serde(default = "circle_vertices")]
        #[schemars(range(min = 3, max = MAX_DIVISIONS))]
        vertices: u32,
        #[serde(default)]
        fill_type: CircleFill,
        #[serde(default = "enabled")]
        calc_uvs: bool,
    },
    UvSphere {
        #[serde(default = "radius")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        radius: f64,
        #[serde(default = "circle_vertices")]
        #[schemars(range(min = 3, max = 100000))]
        segments: u32,
        #[serde(default = "rotational::rings")]
        #[schemars(range(min = 3, max = 100000))]
        ring_count: u32,
        #[serde(default = "enabled")]
        calc_uvs: bool,
        #[serde(default = "unit_scale")]
        scale: [f64; 3],
        #[serde(default = "zero_rotation")]
        creation_rotation: [f64; 3],
    },
    Cylinder {
        #[serde(default = "radius")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        radius: f64,
        #[serde(default = "size")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        depth: f64,
        #[serde(default = "circle_vertices")]
        #[schemars(range(min = 3, max = MAX_DIVISIONS))]
        vertices: u32,
        #[serde(default = "rotational::cap_fill")]
        end_fill_type: CircleFill,
        #[serde(default = "enabled")]
        calc_uvs: bool,
        #[serde(default = "unit_scale")]
        scale: [f64; 3],
        #[serde(default = "zero_rotation")]
        creation_rotation: [f64; 3],
    },
    Cone {
        #[serde(default = "radius")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        radius1: f64,
        #[serde(default)]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        radius2: f64,
        #[serde(default = "size")]
        #[schemars(range(min = 0., max = MAX_DIMENSION))]
        depth: f64,
        #[serde(default = "circle_vertices")]
        #[schemars(range(min = 3, max = MAX_DIVISIONS))]
        vertices: u32,
        #[serde(default = "rotational::cap_fill")]
        end_fill_type: CircleFill,
        #[serde(default = "enabled")]
        calc_uvs: bool,
        #[serde(default = "unit_scale")]
        scale: [f64; 3],
        #[serde(default = "zero_rotation")]
        creation_rotation: [f64; 3],
    },
    Torus {
        #[serde(default = "rotational::major_segments")]
        #[schemars(range(min = 3, max = 256))]
        major_segments: u32,
        #[serde(default = "rotational::minor_segments")]
        #[schemars(range(min = 3, max = 256))]
        minor_segments: u32,
        #[serde(default)]
        mode: TorusMode,
        #[serde(default = "radius")]
        #[schemars(range(min = 0., max = 10000.))]
        major_radius: f64,
        #[serde(default = "rotational::minor_radius")]
        #[schemars(range(min = 0., max = 10000.))]
        minor_radius: f64,
        #[serde(default = "rotational::outer_radius")]
        #[schemars(range(min = 0., max = 10000.))]
        abso_major_rad: f64,
        #[serde(default = "rotational::inner_radius")]
        #[schemars(range(min = 0., max = 10000.))]
        abso_minor_rad: f64,
        #[serde(default = "enabled")]
        generate_uvs: bool,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct PrimitiveRecipe {
    pub primitive: Primitive,
    pub max_components: usize,
    pub edited: bool,
}

impl Primitive {
    /// Vertex + edge + polygon + face-corner count. Checked before allocation.
    pub fn component_count(&self) -> Result<usize> {
        if let Self::Cube { scale, .. }
        | Self::IcoSphere { scale, .. }
        | Self::UvSphere { scale, .. }
        | Self::Cylinder { scale, .. }
        | Self::Cone { scale, .. } = self
        {
            if scale
                .iter()
                .any(|n| !n.is_finite() || n.abs() > MAX_DIMENSION)
            {
                return Err(SceneError(
                    "primitive scale must be finite and within the dimension range".into(),
                ));
            }
        }
        let dimension = match self {
            Self::IcoSphere { .. } | Self::Monkey { .. } => return legacy::component_count(self),
            Self::Plane { size, .. } | Self::Cube { size, .. } | Self::Grid { size, .. } => *size,
            Self::Circle { radius, .. } => *radius,
            Self::UvSphere { .. }
            | Self::Cylinder { .. }
            | Self::Cone { .. }
            | Self::Torus { .. } => return rotational::component_count(self),
        };
        if !dimension.is_finite() || !(0. ..=MAX_DIMENSION).contains(&dimension) {
            return Err(SceneError(
                "primitive dimension must be finite and within 0..999999995904".into(),
            ));
        }
        let checked = || -> Option<usize> {
            Some(match self {
                Self::IcoSphere { .. } | Self::Monkey { .. } => {
                    unreachable!("legacy count returned above")
                }
                Self::UvSphere { .. }
                | Self::Cylinder { .. }
                | Self::Cone { .. }
                | Self::Torus { .. } => unreachable!("rotational count returned above"),
                Self::Plane { .. } => 13,
                Self::Cube { .. } => 50,
                Self::Circle {
                    vertices,
                    fill_type,
                    ..
                } => {
                    if !(3..=MAX_DIVISIONS).contains(vertices) {
                        return None;
                    }
                    let n = *vertices as usize;
                    match fill_type {
                        CircleFill::Nothing => n.checked_mul(2)?,
                        CircleFill::Ngon => n.checked_mul(3)?.checked_add(1)?,
                        CircleFill::Trifan => n.checked_mul(7)?.checked_add(1)?,
                    }
                }
                Self::Grid {
                    x_subdivisions,
                    y_subdivisions,
                    ..
                } => {
                    if !(1..=MAX_DIVISIONS).contains(x_subdivisions)
                        || !(1..=MAX_DIVISIONS).contains(y_subdivisions)
                    {
                        return None;
                    }
                    let (x, y) = (*x_subdivisions as usize, *y_subdivisions as usize);
                    let vertices = x.checked_add(1)?.checked_mul(y.checked_add(1)?)?;
                    let edges = x
                        .checked_mul(y.checked_add(1)?)?
                        .checked_add(y.checked_mul(x.checked_add(1)?)?)?;
                    vertices
                        .checked_add(edges)?
                        .checked_add(x.checked_mul(y)?.checked_mul(5)?)?
                }
            })
        };
        checked().ok_or_else(|| {
            SceneError("primitive subdivision range or component arithmetic is invalid".into())
        })
    }

    pub fn generate(&self, max_components: usize) -> Result<MeshAsset> {
        let required = self.component_count()?;
        if required > max_components {
            return Err(SceneError(format!(
                "primitive needs {required} components; generation budget is {max_components}"
            )));
        }
        let calc_uvs = match self {
            Self::IcoSphere { calc_uvs, .. }
            | Self::Monkey { calc_uvs, .. }
            | Self::Plane { calc_uvs, .. }
            | Self::Cube { calc_uvs, .. }
            | Self::Grid { calc_uvs, .. }
            | Self::Circle { calc_uvs, .. }
            | Self::UvSphere { calc_uvs, .. }
            | Self::Cylinder { calc_uvs, .. }
            | Self::Cone { calc_uvs, .. } => *calc_uvs,
            Self::Torus { generate_uvs, .. } => *generate_uvs,
        };
        let mut builder = Builder::new(calc_uvs);
        match self {
            Self::IcoSphere { .. } | Self::Monkey { .. } => legacy::generate(self, &mut builder)?,
            Self::UvSphere { .. }
            | Self::Cylinder { .. }
            | Self::Cone { .. }
            | Self::Torus { .. } => rotational::generate(self, &mut builder)?,
            Self::Plane { size, .. } => builder.grid(1, 1, *size as f32),
            Self::Grid {
                size,
                x_subdivisions,
                y_subdivisions,
                ..
            } => builder.grid(*x_subdivisions, *y_subdivisions, *size as f32),
            Self::Cube { size, scale, .. } => {
                // The fixed upstream version uses a unit cube when size is zero.
                let half = if *size == 0. {
                    0.5
                } else {
                    (*size as f32) * 0.5
                };
                for x in [-half, half] {
                    for y in [-half, half] {
                        for z in [-half, half] {
                            builder.vertex([
                                (x * scale[0] as f32) as f64,
                                (y * scale[1] as f32) as f64,
                                (z * scale[2] as f32) as f64,
                            ]);
                        }
                    }
                }
                let faces = [
                    [0, 1, 3, 2],
                    [2, 3, 7, 6],
                    [6, 7, 5, 4],
                    [4, 5, 1, 0],
                    [2, 6, 4, 0],
                    [7, 3, 1, 5],
                ];
                for (i, face) in faces.into_iter().enumerate() {
                    let (u, v) = match i.cmp(&4) {
                        std::cmp::Ordering::Less => (0.375, i as f64 * 0.25),
                        std::cmp::Ordering::Equal => (0.125, 0.5),
                        std::cmp::Ordering::Greater => (0.625, 0.5),
                    };
                    let points = face.map(|v| builder.asset.vertices[&vertex_id(v)]);
                    let a: [f64; 3] = std::array::from_fn(|i| points[1][i] - points[0][i]);
                    let b: [f64; 3] = std::array::from_fn(|i| points[2][i] - points[0][i]);
                    let normal = [
                        a[1] * b[2] - a[2] * b[1],
                        a[2] * b[0] - a[0] * b[2],
                        a[0] * b[1] - a[1] * b[0],
                    ];
                    let length = normal.iter().map(|n| n * n).sum::<f64>().sqrt();
                    let normal = if length == 0. {
                        [0., 0., 1.]
                    } else {
                        normal.map(|n| n / length)
                    };
                    builder.face(
                        &face,
                        vec![[u, v], [u + 0.25, v], [u + 0.25, v + 0.25], [u, v + 0.25]],
                        normal,
                    );
                }
            }
            Self::Circle {
                radius,
                vertices,
                fill_type,
                ..
            } => {
                let n = *vertices as usize;
                let radius = *radius as f32;
                let center = if *fill_type == CircleFill::Trifan {
                    Some(builder.vertex([0.; 3]))
                } else {
                    None
                };
                let mut ring = Vec::with_capacity(n);
                let mut uv = Vec::with_capacity(n);
                for i in 0..n {
                    let angle = std::f64::consts::TAU * i as f64 / n as f64;
                    let x = (-angle.sin() as f32) * radius;
                    let y = (angle.cos() as f32) * radius;
                    ring.push(builder.vertex([x as f64, y as f64, 0.]));
                    uv.push(if radius == 0. {
                        [0.; 2]
                    } else {
                        [
                            (x / radius * 0.5 + 0.5) as f64,
                            (y / radius * 0.5 + 0.5) as f64,
                        ]
                    });
                }
                match fill_type {
                    CircleFill::Nothing => {
                        for i in 0..n {
                            builder.edge(ring[i], ring[(i + 1) % n]);
                        }
                    }
                    CircleFill::Ngon => builder.face(&ring, uv, [0., 0., 1.]),
                    CircleFill::Trifan => {
                        for i in 0..n {
                            builder.face(
                                &[center.expect("fan center"), ring[i], ring[(i + 1) % n]],
                                vec![
                                    if radius == 0. { [0.; 2] } else { [0.5; 2] },
                                    uv[i],
                                    uv[(i + 1) % n],
                                ],
                                [0., 0., 1.],
                            );
                        }
                    }
                }
                if radius == 0. && calc_uvs && *fill_type != CircleFill::Nothing {
                    builder
                        .asset
                        .diagnostics
                        .push("degenerate_default_uv".into());
                }
            }
        }
        builder.asset.recipe = Some(PrimitiveRecipe {
            primitive: self.clone(),
            max_components,
            edited: false,
        });
        builder.asset.validate()?;
        Ok(builder.asset)
    }
}

struct Builder {
    asset: MeshAsset,
    edges: BTreeMap<[usize; 2], String>,
    calc_uvs: bool,
}
fn vertex_id(i: usize) -> String {
    format!("v{i:06}")
}
impl Builder {
    fn new(calc_uvs: bool) -> Self {
        Self {
            asset: MeshAsset {
                uv_layout: Some(UvLayout {
                    layers: if calc_uvs {
                        vec!["UVMap".into()]
                    } else {
                        vec![]
                    },
                    active: calc_uvs.then(|| "UVMap".into()),
                }),
                ..Default::default()
            },
            edges: BTreeMap::new(),
            calc_uvs,
        }
    }
    fn vertex(&mut self, position: [f64; 3]) -> usize {
        let index = self.asset.vertices.len();
        self.asset.vertices.insert(vertex_id(index), position);
        index
    }
    fn edge(&mut self, a: usize, b: usize) {
        let key = if a < b { [a, b] } else { [b, a] };
        if !self.edges.contains_key(&key) {
            let id = format!("e{:06}", self.edges.len());
            self.asset
                .edges
                .insert(id.clone(), [vertex_id(a), vertex_id(b)]);
            self.edges.insert(key, id);
        }
    }
    fn face(&mut self, indices: &[usize], uv: Vec<[f64; 2]>, normal: [f64; 3]) {
        for i in 0..indices.len() {
            self.edge(indices[i], indices[(i + 1) % indices.len()]);
        }
        self.asset.polygons.insert(
            format!("p{:06}", self.asset.polygons.len()),
            Polygon {
                vertices: indices.iter().map(|i| vertex_id(*i)).collect(),
                uv_layers: if self.calc_uvs {
                    BTreeMap::from([("UVMap".into(), uv)])
                } else {
                    BTreeMap::new()
                },
                corner_normals: Some(vec![normal; indices.len()]),
                normal: Some(normal),
                smooth: false,
                material_slot: None,
            },
        );
    }
    fn grid(&mut self, nx: u32, ny: u32, size: f32) {
        for y in 0..=ny {
            for x in 0..=nx {
                self.vertex([
                    ((x as f32 / nx as f32 - 0.5) * size) as f64,
                    ((y as f32 / ny as f32 - 0.5) * size) as f64,
                    0.,
                ]);
            }
        }
        for y in 0..ny {
            for x in 0..nx {
                let a = y as usize * (nx as usize + 1) + x as usize;
                let b = a + 1;
                let d = a + nx as usize + 1;
                let c = d + 1;
                let (u0, u1, v0, v1) = (
                    x as f32 / nx as f32,
                    (x + 1) as f32 / nx as f32,
                    y as f32 / ny as f32,
                    (y + 1) as f32 / ny as f32,
                );
                self.face(
                    &[a, b, c, d],
                    vec![
                        [u0 as f64, v0 as f64],
                        [u1 as f64, v0 as f64],
                        [u1 as f64, v1 as f64],
                        [u0 as f64, v1 as f64],
                    ],
                    [0., 0., 1.],
                );
            }
        }
    }
}

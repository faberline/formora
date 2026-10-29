// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! Component transforms with derived frames and persist-on-success receipts.
use super::{frame_math as math, selection::Elements};
use crate::scene::{Result, Scene, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
mod context;
mod geodesic;
mod gimbal;
mod influence;
mod inverse;
mod mirror;
mod normal_orientation;
mod random;
mod uv;

type Vector = [f32; 3];
type Matrix = [[f32; 3]; 3];
const IDENTITY: Matrix = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]];

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Axis {
    X,
    Y,
    #[default]
    Z,
}
impl Axis {
    fn index(self) -> usize {
        match self {
            Self::X => 0,
            Self::Y => 1,
            Self::Z => 2,
        }
    }
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Change {
    Translate {
        value: [f64; 3],
    },
    Rotate {
        radians: f64,
        #[serde(default)]
        axis: Axis,
    },
    Resize {
        value: [f64; 3],
    },
}
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Orientation {
    #[default]
    Global,
    Local,
    Parent,
    Cursor,
    View,
    Normal,
    Gimbal,
    Custom {
        matrix: [[f64; 3]; 3],
    },
}
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Pivot {
    #[default]
    Median,
    Bounds,
    Cursor,
    Active,
    Individual,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Falloff {
    Smooth,
    Sphere,
    Root,
    Sharp,
    Linear,
    Constant,
    Random,
    InverseSquare,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum RandomAlgorithm {
    #[serde(rename = "splitmix64_v1")]
    Splitmix64V1,
    #[serde(rename = "blender_5_2")]
    Blender52,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Proportional {
    pub radius: f64,
    pub falloff: Falloff,
    #[serde(default)]
    pub connected: bool,
    #[serde(default)]
    pub projected: bool,
    pub seed: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub random_algorithm: Option<RandomAlgorithm>,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Mirror {
    pub axis: Axis,
    #[serde(default)]
    pub topology: bool,
}
fn enabled() -> bool {
    true
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub entity: String,
    pub change: Change,
    #[serde(default)]
    pub orientation: Orientation,
    #[serde(default)]
    pub pivot: Pivot,
    pub center_override: Option<[f64; 3]>,
    #[serde(default)]
    pub constraint_axis: [bool; 3],
    pub proportional: Option<Proportional>,
    pub mirror: Option<Mirror>,
    #[serde(default)]
    pub correct_face_attributes: bool,
    #[serde(default = "enabled")]
    pub keep_connected: bool,
    #[serde(default = "super::primitives::default_budget")]
    pub max_components: usize,
}
#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct Receipt {
    pub command_index: usize,
    pub entity: String,
    pub mesh_asset: String,
    pub shared_instances: Vec<String>,
    pub basis_world: [[f64; 3]; 3],
    #[serde(skip_serializing_if = "BTreeMap::is_empty")]
    pub component_basis_local: BTreeMap<String, [[f64; 3]; 3]>,
    pub pivot_world: [f64; 3],
    pub centres_local: BTreeMap<String, [f64; 3]>,
    pub influence: BTreeMap<String, f64>,
    pub changed: Elements,
    pub random_seed: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub random_algorithm: Option<RandomAlgorithm>,
    #[serde(skip_serializing_if = "BTreeMap::is_empty")]
    pub mirror_sources: BTreeMap<String, String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub mirror_plane_vertices: Vec<String>,
    #[serde(skip_serializing_if = "std::collections::BTreeSet::is_empty")]
    pub attribute_faces: std::collections::BTreeSet<super::selection::FaceRef>,
}
fn finite(values: &[f64]) -> Result<()> {
    if values
        .iter()
        .any(|v| !v.is_finite() || !(*v as f32).is_finite())
    {
        return Err(SceneError(
            "mesh transform values must fit finite f32 values".into(),
        ));
    }
    Ok(())
}
fn sub(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[i] - b[i])
}
fn add(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[i] + b[i])
}
fn dot(a: Vector, b: Vector) -> f32 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}
fn normalized(a: Vector) -> Result<Vector> {
    let len = dot(a, a).sqrt();
    if !len.is_finite() || len == 0. {
        return Err(SceneError("unsafe mesh transform axis".into()));
    }
    Ok(a.map(|v| v / len))
}
fn rotation(axis: Vector, radians: f32) -> Matrix {
    let (s, c) = radians.sin_cos();
    let t = 1. - c;
    let [x, y, z] = axis;
    [
        [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
        [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
    ]
}

/// Compute on a private asset. Publish only after all calculations validate.
pub fn execute(scene: &mut Scene, request: &Request) -> Result<Receipt> {
    let context = context::Context::new(scene, request)?;
    let asset = &scene.mesh_assets[&context.asset];
    let influence = influence::calculate(&context, request)?;
    let mirror = mirror::Plan::new(&context, request)?;
    let mut next = asset.clone();
    let mut changed = Elements::default();
    let constrained = request.constraint_axis.iter().any(|v| *v);
    let count = request.constraint_axis.iter().filter(|v| **v).count();
    let mut axis_index = match request.change {
        Change::Rotate { axis, .. } => axis.index(),
        _ => 2,
    };
    if count == 1 {
        axis_index = request
            .constraint_axis
            .iter()
            .position(|v| *v)
            .expect("one axis");
    }
    if count == 2 {
        axis_index = request
            .constraint_axis
            .iter()
            .position(|v| !*v)
            .expect("one excluded axis");
    }
    let delta = if let Change::Translate { value } = request.change {
        finite(&value)?;
        let vector = std::array::from_fn(|i| {
            if constrained && !request.constraint_axis[i] {
                0.
            } else {
                value[i] as f32
            }
        });
        Some(math::vector(
            context.inverse,
            math::vector(context.basis, vector),
        ))
    } else {
        None
    };
    let resize = if let Change::Resize { value } = request.change {
        finite(&value)?;
        let diagonal = std::array::from_fn(|i| {
            std::array::from_fn(|j| {
                if i != j {
                    0.
                } else if constrained && !request.constraint_axis[i] {
                    1.
                } else {
                    value[i] as f32
                }
            })
        });
        Some(math::multiply(
            context.inverse,
            math::multiply(
                math::multiply(
                    context.basis,
                    math::multiply(diagonal, context.basis_inverse),
                ),
                context.object,
            ),
        ))
    } else {
        None
    };
    let axis = if let Change::Rotate { radians, .. } = request.change {
        finite(&[radians])?;
        let axis = std::array::from_fn(|i| context.basis[i][axis_index]);
        Some(if request.orientation == Orientation::Gimbal {
            if axis.iter().any(|v| !v.is_finite()) || dot(axis, axis) == 0. {
                return Err(SceneError("unsafe mesh transform gimbal axis".into()));
            }
            axis
        } else {
            normalized(axis)?
        })
    } else {
        None
    };
    let mut centres = BTreeMap::new();
    let mut component_bases = BTreeMap::new();
    let mut weights = BTreeMap::new();
    for (index, weight) in influence
        .weights
        .iter()
        .copied()
        .enumerate()
        .filter(|(i, w)| *w > 0. && mirror.sources[*i].is_none())
    {
        let id = &context.graph.vertex_ids[index];
        let original = context.positions[index];
        let origin = if request.pivot == Pivot::Individual {
            influence
                .origins
                .as_ref()
                .and_then(|origins| {
                    let origin = origins[index];
                    context.island_member[origin].then_some(origin)
                })
                .unwrap_or(index)
        } else {
            index
        };
        let centre = context.centres[origin];
        let component_basis = context.component_bases.as_ref().map(|bases| bases[origin]);
        if let Some(basis) = component_basis {
            component_bases.insert(id.clone(), basis.map(|row| row.map(f64::from)));
        }
        centres.insert(id.clone(), centre.map(f64::from));
        weights.insert(id.clone(), f64::from(weight));
        let position = match request.change {
            Change::Translate { .. } => {
                let delta = if let Some(basis) = component_basis {
                    let Change::Translate { value } = request.change else {
                        unreachable!()
                    };
                    let vector = std::array::from_fn(|i| {
                        if constrained && !request.constraint_axis[i] {
                            0.
                        } else {
                            value[i] as f32
                        }
                    });
                    let world = math::vector(context.basis, vector);
                    let vector = math::vector(context.basis_inverse, world);
                    math::vector(
                        context.inverse,
                        math::vector(context.object_axes, math::vector(basis, vector)),
                    )
                } else {
                    delta.expect("translation")
                };
                add(original, delta.map(|v| v * weight))
            }
            Change::Rotate { radians, .. } => {
                let axis = if let Some(basis) = component_basis.filter(|_| constrained && count < 3)
                {
                    let world = math::multiply(context.object_axes, basis);
                    std::array::from_fn(|i| world[i][axis_index])
                } else {
                    axis.expect("rotation axis")
                };
                let world = rotation(axis, radians as f32 * weight);
                let local = math::multiply(context.inverse, math::multiply(world, context.object));
                add(math::vector(local, sub(original, centre)), centre)
            }
            Change::Resize { .. } => {
                let resize = if let Some(basis) = component_basis {
                    let Change::Resize { value } = request.change else {
                        unreachable!()
                    };
                    let diagonal = std::array::from_fn(|i| {
                        std::array::from_fn(|j| {
                            if i != j {
                                0.
                            } else if constrained && !request.constraint_axis[i] {
                                1.
                            } else {
                                value[i] as f32
                            }
                        })
                    });
                    let local =
                        math::multiply(context.inverse, math::multiply(diagonal, context.object));
                    math::multiply(basis, math::multiply(local, math::inverse(basis)?))
                } else {
                    resize.expect("resize")
                };
                let moved = add(math::vector(resize, sub(original, centre)), centre);
                add(original, sub(moved, original).map(|v| v * weight))
            }
        };
        if position.iter().any(|v| !v.is_finite()) {
            return Err(SceneError(
                "mesh transform arithmetic exceeded finite f32 range".into(),
            ));
        }
        let position = position.map(f64::from);
        if position != asset.vertices[id] {
            changed.vertices.insert(id.clone());
            next.vertices.insert(id.clone(), position);
        }
    }
    mirror.apply(&context, &mut next);
    let mut mirror_sources = BTreeMap::new();
    for (destination, source) in mirror.sources.iter().enumerate() {
        if let Some(source) = source {
            let id = &context.graph.vertex_ids[destination];
            let source_id = &context.graph.vertex_ids[*source];
            mirror_sources.insert(id.clone(), source_id.clone());
            if let Some(weight) = weights.get(source_id).copied() {
                weights.insert(id.clone(), weight);
                centres.insert(id.clone(), context.centres[destination].map(f64::from));
                if let Some(bases) = &context.component_bases {
                    component_bases
                        .insert(id.clone(), bases[destination].map(|r| r.map(f64::from)));
                }
            }
        }
    }
    changed.vertices = next
        .vertices
        .iter()
        .filter(|(id, p)| asset.vertices[*id] != **p)
        .map(|(id, _)| id.clone())
        .collect();
    for edge in &context.graph.edges {
        if edge
            .vertices
            .iter()
            .any(|v| changed.vertices.contains(&context.graph.vertex_ids[*v]))
        {
            changed.edges.insert(edge.id.clone());
        }
    }
    for face in &context.graph.faces {
        if face
            .vertices
            .iter()
            .any(|v| changed.vertices.contains(&context.graph.vertex_ids[*v]))
        {
            changed.faces.insert(face.key.clone());
        }
    }
    let attribute_faces = uv::apply(&context, request, &mirror, asset, &mut next)?;
    changed.faces.extend(attribute_faces.iter().cloned());
    if !changed.vertices.is_empty() || !attribute_faces.is_empty() {
        if let Some(recipe) = &mut next.recipe {
            recipe.edited = true;
        }
        if !changed.vertices.is_empty() {
            super::normals::apply_automatic(&mut next)?;
        }
    }
    next.validate()?;
    let receipt = Receipt {
        command_index: 0,
        entity: request.entity.clone(),
        mesh_asset: context.asset.clone(),
        shared_instances: context.instances,
        basis_world: context.basis.map(|r| r.map(f64::from)),
        component_basis_local: component_bases,
        pivot_world: context.pivot.map(f64::from),
        centres_local: centres,
        influence: weights,
        changed,
        random_seed: request.proportional.as_ref().and_then(|p| p.seed),
        random_algorithm: request
            .proportional
            .as_ref()
            .and_then(|p| p.random_algorithm),
        mirror_sources,
        attribute_faces,
        mirror_plane_vertices: mirror
            .plane
            .iter()
            .map(|i| context.graph.vertex_ids[*i].clone())
            .collect(),
    };
    scene.mesh_assets.insert(context.asset, next);
    Ok(receipt)
}

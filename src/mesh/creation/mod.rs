// SPDX-FileCopyrightText: 2004 Blender Authors
// SPDX-FileCopyrightText: 2009 Blender Authors
// SPDX-FileCopyrightText: 2010-2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
//! Agent-first placement and mesh insertion. No legacy UI mode is required.
use super::{
    MeshAsset, UvLayout,
    primitives::{Primitive, PrimitiveRecipe},
    selection::{self, Editing, Elements, FaceRef},
};
use crate::scene::{Entity, EntityKind, Geometry, Result, Scene, SceneError, Transform, valid_id};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
mod inverse4;
mod math;

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct AuthoringContext {
    #[serde(default)]
    pub cursor_location: [f64; 3],
    #[serde(default)]
    pub cursor_rotation: [f64; 3],
    #[serde(default)]
    pub view_rotation: [f64; 3],
}
impl AuthoringContext {
    pub fn validate(&self) -> Result<()> {
        finite(&self.cursor_location)?;
        finite(&self.cursor_rotation)?;
        finite(&self.view_rotation)
    }
}
#[derive(Debug, Clone, Copy, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Alignment {
    #[default]
    World,
    Cursor,
    View,
}
#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Placement {
    #[serde(default)]
    pub align: Alignment,
    pub location: Option<[f64; 3]>,
    pub rotation: Option<[f64; 3]>,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ObjectCreation {
    pub id: String,
    pub asset: String,
    pub name: String,
    pub primitive: Primitive,
    #[serde(default)]
    pub placement: Placement,
    #[serde(default)]
    pub preview_selection: bool,
    #[serde(default = "super::primitives::default_budget")]
    pub max_components: usize,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MeshInsertion {
    pub entity: String,
    pub prefix: String,
    pub primitive: Primitive,
    #[serde(default)]
    pub placement: Placement,
    #[serde(default = "enabled")]
    pub preview_selection: bool,
    #[serde(default = "super::primitives::default_budget")]
    pub max_components: usize,
}
fn enabled() -> bool {
    true
}
#[derive(Debug, Clone, Copy, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum CreationKind {
    NewObject,
    AppendMesh,
}
#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct CreationReceipt {
    pub command_index: usize,
    pub kind: CreationKind,
    pub mesh_asset: String,
    pub entity: String,
    pub created: Elements,
    pub edit_ready: bool,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CreationFrame {
    pub matrix: [[f64; 4]; 3],
}
fn finite(values: &[f64]) -> Result<()> {
    if values
        .iter()
        .any(|v| !v.is_finite() || v.abs() > f32::MAX as f64)
    {
        return Err(SceneError(
            "creation coordinates and angles must fit finite f32 values".into(),
        ));
    }
    Ok(())
}
impl CreationFrame {
    pub fn validate(&self) -> Result<()> {
        for row in &self.matrix {
            finite(row)?;
        }
        Ok(())
    }
    pub fn generate(&self, primitive: &Primitive, budget: usize) -> Result<MeshAsset> {
        self.validate()?;
        let mut neutral = primitive.clone();
        let scale = neutral.neutralize_frame()?;
        let mut asset = neutral.generate(budget)?;
        let matrix = self.matrix.map(|r| {
            [
                r[0] as f32 * scale[0],
                r[1] as f32 * scale[1],
                r[2] as f32 * scale[2],
                r[3] as f32,
            ]
        });
        for point in asset.vertices.values_mut() {
            let p = point.map(|v| v as f32);
            let next = matrix.map(|r| r[0] * p[0] + r[1] * p[1] + r[2] * p[2] + r[3]);
            if next.iter().any(|v| !v.is_finite()) {
                return Err(SceneError("created geometry exceeds finite range".into()));
            }
            *point = next.map(f64::from);
        }
        super::primitives::recompute_normals(&mut asset);
        conic_uvs(&mut asset, primitive, matrix);
        asset.recipe = Some(PrimitiveRecipe {
            primitive: primitive.clone(),
            max_components: budget,
            edited: false,
            creation_frame: Some(self.clone()),
        });
        asset.validate()?;
        Ok(asset)
    }
}
// The fixed source classifies cap UVs after transforming the face normal.
// Its singular 4x4 inverse is the zero matrix, so collapsed caps use the UV centre.
fn conic_uvs(asset: &mut MeshAsset, primitive: &Primitive, matrix: [[f32; 4]; 3]) {
    use super::primitives::CircleFill;
    let (bottom, top, capped) = match primitive {
        Primitive::Cylinder {
            radius,
            end_fill_type,
            ..
        } => (
            *radius as f32,
            *radius as f32,
            *end_fill_type != CircleFill::Nothing,
        ),
        Primitive::Cone {
            radius1,
            radius2,
            end_fill_type,
            ..
        } => (
            *radius1 as f32,
            *radius2 as f32,
            *end_fill_type != CircleFill::Nothing,
        ),
        _ => return,
    };
    let basis = matrix.map(|r| [r[0], r[1], r[2]]);
    let inverse = math::inverse(basis).ok();
    let up = basis.map(|r| r[2]);
    let radius = if capped { 0.24_f32 } else { 0.5_f32 };
    let top_scale = if top != 0. {
        radius / top
    } else if bottom != 0. {
        radius / bottom
    } else {
        radius
    };
    let bottom_scale = if bottom != 0. {
        radius / bottom
    } else {
        top_scale
    };
    for polygon in asset.polygons.values_mut() {
        if polygon.vertices.len() == 4 && top != 0. && bottom != 0. {
            continue;
        }
        let mut normal = [0_f32; 3];
        for i in 0..polygon.vertices.len() {
            let a = asset.vertices
                [&polygon.vertices[(i + polygon.vertices.len() - 1) % polygon.vertices.len()]]
                .map(|v| v as f32);
            let b = asset.vertices[&polygon.vertices[i]].map(|v| v as f32);
            for j in 0..3 {
                normal[j] += (a[(j + 1) % 3] - b[(j + 1) % 3]) * (a[(j + 2) % 3] + b[(j + 2) % 3]);
            }
        }
        let upper = (0..3).map(|i| normal[i] * up[i]).sum::<f32>() > 0.;
        let x = if !capped {
            0.5
        } else if upper {
            0.25
        } else {
            0.75
        };
        let y = if capped { 0.25 } else { 0.5 };
        let scale = if upper { top_scale } else { bottom_scale };
        for uv in polygon.uv_layers.values_mut() {
            for (id, uv) in polygon.vertices.iter().zip(uv) {
                let point = asset.vertices[id];
                let local = inverse
                    .map(|inv| {
                        math::vector(inv, std::array::from_fn(|i| point[i] as f32 - matrix[i][3]))
                    })
                    .unwrap_or([0.; 3]);
                *uv = [(x + local[0] * scale) as f64, (y + local[1] * scale) as f64];
            }
        }
    }
}
fn resolve(
    primitive: &Primitive,
    placement: &Placement,
    context: &AuthoringContext,
) -> Result<([f64; 3], [f64; 3])> {
    context.validate()?;
    let location = placement.location.unwrap_or(context.cursor_location);
    finite(&location)?;
    let torus = matches!(primitive, Primitive::Torus { .. });
    let rotation = if torus && placement.rotation.is_none() {
        [0.; 3]
    } else if !torus && placement.rotation.is_some() {
        placement.rotation.unwrap()
    } else {
        match placement.align {
            Alignment::World => placement.rotation.unwrap_or([0.; 3]),
            Alignment::Cursor => context.cursor_rotation,
            Alignment::View => {
                let mut rotation = context.view_rotation;
                if matches!(primitive, Primitive::Monkey { .. }) {
                    rotation[0] = (rotation[0] as f32 - std::f32::consts::FRAC_PI_2) as f64;
                }
                rotation
            }
        }
    };
    finite(&rotation)?;
    Ok((
        location.map(|v| v as f32 as f64),
        rotation.map(|v| v as f32 as f64),
    ))
}
fn frame(
    primitive: &Primitive,
    location: [f64; 3],
    rotation: [f64; 3],
    world: math::Mat4,
) -> Result<CreationFrame> {
    let object = std::array::from_fn(|r| std::array::from_fn(|c| world[r][c] as f32));
    let inv = math::inverse(object)?;
    if matches!(primitive, Primitive::Torus { .. }) {
        let inverse = inverse4::inverse(world.map(|r| r.map(|v| v as f32)))?;
        let rotation = math::euler(rotation, false);
        let matrix = std::array::from_fn(|r| {
            let mut row = [0.; 4];
            for (c, item) in row.iter_mut().enumerate().take(3) {
                *item = (inverse[r][0] * rotation[0][c] + inverse[r][1] * rotation[1][c])
                    + inverse[r][2] * rotation[2][c];
            }
            row[3] = (inverse[r][0] * location[0] as f32 + inverse[r][1] * location[1] as f32)
                + (inverse[r][2] * location[2] as f32 + inverse[r][3]);
            row.map(f64::from)
        });
        return Ok(CreationFrame { matrix });
    }
    let basis = math::inverse(math::multiply(
        math::inverse(math::euler(rotation, true))?,
        object,
    ))?;
    let delta = std::array::from_fn(|i| location[i] as f32 - world[i][3] as f32);
    let translation = math::vector(inv, delta);
    let frame = CreationFrame {
        matrix: std::array::from_fn(|r| {
            [
                basis[r][0] as f64,
                basis[r][1] as f64,
                basis[r][2] as f64,
                translation[r] as f64,
            ]
        }),
    };
    frame.validate()?;
    Ok(frame)
}
fn elements(asset: &MeshAsset) -> Result<Elements> {
    let topology = selection::topology(asset)?;
    Ok(Elements {
        vertices: topology.vertices.into_iter().collect(),
        edges: topology.edges.into_keys().collect(),
        faces: topology.faces.into_iter().map(|f| f.face).collect(),
    })
}
pub fn create(scene: &mut Scene, request: &ObjectCreation) -> Result<CreationReceipt> {
    if !valid_id(&request.id) || !valid_id(&request.asset) {
        return Err(SceneError("invalid primitive object or asset ID".into()));
    }
    if scene.entities.contains_key(&request.id) || scene.mesh_assets.contains_key(&request.asset) {
        return Err(SceneError(
            "primitive object or asset already exists".into(),
        ));
    }
    let context = scene.authoring_context.clone().unwrap_or_default();
    let (location, rotation) = resolve(&request.primitive, &request.placement, &context)?;
    let basis = math::euler(rotation, false);
    let world = std::array::from_fn(|r| {
        std::array::from_fn(|c| {
            if r == 3 {
                if c == 3 { 1. } else { 0. }
            } else if c == 3 {
                location[r]
            } else {
                basis[r][c] as f64
            }
        })
    });
    let frame = frame(&request.primitive, location, rotation, world)?;
    let mut asset = frame.generate(&request.primitive, request.max_components)?;
    let created = elements(&asset)?;
    asset.editing = Some(Editing {
        selected: created.clone(),
        preview: request.preview_selection,
        ..Default::default()
    });
    let entity = Entity {
        name: request.name.clone(),
        parent: None,
        transform: Transform {
            translation: location,
            rotation: math::quaternion(basis),
            scale: [1.; 3],
        },
        content: EntityKind::Mesh {
            geometry: Geometry::Asset {
                id: request.asset.clone(),
            },
            material: None,
        },
    };
    scene.mesh_assets.insert(request.asset.clone(), asset);
    scene.entities.insert(request.id.clone(), entity);
    Ok(CreationReceipt {
        command_index: 0,
        kind: CreationKind::NewObject,
        mesh_asset: request.asset.clone(),
        entity: request.id.clone(),
        created,
        edit_ready: true,
    })
}
fn count(asset: &MeshAsset) -> Result<usize> {
    let topology = selection::topology(asset)?;
    let mut total = topology
        .vertices
        .len()
        .checked_add(topology.edges.len())
        .and_then(|n| n.checked_add(topology.faces.len()));
    for face in topology.faces {
        total = total.and_then(|n| n.checked_add(face.vertices.len()));
    }
    total.ok_or_else(|| SceneError("merged component count overflow".into()))
}
fn reset_uv(count: usize, torus: bool) -> Vec<[f64; 2]> {
    if torus {
        return vec![[0.; 2]; count];
    }
    match count {
        3 => vec![[0., 0.], [1., 0.], [1., 1.]],
        4 => vec![[0., 0.], [1., 0.], [1., 1.], [0., 1.]],
        _ => {
            let mut angle = 0f32;
            let delta = (1. / count as f32) * std::f32::consts::PI * 2.;
            (0..count)
                .map(|_| {
                    let uv = [
                        (0.5 * angle.sin() + 0.5) as f64,
                        (0.5 * angle.cos() + 0.5) as f64,
                    ];
                    angle += delta;
                    uv
                })
                .collect()
        }
    }
}
pub fn append(scene: &mut Scene, request: &MeshInsertion) -> Result<CreationReceipt> {
    if !valid_id(&request.prefix) || request.prefix.len() > 100 {
        return Err(SceneError(
            "creation prefix must be a valid ID of at most 100 bytes".into(),
        ));
    }
    let entity = scene
        .entities
        .get(&request.entity)
        .ok_or_else(|| SceneError("unknown insertion entity".into()))?;
    let EntityKind::Mesh {
        geometry: Geometry::Asset { id },
        ..
    } = &entity.content
    else {
        return Err(SceneError("insertion requires a mesh asset entity".into()));
    };
    let asset_id = id.clone();
    let original = &scene.mesh_assets[&asset_id];
    let required = count(original)?
        .checked_add(request.primitive.component_count()?)
        .ok_or_else(|| SceneError("merged component budget overflow".into()))?;
    if required > request.max_components {
        return Err(SceneError(format!(
            "insertion needs {required} merged components; generation budget is {}",
            request.max_components
        )));
    }
    let context = scene.authoring_context.clone().unwrap_or_default();
    let (location, rotation) = resolve(&request.primitive, &request.placement, &context)?;
    let frame = frame(
        &request.primitive,
        location,
        rotation,
        math::world(scene, &request.entity)?,
    )?;
    let generated = frame.generate(&request.primitive, request.max_components)?;
    let mut merged = original.clone();
    let torus = matches!(request.primitive, Primitive::Torus { .. });
    let generated_uv = generated
        .uv_layout
        .as_ref()
        .and_then(|l| l.active.as_ref())
        .cloned();
    let existing_layers = merged
        .uv_layout
        .as_ref()
        .map(|l| l.layers.clone())
        .unwrap_or_else(|| {
            merged
                .polygons
                .values()
                .next()
                .map(|p| p.uv_layers.keys().cloned().collect())
                .or_else(|| {
                    merged
                        .triangles
                        .values()
                        .next()
                        .map(|p| p.uv_layers.keys().cloned().collect())
                })
                .unwrap_or_default()
        });
    let mut layout = merged.uv_layout.clone().unwrap_or(UvLayout {
        active: existing_layers.first().cloned(),
        layers: existing_layers,
    });
    if layout.layers.is_empty() && generated_uv.is_some() {
        layout = UvLayout {
            layers: vec!["UVMap".into()],
            active: Some("UVMap".into()),
        };
        for polygon in merged.polygons.values_mut() {
            polygon
                .uv_layers
                .insert("UVMap".into(), reset_uv(polygon.vertices.len(), torus));
        }
        for triangle in merged.triangles.values_mut() {
            triangle.uv_layers.insert(
                "UVMap".into(),
                reset_uv(3, torus).try_into().expect("triangle UV size"),
            );
        }
    }
    if layout.active.is_none() && generated_uv.is_some() {
        layout.active = layout.layers.first().cloned();
    }
    merged.uv_layout = Some(layout.clone());
    let rename = |id: &str| format!("{}_{}", request.prefix, id);
    let vertices: BTreeMap<_, _> = generated
        .vertices
        .keys()
        .map(|id| (id.clone(), rename(id)))
        .collect();
    let mut created = Elements::default();
    for (id, point) in &generated.vertices {
        let new = &vertices[id];
        if merged.vertices.contains_key(new) {
            return Err(SceneError(format!(
                "created vertex ID already exists: {new}"
            )));
        }
        merged.vertices.insert(new.clone(), *point);
        created.vertices.insert(new.clone());
    }
    let old_edges = selection::topology(original)?.edges;
    for (id, pair) in &generated.edges {
        let new = rename(id);
        if old_edges.contains_key(&new) {
            return Err(SceneError(format!("created edge ID already exists: {new}")));
        }
        merged
            .edges
            .insert(new.clone(), pair.each_ref().map(|v| vertices[v].clone()));
        created.edges.insert(new);
    }
    for (id, polygon) in generated.polygons {
        let new = rename(&id);
        if merged.polygons.contains_key(&new) {
            return Err(SceneError(format!(
                "created polygon ID already exists: {new}"
            )));
        }
        let mut polygon = polygon;
        polygon.vertices = polygon
            .vertices
            .iter()
            .map(|v| vertices[v].clone())
            .collect();
        let uv = generated_uv
            .as_ref()
            .and_then(|name| polygon.uv_layers.get(name))
            .cloned();
        polygon.uv_layers = layout
            .layers
            .iter()
            .map(|name| {
                (
                    name.clone(),
                    if Some(name) == layout.active.as_ref() {
                        uv.clone().unwrap_or(vec![[0.; 2]; polygon.vertices.len()])
                    } else {
                        vec![[0.; 2]; polygon.vertices.len()]
                    },
                )
            })
            .collect();
        polygon.material_slot = if merged.material_slots.is_empty() {
            None
        } else {
            Some(if torus {
                merged.active_material_index
            } else {
                0
            })
        };
        merged.polygons.insert(new.clone(), polygon);
        created.faces.insert(FaceRef::Polygon(new));
    }
    for diagnostic in generated.diagnostics {
        if !merged.diagnostics.contains(&diagnostic) {
            merged.diagnostics.push(diagnostic);
        }
    }
    let mut editing = merged.editing.take().unwrap_or_default();
    editing.selected = created.clone();
    editing.history.clear();
    editing.preview = request.preview_selection;
    merged.editing = Some(editing);
    if let Some(recipe) = &mut merged.recipe {
        recipe.edited = true;
    }
    merged.validate()?;
    scene.mesh_assets.insert(asset_id.clone(), merged);
    Ok(CreationReceipt {
        command_index: 0,
        kind: CreationKind::AppendMesh,
        mesh_asset: asset_id,
        entity: request.entity.clone(),
        created,
        edit_ready: true,
    })
}

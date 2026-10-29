//! Shared mesh assets. Preview tessellation never rewrites source topology.
use crate::scene::{Result, SceneError, unique_map, valid_id};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
pub mod creation;
mod frame_math;
pub mod normals;
pub mod primitives;
pub mod selection;
pub mod snap;
mod tessellation;
pub mod transform;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
pub struct PolygonTriangle {
    pub polygon: String,
    pub corners: [usize; 3],
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
pub struct TessellationDiagnostic {
    pub polygon: String,
    pub code: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, JsonSchema)]
pub struct Tessellation {
    pub triangles: Vec<PolygonTriangle>,
    pub diagnostics: Vec<TessellationDiagnostic>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Triangle {
    pub vertices: [String; 3],
    /// One value for each corner, in the same order as vertices.
    #[serde(deserialize_with = "unique_map")]
    pub uv_layers: BTreeMap<String, [[f64; 2]; 3]>,
    pub corner_normals: Option<[[f64; 3]; 3]>,
    pub material_slot: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Polygon {
    pub vertices: Vec<String>,
    #[serde(deserialize_with = "unique_map")]
    pub uv_layers: BTreeMap<String, Vec<[f64; 2]>>,
    pub corner_normals: Option<Vec<[f64; 3]>>,
    pub normal: Option<[f64; 3]>,
    pub smooth: bool,
    pub material_slot: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct UvLayout {
    pub layers: Vec<String>,
    pub active: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MeshAsset {
    #[serde(deserialize_with = "unique_map")]
    pub vertices: BTreeMap<String, [f64; 3]>,
    #[serde(deserialize_with = "unique_map")]
    pub triangles: BTreeMap<String, Triangle>,
    #[serde(
        default,
        deserialize_with = "unique_map",
        skip_serializing_if = "BTreeMap::is_empty"
    )]
    pub edges: BTreeMap<String, [String; 2]>,
    #[serde(
        default,
        deserialize_with = "unique_map",
        skip_serializing_if = "BTreeMap::is_empty"
    )]
    pub polygons: BTreeMap<String, Polygon>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub uv_layout: Option<UvLayout>,
    pub material_slots: Vec<Option<String>>,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub active_material_index: usize,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub recipe: Option<primitives::PrimitiveRecipe>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub diagnostics: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub editing: Option<selection::Editing>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub vertex_groups: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub vertex_weights: Option<selection::VertexWeights>,
    #[serde(
        default,
        deserialize_with = "crate::scene::unique_set",
        skip_serializing_if = "BTreeSet::is_empty"
    )]
    pub edge_seams: BTreeSet<String>,
    #[serde(
        default,
        deserialize_with = "crate::scene::unique_set",
        skip_serializing_if = "BTreeSet::is_empty"
    )]
    pub smooth_triangles: BTreeSet<String>,
}

impl MeshAsset {
    pub fn tessellate(&self) -> Result<Tessellation> {
        self.tessellate_without(&BTreeSet::new())
    }

    pub(crate) fn tessellate_without(&self, hidden: &BTreeSet<String>) -> Result<Tessellation> {
        self.validate()?;
        let mut output = Tessellation::default();
        for (id, polygon) in &self.polygons {
            if hidden.contains(id) {
                continue;
            }
            let points: Vec<_> = polygon.vertices.iter().map(|v| self.vertices[v]).collect();
            let triangles = tessellation::triangulate(&points)
                .map_err(|e| SceneError(format!("polygon {id}: {e}")))?;
            let used = triangles
                .iter()
                .flatten()
                .copied()
                .collect::<BTreeSet<_>>()
                .len();
            if used < points.len() {
                output.diagnostics.push(TessellationDiagnostic {
                    polygon: id.clone(),
                    code: if triangles.is_empty() {
                        "degenerate_polygon"
                    } else {
                        "collapsed_polygon_corners"
                    }
                    .into(),
                });
            }
            output
                .triangles
                .extend(triangles.into_iter().map(|corners| PolygonTriangle {
                    polygon: id.clone(),
                    corners,
                }));
        }
        Ok(output)
    }

    pub fn validate(&self) -> Result<()> {
        self.validate_with_topology(false).map(|_| ())
    }

    pub(crate) fn validated_topology(&self) -> Result<selection::Graph> {
        Ok(self
            .validate_with_topology(true)?
            .expect("requested topology"))
    }

    fn validate_with_topology(&self, require_graph: bool) -> Result<Option<selection::Graph>> {
        if (self.material_slots.is_empty() && self.active_material_index != 0)
            || (!self.material_slots.is_empty()
                && self.active_material_index >= self.material_slots.len())
        {
            return Err(SceneError(
                "active material index is outside the asset slots".into(),
            ));
        }
        if let Some(recipe) = &self.recipe {
            if let Some(frame) = &recipe.creation_frame {
                frame.validate()?;
            }
            if recipe.primitive.component_count()? > recipe.max_components {
                return Err(SceneError(
                    "primitive recipe exceeds its generation budget".into(),
                ));
            }
        }
        if self.diagnostics.iter().any(|code| !valid_id(code)) {
            return Err(SceneError("invalid mesh diagnostic code".into()));
        }
        let layout = self
            .uv_layout
            .as_ref()
            .map(|layout| layout.layers.iter().collect::<BTreeSet<_>>());
        if let Some(names) = &layout {
            let supplied = self.uv_layout.as_ref().expect("present layout");
            if names.len() != supplied.layers.len()
                || names.iter().any(|n| !valid_layer(n))
                || supplied
                    .active
                    .as_ref()
                    .is_some_and(|name| !names.contains(name))
            {
                return Err(SceneError("invalid mesh UV layout".into()));
            }
        }
        for (id, position) in &self.vertices {
            if !valid_id(id) || !position.iter().all(|n| n.is_finite()) {
                return Err(SceneError(format!("invalid mesh vertex: {id}")));
            }
        }
        let mut pairs = BTreeSet::new();
        for (id, [a, b]) in &self.edges {
            if !valid_id(id)
                || a == b
                || !self.vertices.contains_key(a)
                || !self.vertices.contains_key(b)
                || !pairs.insert(edge_pair(a, b))
            {
                return Err(SceneError(format!("invalid mesh edge: {id}")));
            }
        }
        for (id, polygon) in &self.polygons {
            let count = polygon.vertices.len();
            if !valid_id(id)
                || count < 3
                || polygon.vertices.iter().collect::<BTreeSet<_>>().len() != count
                || polygon
                    .vertices
                    .iter()
                    .any(|v| !self.vertices.contains_key(v))
                || (0..count).any(|i| {
                    !pairs.contains(&edge_pair(
                        &polygon.vertices[i],
                        &polygon.vertices[(i + 1) % count],
                    ))
                })
                || polygon
                    .material_slot
                    .is_some_and(|i| i >= self.material_slots.len())
                || polygon.normal.is_some_and(|n| !valid_normal(&n))
                || polygon
                    .corner_normals
                    .as_ref()
                    .is_some_and(|ns| ns.len() != count || ns.iter().any(|n| !valid_normal(n)))
            {
                return Err(SceneError(format!("invalid mesh polygon: {id}")));
            }
            let names = polygon.uv_layers.keys().collect::<BTreeSet<_>>();
            if match &layout {
                Some(layout) => names != *layout,
                None => !names.is_empty(),
            } {
                return Err(SceneError(format!(
                    "polygon UV layers do not match layout: {id}"
                )));
            }
            if polygon.uv_layers.iter().any(|(name, values)| {
                !valid_layer(name)
                    || values.len() != count
                    || !values.iter().flatten().all(|n| n.is_finite())
            }) {
                return Err(SceneError(format!("invalid polygon UV values: {id}")));
            }
        }
        for (id, triangle) in &self.triangles {
            if !valid_id(id)
                || triangle.vertices.iter().collect::<BTreeSet<_>>().len() != 3
                || triangle
                    .vertices
                    .iter()
                    .any(|v| !self.vertices.contains_key(v))
                || triangle
                    .material_slot
                    .is_some_and(|i| i >= self.material_slots.len())
            {
                return Err(SceneError(format!("invalid mesh triangle: {id}")));
            }
            for (layer, uv) in &triangle.uv_layers {
                if !valid_layer(layer) || !uv.iter().flatten().all(|n| n.is_finite()) {
                    return Err(SceneError(format!("invalid mesh UV layer: {layer}")));
                }
            }
            if layout
                .as_ref()
                .is_some_and(|names| triangle.uv_layers.keys().collect::<BTreeSet<_>>() != *names)
            {
                return Err(SceneError(format!(
                    "triangle UV layers do not match layout: {id}"
                )));
            }
            if let Some(normals) = &triangle.corner_normals {
                for n in normals {
                    if !valid_normal(n) {
                        return Err(SceneError(format!("invalid mesh corner normal: {id}")));
                    }
                }
            }
        }
        selection::validate_attributes(self, require_graph)
    }
}

fn is_zero(value: &usize) -> bool {
    *value == 0
}

fn valid_layer(name: &str) -> bool {
    !name.is_empty() && name.len() <= 128
}

fn valid_normal(n: &[f64; 3]) -> bool {
    n.iter().all(|x| x.is_finite())
        && (n.iter().all(|x| *x == 0.) || (n.iter().map(|x| x * x).sum::<f64>() - 1.).abs() <= 1e-6)
}

fn edge_pair<'a>(a: &'a str, b: &'a str) -> (&'a str, &'a str) {
    if a < b { (a, b) } else { (b, a) }
}

//! Shared triangle assets. Component IDs are independent of position and ordering.
use crate::scene::{Result, SceneError, unique_map, valid_id};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

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

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MeshAsset {
    #[serde(deserialize_with = "unique_map")]
    pub vertices: BTreeMap<String, [f64; 3]>,
    #[serde(deserialize_with = "unique_map")]
    pub triangles: BTreeMap<String, Triangle>,
    pub material_slots: Vec<Option<String>>,
}

impl MeshAsset {
    pub fn validate(&self) -> Result<()> {
        for (id, position) in &self.vertices {
            if !valid_id(id) || !position.iter().all(|n| n.is_finite()) {
                return Err(SceneError(format!("invalid mesh vertex: {id}")));
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
                if layer.is_empty()
                    || layer.len() > 128
                    || !uv.iter().flatten().all(|n| n.is_finite())
                {
                    return Err(SceneError(format!("invalid mesh UV layer: {layer}")));
                }
            }
            if let Some(normals) = &triangle.corner_normals {
                for n in normals {
                    let length_squared = n.iter().map(|x| x * x).sum::<f64>();
                    if !n.iter().all(|n| n.is_finite())
                        || (n.iter().any(|x| *x != 0.0) && (length_squared - 1.0).abs() > 1e-6)
                    {
                        return Err(SceneError(format!("invalid mesh corner normal: {id}")));
                    }
                }
            }
        }
        Ok(())
    }
}

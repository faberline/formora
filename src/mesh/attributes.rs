//! Persistent integer values use component IDs, independently of their values.
use super::MeshAsset;
use crate::scene::{Result, SceneError, unique_map};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(transparent)]
pub struct IntegerLayer(#[serde(deserialize_with = "unique_map")] pub BTreeMap<String, i32>);

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct IntegerAttributes {
    #[serde(default, deserialize_with = "unique_map")]
    pub vertices: BTreeMap<String, IntegerLayer>,
    #[serde(default, deserialize_with = "unique_map")]
    pub edges: BTreeMap<String, IntegerLayer>,
    #[serde(default, deserialize_with = "unique_map")]
    pub polygons: BTreeMap<String, IntegerLayer>,
    #[serde(default, deserialize_with = "unique_map")]
    pub triangles: BTreeMap<String, IntegerLayer>,
}

fn validate_layers<T>(
    domain: &str,
    layers: &BTreeMap<String, IntegerLayer>,
    components: &BTreeMap<String, T>,
) -> Result<()> {
    for (name, layer) in layers {
        if !super::valid_layer(name) {
            return Err(SceneError(format!("invalid integer {domain} layer name: {name}")));
        }
        if layer.0.len() != components.len() || !layer.0.keys().eq(components.keys()) {
            return Err(SceneError(format!(
                "integer {domain} layer {name} must cover every component exactly"
            )));
        }
    }
    Ok(())
}

fn add_defaults<'a>(
    layers: &mut BTreeMap<String, IntegerLayer>,
    ids: impl Iterator<Item = &'a String> + Clone,
) {
    for layer in layers.values_mut() {
        for id in ids.clone() {
            layer.0.entry(id.clone()).or_insert(0);
        }
    }
}

impl IntegerAttributes {
    pub(crate) fn validate(&self, asset: &MeshAsset) -> Result<()> {
        validate_layers("vertex", &self.vertices, &asset.vertices)?;
        validate_layers("edge", &self.edges, &asset.edges)?;
        validate_layers("polygon", &self.polygons, &asset.polygons)?;
        validate_layers("triangle", &self.triangles, &asset.triangles)
    }

    /// Primitive insertion supplies zero values in existing layers. Call only
    /// after validating the complete original asset, before validating insertion.
    pub(crate) fn extend_zero_defaults<'a>(
        &mut self,
        vertices: impl Iterator<Item = &'a String> + Clone,
        edges: impl Iterator<Item = &'a String> + Clone,
        polygons: impl Iterator<Item = &'a String> + Clone,
        triangles: impl Iterator<Item = &'a String> + Clone,
    ) {
        add_defaults(&mut self.vertices, vertices);
        add_defaults(&mut self.edges, edges);
        add_defaults(&mut self.polygons, polygons);
        add_defaults(&mut self.triangles, triangles);
    }
}

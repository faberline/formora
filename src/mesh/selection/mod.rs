//! Persistent selection and typed topology identity. The runtime uses Rust only.
use super::MeshAsset;
use crate::scene::{Result, SceneError, unique_map, unique_set};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

mod interior;
mod operations;
mod topology;
pub(crate) use topology::Graph;
pub use topology::{TopologyDescription, TopologyFace};

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize, JsonSchema,
)]
#[serde(rename_all = "snake_case")]
pub enum Domain {
    Vertex,
    Edge,
    Face,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize, JsonSchema)]
#[serde(
    tag = "kind",
    content = "id",
    rename_all = "snake_case",
    deny_unknown_fields
)]
pub enum FaceRef {
    Polygon(String),
    Triangle(String),
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "domain", rename_all = "snake_case", deny_unknown_fields)]
pub enum Component {
    Vertex { id: String },
    Edge { id: String },
    Face { face: FaceRef },
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Elements {
    #[serde(default, deserialize_with = "unique_set")]
    pub vertices: BTreeSet<String>,
    #[serde(default, deserialize_with = "unique_set")]
    pub edges: BTreeSet<String>,
    #[serde(default, deserialize_with = "unique_set")]
    pub faces: BTreeSet<FaceRef>,
}

fn vertex_mode() -> BTreeSet<Domain> {
    BTreeSet::from([Domain::Vertex])
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Editing {
    #[serde(default = "enabled", skip_serializing_if = "is_enabled")]
    pub preview: bool,
    #[serde(default = "vertex_mode", deserialize_with = "unique_set")]
    pub mode: BTreeSet<Domain>,
    #[serde(default)]
    pub selected: Elements,
    #[serde(default)]
    pub hidden: Elements,
    #[serde(default)]
    pub history: Vec<Component>,
    pub active_face: Option<FaceRef>,
}
impl Default for Editing {
    fn default() -> Self {
        Self {
            preview: true,
            mode: vertex_mode(),
            selected: Elements::default(),
            hidden: Elements::default(),
            history: Vec::new(),
            active_face: None,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(transparent)]
pub struct GroupWeights(#[serde(deserialize_with = "unique_map")] pub BTreeMap<String, f64>);

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(transparent)]
pub struct VertexWeights(
    #[serde(deserialize_with = "unique_map")] pub BTreeMap<String, GroupWeights>,
);

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ModeAction {
    Enable,
    Disable,
    #[default]
    Toggle,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum CountComparison {
    Less,
    #[default]
    Equal,
    Greater,
    NotEqual,
}
impl CountComparison {
    fn matches(self, value: usize, count: u32) -> bool {
        match self {
            Self::Less => value < count as usize,
            Self::Equal => value == count as usize,
            Self::Greater => value > count as usize,
            Self::NotEqual => value != count as usize,
        }
    }
}
fn enabled() -> bool {
    true
}
fn is_enabled(value: &bool) -> bool {
    *value
}
fn four() -> u32 {
    4
}
fn not_equal() -> CountComparison {
    CountComparison::NotEqual
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Selector {
    Mode {
        domain: Domain,
        #[serde(default)]
        action: ModeAction,
        #[serde(default)]
        extend: bool,
        #[serde(default)]
        expand: bool,
    },
    NonManifold {
        #[serde(default = "enabled")]
        extend: bool,
        #[serde(default = "enabled")]
        wire: bool,
        #[serde(default = "enabled")]
        boundary: bool,
        #[serde(default = "enabled")]
        multiple_faces: bool,
        #[serde(default = "enabled")]
        non_contiguous: bool,
        #[serde(default = "enabled")]
        vertices: bool,
    },
    Loose {
        #[serde(default)]
        extend: bool,
    },
    InteriorFaces {},
    FacesBySides {
        #[serde(default = "four")]
        #[schemars(range(min = 3, max = 2147483647))]
        count: u32,
        #[serde(default)]
        comparison: CountComparison,
        #[serde(default = "enabled")]
        extend: bool,
    },
    Poles {
        #[serde(default = "four")]
        #[schemars(range(min = 0, max = 2147483647))]
        count: u32,
        #[serde(default = "not_equal")]
        comparison: CountComparison,
        #[serde(default = "enabled")]
        exclude_nonmanifold: bool,
        #[serde(default)]
        extend: bool,
    },
    Ungrouped {
        #[serde(default)]
        extend: bool,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Completed,
    Unchanged,
}

#[derive(Debug, Clone, Serialize, JsonSchema)]
pub struct CommandOutcome {
    pub command_index: usize,
    pub mesh_asset: String,
    pub outcome: Outcome,
}

pub fn topology(asset: &MeshAsset) -> Result<TopologyDescription> {
    Ok(Graph::new(asset)?.describe())
}

pub(crate) fn validate_attributes(asset: &MeshAsset, require_graph: bool) -> Result<Option<Graph>> {
    let names: BTreeSet<_> = asset.vertex_groups.iter().collect();
    if names.len() != asset.vertex_groups.len()
        || names.iter().any(|name| !super::valid_layer(name))
    {
        return Err(SceneError("invalid vertex group names".into()));
    }
    if let Some(weights) = &asset.vertex_weights {
        for (vertex, groups) in &weights.0 {
            if !asset.vertices.contains_key(vertex)
                || groups.0.iter().any(|(name, weight)| {
                    !names.contains(name) || !weight.is_finite() || !(0.0..=1.0).contains(weight)
                })
            {
                return Err(SceneError("invalid mesh vertex weights".into()));
            }
        }
    }
    if asset
        .smooth_triangles
        .iter()
        .any(|id| !asset.triangles.contains_key(id))
    {
        return Err(SceneError("unknown smooth triangle".into()));
    }
    if require_graph || asset.editing.is_some() || !asset.edge_seams.is_empty() {
        let graph = Graph::new(asset)?;
        if asset
            .edge_seams
            .iter()
            .any(|id| !graph.edge_index.contains_key(id))
        {
            return Err(SceneError("unknown seam edge".into()));
        }
        if let Some(editing) = &asset.editing {
            graph.validate(editing)?;
        }
        return Ok(Some(graph));
    }
    Ok(None)
}

pub fn set_editing(asset: &mut MeshAsset, editing: Option<Editing>) -> Result<()> {
    let graph = Graph::new(asset)?;
    let next = if let Some(mut editing) = editing {
        graph.validate(&editing)?;
        let mut flags = graph.flags(&editing.selected);
        let hidden = graph.flags(&editing.hidden);
        graph.expand_down(&mut flags, &hidden);
        graph.flush_up(&mut flags, &hidden, &editing.mode);
        editing.selected = graph.elements(&flags);
        editing
            .history
            .retain(|entry| graph.component_selected(entry, &flags));
        graph.validate(&editing)?;
        Some(editing)
    } else {
        None
    };
    asset.editing = next;
    Ok(())
}

pub fn apply(asset: &mut MeshAsset, selector: &Selector) -> Result<Outcome> {
    let graph = Graph::new(asset)?;
    let mut editing = asset.editing.clone().unwrap_or_default();
    graph.validate(&editing)?;
    let outcome = graph.apply(asset, &mut editing, selector)?;
    graph.validate(&editing)?;
    if outcome == Outcome::Completed {
        editing.preview = true;
        asset.editing = Some(editing);
    }
    Ok(outcome)
}

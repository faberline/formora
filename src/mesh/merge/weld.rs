// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
use super::{Cluster, FaceMapping, Lineage, Method};
use crate::mesh::{
    MeshAsset, Polygon, Triangle,
    selection::{Component, Domain, Elements, FaceRef, Graph, GroupWeights},
};
use crate::scene::{Result, SceneError};
use std::collections::{BTreeMap, BTreeSet};

mod uv;

#[derive(Clone)]
struct Face {
    key: FaceRef,
    origin: FaceRef,
    vertices: Vec<String>,
    uv: BTreeMap<String, Vec<[f64; 2]>>,
    normals: Option<Vec<[f64; 3]>>,
    normal: Option<[f64; 3]>,
    smooth: bool,
    material: Option<usize>,
}
impl Face {
    fn from_asset(asset: &MeshAsset, key: &FaceRef) -> Self {
        match key {
            FaceRef::Polygon(id) => {
                let face = &asset.polygons[id];
                Self {
                    key: key.clone(),
                    origin: key.clone(),
                    vertices: face.vertices.clone(),
                    uv: face.uv_layers.clone(),
                    normals: face.corner_normals.clone(),
                    normal: face.normal,
                    smooth: face.smooth,
                    material: face.material_slot,
                }
            }
            FaceRef::Triangle(id) => {
                let face = &asset.triangles[id];
                Self {
                    key: key.clone(),
                    origin: key.clone(),
                    vertices: face.vertices.to_vec(),
                    uv: face
                        .uv_layers
                        .iter()
                        .map(|(name, values)| (name.clone(), values.to_vec()))
                        .collect(),
                    normals: face.corner_normals.map(|values| values.to_vec()),
                    normal: None,
                    smooth: asset.smooth_triangles.contains(id),
                    material: face.material_slot,
                }
            }
        }
    }
    fn subset(&self, indices: &[usize]) -> Self {
        let mut face = self.clone();
        face.vertices = indices.iter().map(|i| self.vertices[*i].clone()).collect();
        face.uv = self
            .uv
            .iter()
            .map(|(name, values)| (name.clone(), indices.iter().map(|i| values[*i]).collect()))
            .collect();
        face.normals = self
            .normals
            .as_ref()
            .map(|values| indices.iter().map(|i| values[*i]).collect());
        face
    }
    fn store(&self, asset: &mut MeshAsset) -> Result<()> {
        match &self.key {
            FaceRef::Polygon(id) => {
                asset.polygons.insert(
                    id.clone(),
                    Polygon {
                        vertices: self.vertices.clone(),
                        uv_layers: self.uv.clone(),
                        corner_normals: self.normals.clone(),
                        normal: self.normal,
                        smooth: self.smooth,
                        material_slot: self.material,
                    },
                );
            }
            FaceRef::Triangle(id) => {
                let vertices = self
                    .vertices
                    .clone()
                    .try_into()
                    .map_err(|_| SceneError("invalid welded triangle length".into()))?;
                let uv_layers = self
                    .uv
                    .iter()
                    .map(|(name, values)| {
                        Ok((
                            name.clone(),
                            values.clone().try_into().map_err(|_| {
                                SceneError("invalid welded triangle UV length".into())
                            })?,
                        ))
                    })
                    .collect::<Result<_>>()?;
                let corner_normals = self
                    .normals
                    .clone()
                    .map(|values| {
                        values
                            .try_into()
                            .map_err(|_| SceneError("invalid welded triangle normal length".into()))
                    })
                    .transpose()?;
                asset.triangles.insert(
                    id.clone(),
                    Triangle {
                        vertices,
                        uv_layers,
                        corner_normals,
                        material_slot: self.material,
                    },
                );
                if self.smooth {
                    asset.smooth_triangles.insert(id.clone());
                }
            }
        }
        Ok(())
    }
}

fn pair(a: &str, b: &str) -> [String; 2] {
    if a < b {
        [a.into(), b.into()]
    } else {
        [b.into(), a.into()]
    }
}
fn fresh(prefix: &str, used: &mut BTreeSet<String>) -> Result<String> {
    for index in 0..=u64::MAX {
        let id = format!("{prefix}_{index}");
        if used.insert(id.clone()) {
            return Ok(id);
        }
    }
    Err(SceneError("merge component identity exhausted".into()))
}
fn canonical(vertices: &[String]) -> Vec<String> {
    // The least cyclic representation, independent of face direction.
    let start = vertices
        .iter()
        .enumerate()
        .min_by_key(|(_, id)| *id)
        .expect("nonempty face")
        .0;
    let n = vertices.len();
    let forward: Vec<_> = (0..n).map(|i| vertices[(start + i) % n].clone()).collect();
    let reverse: Vec<_> = (0..n)
        .map(|i| vertices[(start + n - i) % n].clone())
        .collect();
    forward.min(reverse)
}

fn split(
    face: Face,
    map: &BTreeMap<String, String>,
    used: &mut BTreeSet<String>,
    output: &mut Vec<Face>,
) -> Result<()> {
    let n = face.vertices.len();
    let mut cut = None;
    for (i, vertex) in face.vertices.iter().enumerate() {
        if let Some(target) = map.get(vertex).filter(|target| *target != vertex) {
            if let Some(j) = face.vertices.iter().position(|id| id == target) {
                if (i + 1) % n != j && (j + 1) % n != i {
                    cut = Some((i, j));
                    break;
                }
            }
        }
    }
    if let Some((i, j)) = cut {
        let path = |a: usize, b: usize| {
            let count = (b + n - a) % n;
            (0..=count)
                .map(|offset| (a + offset) % n)
                .collect::<Vec<_>>()
        };
        let first = face.subset(&path(i, j));
        let mut second = face.subset(&path(j, i));
        second.key = FaceRef::Polygon(fresh("merge_face", used)?);
        split(first, map, used, output)?;
        split(second, map, used, output)?;
    } else {
        output.push(face);
    }
    Ok(())
}

pub(super) fn apply(
    asset: &mut MeshAsset,
    graph: &Graph,
    clusters: &[Cluster],
    method: Method,
    uvs: bool,
) -> Result<Lineage> {
    let original = asset.clone();
    let mut lineage = Lineage::default();
    for id in &graph.vertex_ids {
        lineage.vertices.insert(id.clone(), id.clone());
    }
    for edge in &graph.edges {
        lineage.edges.insert(edge.id.clone(), edge.id.clone());
    }
    for face in &graph.faces {
        lineage.faces.push(FaceMapping {
            source: face.key.clone(),
            survivors: vec![face.key.clone()],
        });
    }
    if clusters.is_empty() {
        return Ok(lineage);
    }
    let mut faces: Vec<_> = graph
        .faces
        .iter()
        .map(|face| Face::from_asset(asset, &face.key))
        .collect();
    if uvs {
        uv::apply(&mut faces, graph, clusters, method, asset)?;
    }
    for cluster in clusters {
        let survivor = &graph.vertex_ids[cluster.survivor];
        let ids: Vec<_> = cluster
            .vertices
            .iter()
            .map(|v| graph.vertex_ids[*v].as_str())
            .collect();
        if matches!(method, Method::Center | Method::Cursor) && ids.len() > 1 {
            if let Some(attributes) = &mut asset.integer_attributes {
                attributes.interpolate_vertices(survivor, &ids)?;
            }
            if let Some(weights) = &mut asset.vertex_weights {
                let mut groups: BTreeMap<String, f32> = BTreeMap::new();
                let factor = 1_f32 / ids.len() as f32;
                for id in &ids {
                    if let Some(source) = weights.0.get(*id) {
                        for (name, value) in &source.0 {
                            let value = *value as f32 * factor;
                            if value != 0. {
                                *groups.entry(name.clone()).or_insert(0.) += value;
                            }
                        }
                    }
                }
                weights.0.insert(
                    survivor.clone(),
                    GroupWeights(
                        groups
                            .into_iter()
                            .map(|(name, value)| (name, f64::from(value.min(1.))))
                            .collect(),
                    ),
                );
            }
        }
        asset
            .vertices
            .insert(survivor.clone(), cluster.point.map(f64::from));
        for id in ids {
            lineage.vertices.insert(id.into(), survivor.clone());
        }
    }
    let vmap = &lineage.vertices;
    let mapped = |id: &String| vmap[id].clone();
    asset.vertices.retain(|id, _| vmap[id] == *id);
    if let Some(weights) = &mut asset.vertex_weights {
        weights.0.retain(|id, _| asset.vertices.contains_key(id));
    }
    if let Some(attributes) = &mut asset.integer_attributes {
        for layer in attributes.vertices.values_mut() {
            layer.0.retain(|id, _| asset.vertices.contains_key(id));
        }
    }
    let mut used: BTreeSet<_> = asset
        .polygons
        .keys()
        .chain(asset.triangles.keys())
        .cloned()
        .collect();
    let mut split_faces = Vec::new();
    for face in faces {
        split(face, vmap, &mut used, &mut split_faces)?;
    }

    // Reserve original edges whose endpoints survive. Mapped duplicates use
    // their actual existing data, even if the duplicate is visited later.
    let mut pairs: BTreeMap<[String; 2], String> = BTreeMap::new();
    let mut origins = BTreeMap::new();
    let mut explicit = BTreeSet::new();
    let mut edge_used: BTreeSet<_> = graph.edges.iter().map(|edge| edge.id.clone()).collect();
    for edge in &graph.edges {
        let ids = edge.vertices.map(|v| graph.vertex_ids[v].clone());
        if ids.iter().all(|id| vmap[id] == *id) {
            pairs.insert(pair(&ids[0], &ids[1]), edge.id.clone());
            origins.insert(edge.id.clone(), edge.id.clone());
            if original.edges.contains_key(&edge.id) {
                explicit.insert(edge.id.clone());
            }
        }
    }
    let mut seams: BTreeSet<_> = original
        .edge_seams
        .iter()
        .filter(|id| origins.contains_key(*id))
        .cloned()
        .collect();
    lineage.edges.clear();
    for edge in &graph.edges {
        let ids = edge.vertices.map(|v| graph.vertex_ids[v].clone());
        let dest = ids.map(|id| vmap[&id].clone());
        if dest[0] == dest[1] {
            continue;
        }
        let key = pair(&dest[0], &dest[1]);
        let target = if let Some(id) = pairs.get(&key) {
            id.clone()
        } else {
            let id = fresh("merge_edge", &mut edge_used)?;
            pairs.insert(key, id.clone());
            origins.insert(id.clone(), edge.id.clone());
            explicit.insert(id.clone());
            id
        };
        if original.edge_seams.contains(&edge.id) {
            seams.insert(target.clone());
        }
        lineage.edges.insert(edge.id.clone(), target);
    }
    asset.edges = pairs
        .iter()
        .filter(|(_, id)| explicit.contains(*id))
        .map(|(vertices, id)| (id.clone(), vertices.clone()))
        .collect();
    asset.edge_seams = seams;
    if let Some(attributes) = &mut asset.integer_attributes {
        for (name, layer) in &mut attributes.edges {
            let old = &original
                .integer_attributes
                .as_ref()
                .expect("existing attributes")
                .edges[name]
                .0;
            layer.0 = asset
                .edges
                .keys()
                .map(|id| (id.clone(), old.get(&origins[id]).copied().unwrap_or(0)))
                .collect();
        }
    }

    let mut ready = Vec::new();
    for face in split_faces {
        let indices: Vec<_> = (0..face.vertices.len())
            .filter(|i| {
                vmap[&face.vertices[*i]] != vmap[&face.vertices[(*i + 1) % face.vertices.len()]]
            })
            .collect();
        let mut result = face.subset(&indices);
        result.vertices = result.vertices.iter().map(mapped).collect();
        if result.vertices.len() < 3
            || result.vertices.iter().collect::<BTreeSet<_>>().len() != result.vertices.len()
        {
            continue;
        }
        let geometry_changed = result.vertices != face.vertices
            || face
                .vertices
                .iter()
                .any(|id| original.vertices[id] != asset.vertices[&vmap[id]]);
        if geometry_changed {
            result.normal = None;
            result.normals = None;
        }
        ready.push(result);
    }
    let mut retained: BTreeMap<Vec<String>, Face> = BTreeMap::new();
    let mut source_faces: BTreeMap<FaceRef, BTreeSet<FaceRef>> = BTreeMap::new();
    // Unmodified existing faces win over newly rebuilt duplicates.
    ready.sort_by_key(|face| {
        face.vertices
            .iter()
            .any(|id| original.vertices.get(id) != asset.vertices.get(id))
            || match &face.key {
                FaceRef::Polygon(id) => original
                    .polygons
                    .get(id)
                    .is_none_or(|old| old.vertices != face.vertices),
                FaceRef::Triangle(id) => original
                    .triangles
                    .get(id)
                    .is_none_or(|old| old.vertices.as_slice() != face.vertices),
            }
    });
    for face in ready {
        let key = canonical(&face.vertices);
        let survivor = if let Some(existing) = retained.get_mut(&key) {
            existing.smooth |= face.smooth;
            existing.key.clone()
        } else {
            let key_id = face.key.clone();
            retained.insert(key, face.clone());
            key_id
        };
        source_faces
            .entry(face.origin)
            .or_default()
            .insert(survivor);
    }
    asset.polygons.clear();
    asset.triangles.clear();
    asset.smooth_triangles.clear();
    for face in retained.values() {
        face.store(asset)?;
    }
    if let Some(attributes) = &mut asset.integer_attributes {
        let old = original
            .integer_attributes
            .as_ref()
            .expect("existing attributes");
        for (name, layer) in &mut attributes.polygons {
            layer.0 = retained
                .values()
                .filter_map(|face| match &face.key {
                    FaceRef::Polygon(id) => Some((
                        id.clone(),
                        match &face.origin {
                            FaceRef::Polygon(source) => old.polygons[name].0[source],
                            FaceRef::Triangle(source) => old
                                .triangles
                                .get(name)
                                .and_then(|layer| layer.0.get(source))
                                .copied()
                                .unwrap_or(0),
                        },
                    )),
                    _ => None,
                })
                .collect();
        }
        for (name, layer) in &mut attributes.triangles {
            layer.0 = retained
                .values()
                .filter_map(|face| match (&face.key, &face.origin) {
                    (FaceRef::Triangle(id), FaceRef::Triangle(source)) => {
                        Some((id.clone(), old.triangles[name].0[source]))
                    }
                    _ => None,
                })
                .collect();
        }
    }
    lineage.faces = graph
        .faces
        .iter()
        .map(|face| FaceMapping {
            source: face.key.clone(),
            survivors: source_faces
                .get(&face.key)
                .map(|keys| keys.iter().cloned().collect())
                .unwrap_or_default(),
        })
        .collect();

    if let Some(editing) = &mut asset.editing {
        let old = original.editing.as_ref().expect("existing editing");
        let map_elements = |elements: &Elements, merge_flags: bool| Elements {
            vertices: elements
                .vertices
                .iter()
                .filter_map(|id| {
                    if merge_flags || vmap[id] == *id {
                        Some(vmap[id].clone())
                    } else {
                        None
                    }
                })
                .collect(),
            edges: elements
                .edges
                .iter()
                .filter_map(|id| {
                    lineage
                        .edges
                        .get(id)
                        .filter(|target| merge_flags || *target == id)
                        .cloned()
                })
                .collect(),
            faces: elements
                .faces
                .iter()
                .flat_map(|face| {
                    source_faces
                        .get(face)
                        .into_iter()
                        .flatten()
                        .filter(move |target| merge_flags || *target == face)
                        .cloned()
                })
                .collect(),
        };
        editing.selected = map_elements(&old.selected, true);
        editing.hidden = map_elements(&old.hidden, false);
        if !editing.mode.contains(&Domain::Vertex) {
            editing.selected = Elements::default();
        }
        let mut seen = BTreeSet::new();
        editing.history = old
            .history
            .iter()
            .filter_map(|component| {
                let item = match component {
                    Component::Vertex { id } => Component::Vertex {
                        id: vmap[id].clone(),
                    },
                    Component::Edge { id } => Component::Edge {
                        id: lineage.edges.get(id)?.clone(),
                    },
                    Component::Face { face } => Component::Face {
                        face: source_faces.get(face)?.iter().next()?.clone(),
                    },
                };
                let selected = match &item {
                    Component::Vertex { id } => editing.selected.vertices.contains(id),
                    Component::Edge { id } => editing.selected.edges.contains(id),
                    Component::Face { face } => editing.selected.faces.contains(face),
                };
                (selected && seen.insert(item.clone())).then_some(item)
            })
            .collect();
        editing.active_face = old
            .active_face
            .as_ref()
            .and_then(|face| source_faces.get(face)?.iter().next().cloned());
    }
    Ok(lineage)
}

pub(super) fn changed(before: &MeshAsset, after: &MeshAsset, old: &Graph, new: &Graph) -> Elements {
    let vertices = new
        .vertex_ids
        .iter()
        .filter(|id| {
            before
                .vertices
                .get(*id)
                .is_some_and(|point| point != &after.vertices[*id])
                || before.vertices.contains_key(*id)
                    && (before
                        .vertex_weights
                        .as_ref()
                        .and_then(|weights| weights.0.get(*id))
                        != after
                            .vertex_weights
                            .as_ref()
                            .and_then(|weights| weights.0.get(*id))
                        || before.integer_attributes.as_ref().map(|attrs| {
                            attrs
                                .vertices
                                .iter()
                                .map(|(name, layer)| (name, layer.0.get(*id)))
                                .collect::<Vec<_>>()
                        }) != after.integer_attributes.as_ref().map(|attrs| {
                            attrs
                                .vertices
                                .iter()
                                .map(|(name, layer)| (name, layer.0.get(*id)))
                                .collect::<Vec<_>>()
                        }))
        })
        .cloned()
        .collect();
    let edges = new
        .edges
        .iter()
        .filter(|edge| {
            old.edge_index.contains_key(&edge.id)
                && (before.edge_seams.contains(&edge.id) != after.edge_seams.contains(&edge.id)
                    || before.edges.get(&edge.id) != after.edges.get(&edge.id))
        })
        .map(|edge| edge.id.clone())
        .collect();
    let faces = new
        .faces
        .iter()
        .filter(|face| {
            old.face_index.contains_key(&face.key)
                && match &face.key {
                    FaceRef::Polygon(id) => before.polygons[id] != after.polygons[id],
                    FaceRef::Triangle(id) => {
                        before.triangles[id] != after.triangles[id]
                            || before.smooth_triangles.contains(id)
                                != after.smooth_triangles.contains(id)
                    }
                }
        })
        .map(|face| face.key.clone())
        .collect();
    Elements {
        vertices,
        edges,
        faces,
    }
}

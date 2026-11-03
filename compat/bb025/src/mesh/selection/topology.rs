// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
// Flag propagation and manifold queries follow the pinned BMesh rules.
use super::{Component, Domain, Editing, Elements, FaceRef};
use crate::mesh::MeshAsset;
use crate::scene::{Result, SceneError, valid_id};
use schemars::JsonSchema;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Serialize, JsonSchema)]
pub struct TopologyFace {
    pub face: FaceRef,
    pub vertices: Vec<String>,
    pub edges: Vec<String>,
}
#[derive(Debug, Serialize, JsonSchema)]
pub struct TopologyDescription {
    pub vertices: Vec<String>,
    pub edges: BTreeMap<String, [String; 2]>,
    pub faces: Vec<TopologyFace>,
}
pub(crate) struct Edge {
    pub id: String,
    pub vertices: [usize; 2],
    pub faces: Vec<(usize, bool)>,
}
pub(crate) struct Face {
    pub key: FaceRef,
    pub vertices: Vec<usize>,
    pub edges: Vec<usize>,
}
pub(crate) struct Graph {
    pub vertex_ids: Vec<String>,
    pub positions: Vec<[f64; 3]>,
    pub vertex_index: BTreeMap<String, usize>,
    pub edge_index: BTreeMap<String, usize>,
    pub face_index: BTreeMap<FaceRef, usize>,
    pub edges: Vec<Edge>,
    pub faces: Vec<Face>,
    pub vertex_edges: Vec<Vec<usize>>,
    pub vertex_faces: Vec<Vec<usize>>,
}
#[derive(Clone)]
pub(crate) struct Flags {
    pub v: Vec<bool>,
    pub e: Vec<bool>,
    pub f: Vec<bool>,
}

impl Graph {
    pub fn new(asset: &MeshAsset) -> Result<Self> {
        let vertex_ids: Vec<_> = asset.vertices.keys().cloned().collect();
        let positions = asset.vertices.values().copied().collect();
        let vertex_index: BTreeMap<_, _> = vertex_ids
            .iter()
            .cloned()
            .enumerate()
            .map(|(i, id)| (id, i))
            .collect();
        let mut result = Self {
            vertex_edges: vec![Vec::new(); vertex_ids.len()],
            vertex_faces: vec![Vec::new(); vertex_ids.len()],
            vertex_ids,
            positions,
            vertex_index,
            edge_index: BTreeMap::new(),
            face_index: BTreeMap::new(),
            edges: Vec::new(),
            faces: Vec::new(),
        };
        let mut pairs = BTreeMap::new();
        for (id, pair) in &asset.edges {
            let mut vertices = [result.vertex(&pair[0])?, result.vertex(&pair[1])?];
            vertices.sort();
            if !valid_id(id) || vertices[0] == vertices[1] || pairs.contains_key(&vertices) {
                return Err(SceneError("invalid topology edge".into()));
            }
            pairs.insert(vertices, result.edges.len());
            result.edge_index.insert(id.clone(), result.edges.len());
            result.edges.push(Edge {
                id: id.clone(),
                vertices,
                faces: Vec::new(),
            });
        }
        let mut faces: Vec<_> = asset
            .polygons
            .iter()
            .map(|(id, f)| (FaceRef::Polygon(id.clone()), f.vertices.clone()))
            .chain(
                asset
                    .triangles
                    .iter()
                    .map(|(id, f)| (FaceRef::Triangle(id.clone()), f.vertices.to_vec())),
            )
            .collect();
        faces.sort_by(|a, b| a.0.cmp(&b.0));
        for (key, ids) in faces {
            let vertices: Vec<_> = ids
                .iter()
                .map(|id| result.vertex(id))
                .collect::<Result<_>>()?;
            if vertices.len() < 3
                || vertices.iter().collect::<BTreeSet<_>>().len() != vertices.len()
            {
                return Err(SceneError("invalid topology face".into()));
            }
            let face_index = result.faces.len();
            let mut face_edges = Vec::new();
            for i in 0..vertices.len() {
                let a = vertices[i];
                let b = vertices[(i + 1) % vertices.len()];
                let pair = if a < b { [a, b] } else { [b, a] };
                let ei = if let Some(e) = pairs.get(&pair) {
                    *e
                } else {
                    let mut salt = 0u64;
                    let id = loop {
                        let mut hash = Sha256::new();
                        for v in pair {
                            let name = &result.vertex_ids[v];
                            hash.update((name.len() as u64).to_le_bytes());
                            hash.update(name.as_bytes());
                        }
                        hash.update(salt.to_le_bytes());
                        let candidate = format!("edge_{:x}", hash.finalize());
                        if !result.edge_index.contains_key(&candidate) {
                            break candidate;
                        }
                        salt = salt
                            .checked_add(1)
                            .ok_or_else(|| SceneError("derived edge identity exhausted".into()))?;
                    };
                    let ei = result.edges.len();
                    pairs.insert(pair, ei);
                    result.edge_index.insert(id.clone(), ei);
                    result.edges.push(Edge {
                        id,
                        vertices: pair,
                        faces: Vec::new(),
                    });
                    ei
                };
                result.edges[ei].faces.push((face_index, a < b));
                face_edges.push(ei);
            }
            for &v in &vertices {
                result.vertex_faces[v].push(face_index);
            }
            result.face_index.insert(key.clone(), face_index);
            result.faces.push(Face {
                key,
                vertices,
                edges: face_edges,
            });
        }
        for (ei, edge) in result.edges.iter().enumerate() {
            for v in edge.vertices {
                result.vertex_edges[v].push(ei);
            }
        }
        Ok(result)
    }
    fn vertex(&self, id: &str) -> Result<usize> {
        self.vertex_index
            .get(id)
            .copied()
            .ok_or_else(|| SceneError(format!("unknown topology vertex: {id}")))
    }
    pub fn describe(&self) -> TopologyDescription {
        TopologyDescription {
            vertices: self.vertex_ids.clone(),
            edges: self
                .edges
                .iter()
                .map(|e| (e.id.clone(), e.vertices.map(|v| self.vertex_ids[v].clone())))
                .collect(),
            faces: self
                .faces
                .iter()
                .map(|f| TopologyFace {
                    face: f.key.clone(),
                    vertices: f
                        .vertices
                        .iter()
                        .map(|v| self.vertex_ids[*v].clone())
                        .collect(),
                    edges: f.edges.iter().map(|e| self.edges[*e].id.clone()).collect(),
                })
                .collect(),
        }
    }
    pub fn validate(&self, state: &Editing) -> Result<()> {
        if state.mode.is_empty() {
            return Err(SceneError("selection mode must not be empty".into()));
        }
        for elements in [&state.selected, &state.hidden] {
            if elements
                .vertices
                .iter()
                .any(|id| !self.vertex_index.contains_key(id))
                || elements
                    .edges
                    .iter()
                    .any(|id| !self.edge_index.contains_key(id))
                || elements
                    .faces
                    .iter()
                    .any(|id| !self.face_index.contains_key(id))
            {
                return Err(SceneError(
                    "selection references an unknown component".into(),
                ));
            }
        }
        if !state.selected.vertices.is_disjoint(&state.hidden.vertices)
            || !state.selected.edges.is_disjoint(&state.hidden.edges)
            || !state.selected.faces.is_disjoint(&state.hidden.faces)
        {
            return Err(SceneError("hidden components cannot be selected".into()));
        }
        let flags = self.flags(&state.selected);
        if state.history.iter().collect::<BTreeSet<_>>().len() != state.history.len()
            || state
                .history
                .iter()
                .any(|entry| !self.component_selected(entry, &flags))
        {
            return Err(SceneError("invalid selection history".into()));
        }
        if state
            .active_face
            .as_ref()
            .is_some_and(|id| !self.face_index.contains_key(id))
        {
            return Err(SceneError("unknown active face".into()));
        }
        Ok(())
    }
    pub fn flags(&self, elements: &Elements) -> Flags {
        Flags {
            v: self
                .vertex_ids
                .iter()
                .map(|id| elements.vertices.contains(id))
                .collect(),
            e: self
                .edges
                .iter()
                .map(|e| elements.edges.contains(&e.id))
                .collect(),
            f: self
                .faces
                .iter()
                .map(|f| elements.faces.contains(&f.key))
                .collect(),
        }
    }
    pub fn elements(&self, flags: &Flags) -> Elements {
        Elements {
            vertices: self
                .vertex_ids
                .iter()
                .zip(&flags.v)
                .filter(|(_, on)| **on)
                .map(|(id, _)| id.clone())
                .collect(),
            edges: self
                .edges
                .iter()
                .zip(&flags.e)
                .filter(|(_, on)| **on)
                .map(|(e, _)| e.id.clone())
                .collect(),
            faces: self
                .faces
                .iter()
                .zip(&flags.f)
                .filter(|(_, on)| **on)
                .map(|(f, _)| f.key.clone())
                .collect(),
        }
    }
    pub fn component_selected(&self, item: &Component, flags: &Flags) -> bool {
        match item {
            Component::Vertex { id } => self.vertex_index.get(id).is_some_and(|i| flags.v[*i]),
            Component::Edge { id } => self.edge_index.get(id).is_some_and(|i| flags.e[*i]),
            Component::Face { face } => self.face_index.get(face).is_some_and(|i| flags.f[*i]),
        }
    }
    pub fn select_vertex(&self, flags: &mut Flags, hidden: &Flags, v: usize) -> bool {
        if !hidden.v[v] {
            flags.v[v] = true;
            true
        } else {
            false
        }
    }
    pub fn select_edge(&self, flags: &mut Flags, hidden: &Flags, e: usize) -> bool {
        if !hidden.e[e] {
            flags.e[e] = true;
            for v in self.edges[e].vertices {
                self.select_vertex(flags, hidden, v);
            }
            true
        } else {
            false
        }
    }
    pub fn select_face(&self, flags: &mut Flags, hidden: &Flags, f: usize) -> bool {
        if !hidden.f[f] {
            flags.f[f] = true;
            for &e in &self.faces[f].edges {
                self.select_edge(flags, hidden, e);
            }
            true
        } else {
            false
        }
    }
    pub fn expand_down(&self, flags: &mut Flags, hidden: &Flags) {
        for f in 0..self.faces.len() {
            if flags.f[f] {
                self.select_face(flags, hidden, f);
            }
        }
        for e in 0..self.edges.len() {
            if flags.e[e] {
                self.select_edge(flags, hidden, e);
            }
        }
    }
    pub fn flush_up(&self, flags: &mut Flags, hidden: &Flags, mode: &BTreeSet<Domain>) {
        if mode.contains(&Domain::Vertex) {
            for (i, e) in self.edges.iter().enumerate() {
                flags.e[i] = !hidden.e[i] && e.vertices.iter().all(|v| flags.v[*v]);
            }
        }
        if mode.contains(&Domain::Vertex) || mode.contains(&Domain::Edge) {
            for (i, f) in self.faces.iter().enumerate() {
                flags.f[i] = !hidden.f[i] && f.edges.iter().all(|e| flags.e[*e]);
            }
        }
    }
    pub fn manifold_vertex(&self, v: usize) -> bool {
        let edges = &self.vertex_edges[v];
        let faces = &self.vertex_faces[v];
        if edges.is_empty()
            || faces.is_empty()
            || edges
                .iter()
                .any(|e| self.edges[*e].faces.is_empty() || self.edges[*e].faces.len() > 2)
        {
            return false;
        }
        let boundary = edges
            .iter()
            .filter(|e| self.edges[**e].faces.len() == 1)
            .count();
        if boundary != 0 && boundary != 2 {
            return false;
        }
        let mut found = BTreeSet::from([faces[0]]);
        let mut pending = vec![faces[0]];
        while let Some(f) = pending.pop() {
            for &e in &self.faces[f].edges {
                if !self.edges[e].vertices.contains(&v) {
                    continue;
                }
                for &(other, _) in &self.edges[e].faces {
                    if found.insert(other) {
                        pending.push(other);
                    }
                }
            }
        }
        found.len() == faces.len()
    }
}

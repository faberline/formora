// SPDX-FileCopyrightText: 2004 Blender Authors
// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
// Selection behavior is derived from the pinned Blender BMesh/edit-mesh rules.
use super::topology::Flags;
use super::{Component, Domain, Editing, Graph, ModeAction, Outcome, Selector};
use crate::mesh::MeshAsset;
use crate::scene::{Result, SceneError};

impl Graph {
    pub fn apply(
        &self,
        asset: &MeshAsset,
        state: &mut Editing,
        selector: &Selector,
    ) -> Result<Outcome> {
        let mut flags = self.flags(&state.selected);
        let hidden = self.flags(&state.hidden);
        if let Selector::Mode {
            domain,
            action,
            extend,
            expand,
        } = selector
        {
            return self.switch_mode(
                state,
                &mut flags,
                &hidden,
                (*domain, *action, *extend, *expand),
            );
        }
        let extend = match selector {
            Selector::NonManifold { extend, .. }
            | Selector::Loose { extend }
            | Selector::FacesBySides { extend, .. }
            | Selector::Poles { extend, .. }
            | Selector::Ungrouped { extend } => *extend,
            _ => true,
        };
        match selector {
            Selector::FacesBySides { count, .. } if !(3..=2147483647).contains(count) => {
                return Err(SceneError(
                    "face side count must be within 3..2147483647".into(),
                ));
            }
            Selector::Poles { count, .. } if *count > 2147483647 => {
                return Err(SceneError("pole count must be within 0..2147483647".into()));
            }
            Selector::Ungrouped { .. } => {
                if !state.mode.contains(&Domain::Vertex) {
                    return Err(SceneError(
                        "invalid_selection_domain: ungrouped selection requires vertex mode".into(),
                    ));
                }
                if asset.vertex_groups.is_empty() || asset.vertex_weights.is_none() {
                    return Err(SceneError("missing_vertex_weights: ungrouped selection requires groups and a weight layer".into()));
                }
            }
            _ => {}
        }
        let mut changed = !extend
            && (!matches!(selector, Selector::Ungrouped { .. }) || flags.v.iter().any(|on| *on));
        if changed {
            flags.v.fill(false);
            flags.e.fill(false);
            flags.f.fill(false);
            state.history.clear();
        }
        match selector {
            Selector::NonManifold {
                wire,
                boundary,
                multiple_faces,
                non_contiguous,
                vertices,
                ..
            } => {
                if *vertices {
                    for v in 0..self.vertex_ids.len() {
                        if !self.manifold_vertex(v) {
                            changed |= self.select_vertex(&mut flags, &hidden, v);
                        }
                    }
                }
                for (i, edge) in self.edges.iter().enumerate() {
                    let count = edge.faces.len();
                    if (*wire && count == 0)
                        || (*boundary && count == 1)
                        || (*multiple_faces && count > 2)
                        || (*non_contiguous && count == 2 && edge.faces[0].1 == edge.faces[1].1)
                    {
                        changed |= self.select_edge(&mut flags, &hidden, i);
                    }
                }
            }
            Selector::Loose { .. } => {
                if state.mode.contains(&Domain::Vertex) {
                    for (i, edges) in self.vertex_edges.iter().enumerate() {
                        if edges.is_empty() {
                            changed |= self.select_vertex(&mut flags, &hidden, i);
                        }
                    }
                }
                if state.mode.contains(&Domain::Edge) {
                    for (i, edge) in self.edges.iter().enumerate() {
                        if edge.faces.is_empty() {
                            changed |= self.select_edge(&mut flags, &hidden, i);
                        }
                    }
                }
                if state.mode.contains(&Domain::Face) {
                    for (i, face) in self.faces.iter().enumerate() {
                        if face.edges.iter().all(|e| self.edges[*e].faces.len() == 1) {
                            changed |= self.select_face(&mut flags, &hidden, i);
                        }
                    }
                }
            }
            Selector::FacesBySides {
                count, comparison, ..
            } => {
                for (i, face) in self.faces.iter().enumerate() {
                    if comparison.matches(face.vertices.len(), *count) {
                        changed |= self.select_face(&mut flags, &hidden, i);
                    }
                }
            }
            Selector::Poles {
                count,
                comparison,
                exclude_nonmanifold,
                ..
            } => {
                for (v, edges) in self.vertex_edges.iter().enumerate() {
                    if hidden.v[v]
                        || !comparison.matches(edges.len(), *count)
                        || (*exclude_nonmanifold
                            && (!self.manifold_vertex(v)
                                || edges.iter().any(|e| self.edges[*e].faces.len() != 2)))
                    {
                        continue;
                    }
                    changed = true;
                    if state.mode.contains(&Domain::Vertex) {
                        self.select_vertex(&mut flags, &hidden, v);
                    } else if state.mode.contains(&Domain::Edge) {
                        for &e in edges {
                            self.select_edge(&mut flags, &hidden, e);
                        }
                    } else {
                        for &f in &self.vertex_faces[v] {
                            self.select_face(&mut flags, &hidden, f);
                        }
                    }
                }
            }
            Selector::Ungrouped { .. } => {
                let weights = &asset.vertex_weights.as_ref().expect("checked weights").0;
                for (v, id) in self.vertex_ids.iter().enumerate() {
                    if weights.get(id).is_none_or(|row| row.0.is_empty()) {
                        changed |= self.select_vertex(&mut flags, &hidden, v);
                    }
                }
            }
            Selector::InteriorFaces {} => {
                for face in self.interior_faces()? {
                    self.select_face(&mut flags, &hidden, face);
                }
            }
            Selector::Mode { .. } => unreachable!("mode handled above"),
        }
        // Interior selection deliberately preserves its independent face flags.
        if changed && !matches!(selector, Selector::InteriorFaces {}) {
            self.flush_up(&mut flags, &hidden, &state.mode);
        }
        state
            .history
            .retain(|item| self.component_selected(item, &flags));
        state.selected = self.elements(&flags);
        Ok(Outcome::Completed)
    }

    fn switch_mode(
        &self,
        state: &mut Editing,
        flags: &mut Flags,
        hidden: &Flags,
        options: (Domain, ModeAction, bool, bool),
    ) -> Result<Outcome> {
        let (domain, action, extend, expand) = options;
        let old = state.mode.clone();
        let mut next = old.clone();
        let unchanged = match action {
            ModeAction::Enable => !next.insert(domain),
            ModeAction::Disable => {
                if !next.contains(&domain) || next.len() == 1 {
                    true
                } else {
                    next.remove(&domain);
                    false
                }
            }
            ModeAction::Toggle => {
                if next.len() == 1 && next.contains(&domain) {
                    true
                } else {
                    if !next.insert(domain) {
                        next.remove(&domain);
                    }
                    false
                }
            }
        };
        if unchanged {
            return Ok(Outcome::Unchanged);
        }
        if !extend {
            if expand {
                self.convert(flags, hidden, *old.last().expect("nonempty mode"), domain);
            }
            next = std::collections::BTreeSet::from([domain]);
        }
        state.mode = next;
        state.history.retain(|entry| {
            state.mode.contains(&match entry {
                Component::Vertex { .. } => Domain::Vertex,
                Component::Edge { .. } => Domain::Edge,
                Component::Face { .. } => Domain::Face,
            })
        });
        if state.mode.contains(&Domain::Vertex) {
            // The editor conversion selects upward; it does not clear older flags.
            for (i, e) in self.edges.iter().enumerate() {
                if !hidden.e[i] && e.vertices.iter().all(|v| flags.v[*v]) {
                    flags.e[i] = true;
                }
            }
            for (i, f) in self.faces.iter().enumerate() {
                if !hidden.f[i] && f.vertices.iter().all(|v| flags.v[*v]) {
                    flags.f[i] = true;
                }
            }
        } else if state.mode.contains(&Domain::Edge) {
            flags.v.fill(false);
            for e in 0..self.edges.len() {
                if flags.e[e] {
                    self.select_edge(flags, hidden, e);
                }
            }
            if flags.e.iter().any(|on| *on) {
                self.flush_up(flags, hidden, &state.mode);
            }
        } else {
            // Rebuild lower-domain flags from the surviving face flags.
            flags.e.fill(false);
            for (v, edges) in self.vertex_edges.iter().enumerate() {
                if !edges.is_empty() {
                    flags.v[v] = false;
                }
            }
            for f in 0..self.faces.len() {
                if flags.f[f] {
                    self.select_face(flags, hidden, f);
                }
            }
        }
        state
            .history
            .retain(|entry| self.component_selected(entry, flags));
        state.selected = self.elements(flags);
        Ok(Outcome::Completed)
    }

    fn convert(&self, flags: &mut Flags, hidden: &Flags, from: Domain, to: Domain) {
        let original = flags.clone();
        match (from, to) {
            (Domain::Vertex, Domain::Edge) => {
                for (i, e) in self.edges.iter().enumerate() {
                    if e.vertices.iter().any(|v| original.v[*v]) {
                        self.select_edge(flags, hidden, i);
                    }
                }
            }
            (Domain::Vertex, Domain::Face) => {
                for (i, f) in self.faces.iter().enumerate() {
                    if f.vertices.iter().any(|v| original.v[*v]) {
                        self.select_face(flags, hidden, i);
                    }
                }
            }
            (Domain::Edge, Domain::Face) => {
                for (i, f) in self.faces.iter().enumerate() {
                    if f.edges.iter().any(|e| original.e[*e]) {
                        self.select_face(flags, hidden, i);
                    }
                }
            }
            (Domain::Edge, Domain::Vertex) => {
                if original.e.iter().any(|v| *v) {
                    for (v, edges) in self.vertex_edges.iter().enumerate() {
                        if !edges
                            .iter()
                            .filter(|e| !hidden.e[**e])
                            .all(|e| original.e[*e])
                        {
                            flags.v[v] = false;
                        }
                    }
                    self.deselect_up(flags, hidden);
                }
            }
            (Domain::Face, Domain::Vertex) => {
                if original.f.iter().any(|v| *v) {
                    for (v, faces) in self.vertex_faces.iter().enumerate() {
                        if !faces
                            .iter()
                            .filter(|f| !hidden.f[**f])
                            .all(|f| original.f[*f])
                        {
                            flags.v[v] = false;
                        }
                    }
                    self.deselect_up(flags, hidden);
                }
            }
            (Domain::Face, Domain::Edge) if original.f.iter().any(|v| *v) => {
                for (e, edge) in self.edges.iter().enumerate() {
                    if !edge
                        .faces
                        .iter()
                        .filter(|(f, _)| !hidden.f[*f])
                        .all(|(f, _)| original.f[*f])
                    {
                        flags.e[e] = false;
                    }
                }
                // Deselecting an edge in face mode only clears vertices with no selected edges.
                for (v, edges) in self.vertex_edges.iter().enumerate() {
                    if !edges.iter().any(|e| flags.e[*e]) {
                        flags.v[v] = false;
                    }
                }
                self.deselect_up(flags, hidden);
            }
            _ => {}
        }
    }

    fn deselect_up(&self, flags: &mut Flags, hidden: &Flags) {
        for (i, e) in self.edges.iter().enumerate() {
            if !hidden.e[i] && !e.vertices.iter().all(|v| flags.v[*v]) {
                flags.e[i] = false;
            }
        }
        for (i, f) in self.faces.iter().enumerate() {
            if f.edges.iter().any(|e| !flags.e[*e]) {
                flags.f[i] = false;
            }
        }
    }
}

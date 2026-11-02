//! Value-checked CPU preparation. Revision and allocation identity are not cache keys.
use super::{
    SurfaceTriangle, Vertex, append_selection, append_triangle, triangles,
    world_transforms_validated,
};
use crate::mesh::MeshAsset;
use crate::scene::{Annotation, EntityKind, Geometry, Material, Result, Scene, SceneError};
use glam::{DMat4, DVec3};
use std::collections::{BTreeMap, BTreeSet};
#[cfg(feature = "preview")]
use std::ops::Range;
use std::sync::Arc;

#[cfg(feature = "preview")]
pub(crate) struct DrawRanges {
    pub meshes: BTreeMap<String, Range<u32>>,
    pub annotations: Range<u32>,
}

type GeometryPreparation = (BTreeMap<String, DMat4>, Arc<Vec<Vertex>>);

struct Triangle {
    points: [DVec3; 3],
    normals: Option<[[f64; 3]; 3]>,
    colors: Option<[[f64; 4]; 3]>,
    material: Option<String>,
    selected: bool,
}

impl Triangle {
    fn borrowed(&self) -> SurfaceTriangle<'_> {
        SurfaceTriangle {
            points: self.points,
            normals: self.normals,
            colors: self.colors,
            material: self.material.as_deref(),
            selected: self.selected,
        }
    }
}

struct Asset {
    source: MeshAsset,
    triangles: Vec<Triangle>,
}

struct Entity {
    world: [u64; 16],
    geometry: Geometry,
    material: Option<String>,
    asset: Option<Arc<Asset>>,
    materials: Arc<()>,
    vertices: Arc<Vec<Vertex>>,
}

/// Reuses resolved asset triangles and world-space vertex chunks by exact input values.
/// Every call validates the full scene. The returned snapshot is immutable and owned.
/// Camera-facing edit markers rebuild conservatively. This does not cache game state.
#[derive(Default)]
pub struct GeometryCache {
    assets: BTreeMap<String, Arc<Asset>>,
    entities: BTreeMap<String, Entity>,
    materials: BTreeMap<String, Material>,
    material_token: Arc<()>,
    annotations: Vec<Annotation>,
    annotation_vertices: Arc<Vec<Vertex>>,
    chunks: Vec<Arc<Vec<Vertex>>>,
    combined: Arc<Vec<Vertex>>,
}

fn material_bits(m: &Material) -> [u64; 6] {
    [
        m.base_color[0].to_bits(),
        m.base_color[1].to_bits(),
        m.base_color[2].to_bits(),
        m.base_color[3].to_bits(),
        m.roughness.to_bits(),
        m.metallic.to_bits(),
    ]
}

// Derived PartialEq distinguishes structure and all nonzero values. Add exact bits
// for every explicit mesh float, including UVs and signed zero. Recipe and weight
// data never reuse validation; their existing validation runs on every call.
fn mesh_bits(asset: &MeshAsset) -> impl Iterator<Item = u64> + '_ {
    asset
        .vertices
        .values()
        .flatten()
        .chain(
            asset
                .triangles
                .values()
                .flat_map(|t| t.uv_layers.values().flatten().flatten()),
        )
        .chain(
            asset
                .polygons
                .values()
                .flat_map(|p| p.uv_layers.values().flatten().flatten()),
        )
        .chain(
            asset
                .triangles
                .values()
                .flat_map(|t| t.corner_normals.iter().flatten().flatten()),
        )
        .chain(
            asset
                .triangles
                .values()
                .flat_map(|t| t.corner_colors.iter().flatten().flatten()),
        )
        .chain(
            asset
                .polygons
                .values()
                .flat_map(|p| p.corner_colors.iter().flatten().flatten()),
        )
        .chain(asset.polygons.values().flat_map(|p| {
            p.corner_normals
                .iter()
                .flatten()
                .flatten()
                .chain(p.normal.iter().flatten())
        }))
        .map(|n| n.to_bits())
}

impl GeometryCache {
    // Only called after successful preparation under the renderer's cache lock.
    #[cfg(feature = "preview")]
    pub(crate) fn draw_ranges(&self) -> Result<DrawRanges> {
        let mut end = 0_u32;
        let mut meshes = BTreeMap::new();
        for (id, entity) in &self.entities {
            let start = end;
            end = end
                .checked_add(
                    u32::try_from(entity.vertices.len())
                        .map_err(|_| SceneError("too many preview vertices".into()))?,
                )
                .ok_or_else(|| SceneError("too many preview vertices".into()))?;
            meshes.insert(id.clone(), start..end);
        }
        let total = u32::try_from(self.combined.len())
            .map_err(|_| SceneError("too many preview vertices".into()))?;
        Ok(DrawRanges {
            meshes,
            annotations: end..total,
        })
    }
    /// Prepares current CPU preview vertices, even if `Scene.revision` is unchanged.
    /// No GPU, files, session, source mutation or timing assumptions are involved.
    pub fn vertices(&mut self, scene: &Scene) -> Result<Arc<Vec<Vertex>>> {
        self.prepare(scene).map(|(_, vertices)| vertices)
    }

    // No unchecked public path. Validation, transform evaluation and preparation all
    // read this immutable Scene before returning. Reuse is based on actual values.
    pub(crate) fn prepare(&mut self, scene: &Scene) -> Result<GeometryPreparation> {
        let used: BTreeSet<_> = scene
            .entities
            .values()
            .filter_map(|e| match &e.content {
                EntityKind::Mesh {
                    geometry: Geometry::Asset { id },
                    ..
                } => Some(id.as_str()),
                _ => None,
            })
            .collect();
        let mut validated = BTreeMap::new();
        scene.validate_with_mesh_assets(|id, source| {
            let reusable = self.assets.get(id).filter(|old| {
                used.contains(id)
                    && source.recipe.is_none()
                    && source.vertex_weights.is_none()
                    && old.source == *source
                    && mesh_bits(&old.source).eq(mesh_bits(source))
            });
            if let Some(asset) = reusable {
                validated.insert(id.to_owned(), Arc::clone(asset));
                Ok(())
            } else {
                source.validate()
            }
        })?;
        let world = world_transforms_validated(scene)?;
        let vertices = self.with_world(scene, &world, &validated)?;
        Ok((world, vertices))
    }

    fn with_world(
        &mut self,
        scene: &Scene,
        world: &BTreeMap<String, DMat4>,
        validated: &BTreeMap<String, Arc<Asset>>,
    ) -> Result<Arc<Vec<Vertex>>> {
        let same_materials = self.materials.len() == scene.materials.len()
            && self
                .materials
                .iter()
                .zip(&scene.materials)
                .all(|((id, a), (other, b))| id == other && material_bits(a) == material_bits(b));
        if !same_materials {
            self.materials = scene.materials.clone();
            self.material_token = Arc::new(());
        }
        self.entities.retain(|id, _| {
            scene
                .entities
                .get(id)
                .is_some_and(|e| matches!(e.content, EntityKind::Mesh { .. }))
        });
        let mut frame_assets = BTreeMap::<String, Arc<Asset>>::new();
        let mut chunks = Vec::new();
        for (id, entity) in &scene.entities {
            let EntityKind::Mesh { geometry, material } = &entity.content else {
                continue;
            };
            let asset = if let Geometry::Asset { id: asset_id } = geometry {
                if let Some(asset) = frame_assets.get(asset_id) {
                    Some(Arc::clone(asset))
                } else {
                    let source = scene
                        .mesh_assets
                        .get(asset_id)
                        .ok_or_else(|| SceneError(format!("missing mesh asset: {asset_id}")))?;
                    let reusable = validated.get(asset_id).or_else(|| {
                        self.assets.get(asset_id).filter(|old| {
                            old.source == *source && mesh_bits(&old.source).eq(mesh_bits(source))
                        })
                    });
                    let asset = if let Some(old) = reusable {
                        Arc::clone(old)
                    } else {
                        let resolved = triangles(scene, geometry, true)?
                            .into_iter()
                            .map(|t| Triangle {
                                points: t.points,
                                normals: t.normals,
                                colors: t.colors,
                                material: t.material.map(str::to_owned),
                                selected: t.selected,
                            })
                            .collect();
                        Arc::new(Asset {
                            source: source.clone(),
                            triangles: resolved,
                        })
                    };
                    frame_assets.insert(asset_id.clone(), Arc::clone(&asset));
                    Some(asset)
                }
            } else {
                None
            };
            let matrix = *world
                .get(id)
                .ok_or_else(|| SceneError(format!("missing world transform: {id}")))?;
            let bits = matrix.to_cols_array().map(f64::to_bits);
            let editing = asset
                .as_ref()
                .and_then(|a| a.source.editing.as_ref())
                .is_some_and(|e| {
                    e.preview
                        && (e.mode.contains(&crate::mesh::selection::Domain::Vertex)
                            || e.mode.contains(&crate::mesh::selection::Domain::Edge))
                });
            let reusable = self.entities.get(id).filter(|old| {
                !editing
                    && old.world == bits
                    && old.geometry == *geometry
                    && old.material == *material
                    && Arc::ptr_eq(&old.materials, &self.material_token)
                    && match (&old.asset, &asset) {
                        (Some(a), Some(b)) => Arc::ptr_eq(a, b),
                        (None, None) => true,
                        _ => false,
                    }
            });
            let vertices = if let Some(old) = reusable {
                Arc::clone(&old.vertices)
            } else {
                let mut vertices = Vec::new();
                let mut append = |t: SurfaceTriangle<'_>| -> Result<()> {
                    let binding = material.as_deref().or(t.material);
                    let (color, surface) = match binding.and_then(|id| scene.materials.get(id)) {
                        Some(m) => (
                            m.base_color.map(|v| v as f32),
                            [m.roughness as f32, m.metallic as f32],
                        ),
                        None => ([0.65, 0.68, 0.72, 1.0], [0.6, 0.0]),
                    };
                    let color = if t.selected {
                        [1.0, 0.55, 0.03, 1.0]
                    } else {
                        color
                    };
                    append_triangle(&mut vertices, t, matrix, color, surface)
                };
                if let Some(asset) = &asset {
                    for t in &asset.triangles {
                        append(t.borrowed())?;
                    }
                } else {
                    for t in triangles(scene, geometry, true)? {
                        append(t)?;
                    }
                }
                if let Some(asset) = &asset {
                    append_selection(&mut vertices, scene, &asset.source, matrix)?;
                }
                let vertices = Arc::new(vertices);
                self.entities.insert(
                    id.clone(),
                    Entity {
                        world: bits,
                        geometry: geometry.clone(),
                        material: material.clone(),
                        asset: asset.clone(),
                        materials: Arc::clone(&self.material_token),
                        vertices: Arc::clone(&vertices),
                    },
                );
                vertices
            };
            chunks.push(vertices);
        }
        let same_notes = self.annotations == scene.annotations
            && self
                .annotations
                .iter()
                .zip(&scene.annotations)
                .all(|(a, b)| a.position.map(f64::to_bits) == b.position.map(f64::to_bits));
        if !same_notes {
            let mut vertices = Vec::new();
            for note in &scene.annotations {
                for t in triangles(scene, &Geometry::Cube { size: [0.06; 3] }, false)? {
                    append_triangle(
                        &mut vertices,
                        t,
                        DMat4::from_translation(DVec3::from_array(note.position)),
                        [1.0, 0.05, 0.05, 1.0],
                        [1.0, 0.0],
                    )?;
                }
            }
            self.annotations = scene.annotations.clone();
            self.annotation_vertices = Arc::new(vertices);
        }
        if !self.annotation_vertices.is_empty() {
            chunks.push(Arc::clone(&self.annotation_vertices));
        }
        self.assets = frame_assets;
        if self.chunks.len() != chunks.len()
            || !self
                .chunks
                .iter()
                .zip(&chunks)
                .all(|(a, b)| Arc::ptr_eq(a, b))
        {
            let mut combined = Vec::with_capacity(chunks.iter().map(|c| c.len()).sum());
            for chunk in &chunks {
                combined.extend_from_slice(chunk);
            }
            self.combined = Arc::new(combined);
            self.chunks = chunks;
        }
        Ok(Arc::clone(&self.combined))
    }
}

#[cfg(feature = "preview")]
pub(crate) fn ordered_ranges(layers: &[&DrawRanges]) -> Result<Vec<(usize, Range<u32>)>> {
    let mut meshes = BTreeMap::new();
    for (index, layer) in layers.iter().enumerate() {
        for (id, range) in &layer.meshes {
            if meshes.insert(id, (index, range.clone())).is_some() {
                return Err(SceneError(format!("duplicate prepared mesh entity: {id}")));
            }
        }
    }
    let mut result: Vec<(usize, Range<u32>)> = Vec::new();
    let mut append = |index: usize, range: Range<u32>| {
        if range.is_empty() {
            return;
        }
        if let Some((old, previous)) = result.last_mut() {
            if *old == index && previous.end == range.start {
                previous.end = range.end;
                return;
            }
        }
        result.push((index, range));
    };
    for (index, range) in meshes.into_values() {
        append(index, range);
    }
    for (index, layer) in layers.iter().enumerate() {
        append(index, layer.annotations.clone());
    }
    Ok(result)
}

#[cfg(all(test, feature = "preview"))]
mod tests {
    use super::*;
    fn ranges(items: &[(&str, Range<u32>)], notes: Range<u32>) -> DrawRanges {
        DrawRanges {
            meshes: items
                .iter()
                .map(|(id, r)| (id.to_string(), r.clone()))
                .collect(),
            annotations: notes,
        }
    }
    #[test]
    fn layers_sort_global_ids_before_annotations_and_coalesce_only_adjacent_ranges() {
        let a = ranges(&[("a", 0..3), ("c", 3..6), ("d", 6..9)], 9..12);
        let b = ranges(&[("b", 0..6), ("z", 6..9)], 9..15);
        assert_eq!(
            ordered_ranges(&[&b, &a]).unwrap(),
            vec![(1, 0..3), (0, 0..6), (1, 3..9), (0, 6..15), (1, 9..12)]
        );
    }
    #[test]
    fn duplicate_ids_fail_even_when_both_meshes_have_no_vertices() {
        let a = ranges(&[("empty", 0..0)], 0..0);
        assert!(
            ordered_ranges(&[&a, &a])
                .unwrap_err()
                .0
                .contains("duplicate")
        );
        assert!(ordered_ranges(&[]).unwrap().is_empty());
    }
    #[test]
    fn successful_cache_ranges_cover_exact_vertex_chunks_and_annotations() {
        let mut scene = Scene::default();
        for id in ["z", "a"] {
            scene.entities.insert(
                id.into(),
                crate::scene::Entity {
                    name: id.into(),
                    parent: None,
                    transform: Default::default(),
                    content: EntityKind::Mesh {
                        geometry: Geometry::Cube { size: [1.; 3] },
                        material: None,
                    },
                },
            );
        }
        scene.annotations.push(Annotation {
            entity: None,
            position: [0., 0., 0.],
            text: "note".into(),
        });
        let mut cache = GeometryCache::default();
        let data = cache.vertices(&scene).unwrap();
        let r = cache.draw_ranges().unwrap();
        assert_eq!(r.meshes["a"], 0..36);
        assert_eq!(r.meshes["z"], 36..72);
        assert_eq!(r.annotations, 72..data.len() as u32);
        assert!(r.annotations.end > 72);
        scene.entities.remove("a");
        cache.vertices(&scene).unwrap();
        let r = cache.draw_ranges().unwrap();
        assert_eq!(r.meshes.len(), 1);
        assert_eq!(r.meshes["z"], 0..36);
        assert_eq!(r.annotations.start, 36);
    }
}

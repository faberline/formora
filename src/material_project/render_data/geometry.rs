use super::*;
use formora_native_bb025::{
    scene::{EntityKind, Geometry},
    transforms,
};

pub(super) fn prepare(project: &PreparedProject) -> Result<RenderScene<'_>, RenderError> {
    let scene = &project.scene;
    let mut groups: BTreeMap<Option<String>, Batch> = BTreeMap::new();
    for (entity_id, entity) in &scene.entities {
        let EntityKind::Mesh {
            geometry: Geometry::Asset { id: mesh_id },
            material: override_material,
        } = &entity.content
        else {
            continue;
        };
        let mesh = &scene.mesh_assets[mesh_id];
        let world = transforms::world(scene, entity_id)
            .map_err(|e| RenderError::new("invalid_transform", e))?;
        let tessellation = mesh
            .tessellate()
            .map_err(|e| RenderError::new("tessellation_failed", e))?;
        if !tessellation.diagnostics.is_empty() {
            return Err(RenderError::new(
                "tessellation_diagnostic",
                format!("{entity_id}/{mesh_id}: {:?}", tessellation.diagnostics),
            ));
        }
        let mut add = |face: Face,
                       corners: [usize; 3],
                       ids: [String; 3],
                       slot: Option<usize>,
                       uvs: Option<[[f64; 2]; 3]>|
         -> Result<(), RenderError> {
            let material = override_material
                .clone()
                .or_else(|| slot.and_then(|s| mesh.material_slots[s].clone()));
            let binding = material
                .as_ref()
                .and_then(|m| project.project.bindings.get(m));
            let factor = material
                .as_ref()
                .map_or([0.65, 0.68, 0.72, 1.0], |m| scene.materials[m].base_color);
            if factor[3] != 1.0 {
                return Err(RenderError::new(
                    "unsupported_alpha",
                    "The first render profile requires opaque used materials",
                ));
            }
            let batch = groups.entry(material.clone()).or_insert_with(|| Batch {
                material,
                image: binding.map(|b| b.image.clone()),
                factor: factor.map(|v| v as f32),
                vertices: Vec::new(),
                sources: Vec::new(),
            });
            for (i, id) in ids.iter().enumerate() {
                let p = transforms::point(world, mesh.vertices[id], entity.transform.precision)
                    .map_err(|e| RenderError::new("invalid_transform", e))?
                    .map(|v| v as f32);
                let uv = uvs.map_or([0.0; 2], |u| u[i]).map(|v| v as f32);
                if !p.iter().chain(uv.iter()).all(|v| v.is_finite()) {
                    return Err(RenderError::new(
                        "gpu_range",
                        "Derived position/UV exceeds f32 range",
                    ));
                }
                batch.vertices.push(Vertex { position: p, uv });
            }
            batch.sources.push(TriangleSource {
                entity: entity_id.clone(),
                mesh: mesh_id.clone(),
                face,
                corners,
                vertex_ids: ids,
                source_uvs: uvs,
            });
            Ok(())
        };
        let layer_for = |slot: Option<usize>| {
            override_material
                .as_deref()
                .or_else(|| slot.and_then(|s| mesh.material_slots[s].as_deref()))
                .and_then(|m| project.project.bindings.get(m))
                .map(|b| b.uv_layer.as_str())
        };
        for (id, f) in &mesh.triangles {
            let uvs = layer_for(f.material_slot).map(|l| f.uv_layers[l]);
            add(
                Face::Triangle { id: id.clone() },
                [0, 1, 2],
                f.vertices.clone(),
                f.material_slot,
                uvs,
            )?;
        }
        for tri in tessellation.triangles {
            let f = &mesh.polygons[&tri.polygon];
            let uvs = layer_for(f.material_slot).map(|l| tri.corners.map(|c| f.uv_layers[l][c]));
            add(
                Face::Polygon { id: tri.polygon },
                tri.corners,
                tri.corners.map(|c| f.vertices[c].clone()),
                f.material_slot,
                uvs,
            )?;
        }
    }
    let batches: Vec<_> = groups.into_values().collect();
    if batches.iter().all(|b| b.vertices.is_empty()) {
        return Err(RenderError::new(
            "empty_geometry",
            "No renderable source triangles",
        ));
    }
    Ok(RenderScene { project, batches })
}

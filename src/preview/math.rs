use crate::mesh::selection::{Domain, FaceRef};
use crate::scene::{EntityKind, Geometry, Result, Scene, SceneError};
use glam::{DMat4, DQuat, DVec3, DVec4};
use std::collections::{BTreeMap, BTreeSet};

#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
pub struct Vertex {
    pub position: [f32; 3],
    pub normal: [f32; 3],
    pub color: [f32; 4],
    pub surface: [f32; 2],
}

pub struct Camera {
    pub view_projection: DMat4,
    pub position: DVec3,
}

#[derive(Debug)]
pub struct Hit {
    pub entity: String,
    pub position: DVec3,
    pub distance: f64,
}

pub fn world_transforms(scene: &Scene) -> Result<BTreeMap<String, DMat4>> {
    scene.validate()?;
    let mut result = BTreeMap::new();
    for id in scene.entities.keys() {
        let mut chain = Vec::new();
        let mut current = Some(id.as_str());
        while let Some(key) = current {
            if let Some(matrix) = result.get(key) {
                chain.push(*matrix);
                break;
            }
            let entity = &scene.entities[key];
            let t = &entity.transform;
            chain.push(DMat4::from_scale_rotation_translation(
                DVec3::from_array(t.scale),
                DQuat::from_array(t.rotation).normalize(),
                DVec3::from_array(t.translation),
            ));
            current = entity.parent.as_deref();
        }
        let matrix = chain
            .into_iter()
            .rev()
            .fold(DMat4::IDENTITY, |parent, local| parent * local);
        if !matrix.is_finite() {
            return Err(SceneError(format!("transform exceeds preview range: {id}")));
        }
        result.insert(id.clone(), matrix);
    }
    Ok(result)
}

pub fn camera(scene: &Scene, width: u32, height: u32) -> Result<Camera> {
    if width == 0 || height == 0 {
        return Err(SceneError("preview size must be nonzero".into()));
    }
    let world = world_transforms(scene)?;
    let (view, fov, near, far, position) = if let Some(id) = &scene.active_camera {
        let EntityKind::Camera {
            vertical_fov_degrees,
            near,
            far,
        } = scene.entities[id].content
        else {
            unreachable!("validated camera")
        };
        let matrix = world[id];
        (
            matrix.inverse(),
            vertical_fov_degrees.to_radians(),
            near,
            far,
            matrix.transform_point3(DVec3::ZERO),
        )
    } else {
        let position = DVec3::new(8.0, -10.0, 7.0);
        (
            glam::dcamera::rh::view::look_at_mat4(position, DVec3::new(0.0, 0.0, 1.0), DVec3::Z),
            60_f64.to_radians(),
            0.1,
            1000.0,
            position,
        )
    };
    let view_projection =
        glam::dcamera::rh::proj::directx::perspective(fov, width as f64 / height as f64, near, far)
            * view;
    if !view_projection.is_finite() || !view_projection.as_mat4().is_finite() {
        return Err(SceneError("camera exceeds preview range".into()));
    }
    Ok(Camera {
        view_projection,
        position,
    })
}

fn quads(geometry: &Geometry) -> Vec<[DVec3; 4]> {
    match geometry {
        Geometry::Asset { .. } => Vec::new(),
        Geometry::Plane { size } => {
            let (x, y) = (size[0] / 2.0, size[1] / 2.0);
            vec![[
                DVec3::new(-x, -y, 0.0),
                DVec3::new(x, -y, 0.0),
                DVec3::new(x, y, 0.0),
                DVec3::new(-x, y, 0.0),
            ]]
        }
        Geometry::Cube { size } => {
            let (x, y, z) = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0);
            vec![
                [
                    DVec3::new(-x, -y, z),
                    DVec3::new(x, -y, z),
                    DVec3::new(x, y, z),
                    DVec3::new(-x, y, z),
                ],
                [
                    DVec3::new(-x, y, -z),
                    DVec3::new(x, y, -z),
                    DVec3::new(x, -y, -z),
                    DVec3::new(-x, -y, -z),
                ],
                [
                    DVec3::new(x, -y, -z),
                    DVec3::new(x, y, -z),
                    DVec3::new(x, y, z),
                    DVec3::new(x, -y, z),
                ],
                [
                    DVec3::new(-x, y, -z),
                    DVec3::new(-x, -y, -z),
                    DVec3::new(-x, -y, z),
                    DVec3::new(-x, y, z),
                ],
                [
                    DVec3::new(x, y, -z),
                    DVec3::new(-x, y, -z),
                    DVec3::new(-x, y, z),
                    DVec3::new(x, y, z),
                ],
                [
                    DVec3::new(-x, -y, -z),
                    DVec3::new(x, -y, -z),
                    DVec3::new(x, -y, z),
                    DVec3::new(-x, -y, z),
                ],
            ]
        }
    }
}

struct SurfaceTriangle<'a> {
    points: [DVec3; 3],
    normals: Option<[[f64; 3]; 3]>,
    material: Option<&'a str>,
    selected: bool,
}

fn triangles<'a>(scene: &'a Scene, geometry: &Geometry) -> Result<Vec<SurfaceTriangle<'a>>> {
    if let Geometry::Asset { id } = geometry {
        let asset = &scene.mesh_assets[id];
        let editing = asset.editing.as_ref();
        let mut hidden = BTreeSet::new();
        if let Some(editing) = editing {
            for face in crate::mesh::selection::topology(asset)?.faces {
                if editing.hidden.faces.contains(&face.face)
                    || face
                        .vertices
                        .iter()
                        .any(|id| editing.hidden.vertices.contains(id))
                    || face
                        .edges
                        .iter()
                        .any(|id| editing.hidden.edges.contains(id))
                {
                    hidden.insert(face.face);
                }
            }
        }
        let selected = |face: &FaceRef| {
            editing.is_some_and(|state| {
                state.preview
                    && state.mode.contains(&Domain::Face)
                    && state.selected.faces.contains(face)
            })
        };
        let mut result: Vec<_> = asset
            .triangles
            .iter()
            .filter(|(id, _)| !hidden.contains(&FaceRef::Triangle((*id).clone())))
            .map(|(id, triangle)| SurfaceTriangle {
                points: triangle
                    .vertices
                    .each_ref()
                    .map(|id| DVec3::from_array(asset.vertices[id])),
                normals: triangle.corner_normals,
                material: triangle
                    .material_slot
                    .and_then(|slot| asset.material_slots[slot].as_deref()),
                selected: selected(&FaceRef::Triangle(id.clone())),
            })
            .collect();
        let hidden_polygons = hidden
            .iter()
            .filter_map(|face| match face {
                FaceRef::Polygon(id) => Some(id.clone()),
                _ => None,
            })
            .collect();
        for t in asset.tessellate_without(&hidden_polygons)?.triangles {
            let polygon = &asset.polygons[&t.polygon];
            result.push(SurfaceTriangle {
                points: t
                    .corners
                    .map(|c| DVec3::from_array(asset.vertices[&polygon.vertices[c]])),
                normals: polygon
                    .corner_normals
                    .as_ref()
                    .map(|ns| t.corners.map(|c| ns[c]))
                    .or(polygon.normal.map(|n| [n; 3])),
                material: polygon
                    .material_slot
                    .and_then(|slot| asset.material_slots[slot].as_deref()),
                selected: selected(&FaceRef::Polygon(t.polygon)),
            });
        }
        return Ok(result);
    }
    Ok(quads(geometry)
        .into_iter()
        .flat_map(|quad| {
            [[0, 1, 2], [0, 2, 3]].map(|indices| SurfaceTriangle {
                points: indices.map(|i| quad[i]),
                normals: None,
                material: None,
                selected: false,
            })
        })
        .collect())
}

fn append_triangle(
    vertices: &mut Vec<Vertex>,
    triangle: SurfaceTriangle<'_>,
    matrix: DMat4,
    color: [f32; 4],
    surface: [f32; 2],
) -> Result<()> {
    let points = triangle.points.map(|p| matrix.transform_point3(p));
    let cross = (points[1] - points[0]).cross(points[2] - points[0]);
    // Keep degenerate topology in the asset; it contributes no visible area.
    if cross.length_squared() == 0.0 {
        return Ok(());
    }
    let flat = cross.normalize();
    let normal_matrix = matrix.inverse().transpose();
    for (index, point) in points.into_iter().enumerate() {
        let supplied = triangle.normals.map(|normals| {
            normal_matrix
                .transform_vector3(DVec3::from_array(normals[index]))
                .normalize()
        });
        let normal = supplied.filter(|n| n.is_finite()).unwrap_or(flat).as_vec3();
        let p = point.as_vec3();
        if !p.is_finite() || !normal.is_finite() {
            return Err(SceneError("geometry exceeds preview range".into()));
        }
        vertices.push(Vertex {
            position: p.to_array(),
            normal: normal.to_array(),
            color,
            surface,
        });
    }
    Ok(())
}

pub fn vertices(scene: &Scene) -> Result<Vec<Vertex>> {
    let world = world_transforms(scene)?;
    let mut result = Vec::new();
    for (id, entity) in &scene.entities {
        if let EntityKind::Mesh { geometry, material } = &entity.content {
            for triangle in triangles(scene, geometry)? {
                // An entity material is an explicit override of all asset slots.
                let binding = material.as_deref().or(triangle.material);
                let (color, surface) = match binding.and_then(|id| scene.materials.get(id)) {
                    Some(m) => (
                        m.base_color.map(|v| v as f32),
                        [m.roughness as f32, m.metallic as f32],
                    ),
                    None => ([0.65, 0.68, 0.72, 1.0], [0.6, 0.0]),
                };
                let color = if triangle.selected {
                    [1.0, 0.55, 0.03, 1.0]
                } else {
                    color
                };
                append_triangle(&mut result, triangle, world[id], color, surface)?;
            }
            if let Geometry::Asset { id: asset_id } = geometry {
                append_selection(&mut result, scene, &scene.mesh_assets[asset_id], world[id])?;
            }
        }
    }
    for note in &scene.annotations {
        for triangle in triangles(scene, &Geometry::Cube { size: [0.06; 3] })? {
            append_triangle(
                &mut result,
                triangle,
                DMat4::from_translation(DVec3::from_array(note.position)),
                [1.0, 0.05, 0.05, 1.0],
                [1.0, 0.0],
            )?;
        }
    }
    Ok(result)
}

// These camera-facing markers are render data only. Surface picking uses triangles().
fn append_selection(
    output: &mut Vec<Vertex>,
    scene: &Scene,
    asset: &crate::mesh::MeshAsset,
    matrix: DMat4,
) -> Result<()> {
    let Some(editing) = &asset.editing else {
        return Ok(());
    };
    if !editing.preview {
        return Ok(());
    }
    if !editing.mode.contains(&Domain::Vertex) && !editing.mode.contains(&Domain::Edge) {
        return Ok(());
    }
    let camera = camera(scene, 1, 1)?;
    let inverse = camera.view_projection.inverse();
    let right = inverse.transform_vector3(DVec3::X).normalize();
    let up = inverse.transform_vector3(DVec3::Y).normalize();
    let marker = |output: &mut Vec<Vertex>, center: DVec3, a: DVec3, b: DVec3| -> Result<()> {
        let toward = (camera.position - center).normalize_or_zero();
        let center = center + toward * (camera.position.distance(center) * 0.0002);
        let corners = [
            center - a - b,
            center + a - b,
            center + a + b,
            center - a + b,
        ];
        for indices in [[0, 1, 2], [0, 2, 3]] {
            append_triangle(
                output,
                SurfaceTriangle {
                    points: indices.map(|i| corners[i]),
                    normals: None,
                    material: None,
                    selected: false,
                },
                DMat4::IDENTITY,
                [1.0, 0.7, 0.02, 1.0],
                [1.0, 0.0],
            )?;
        }
        Ok(())
    };
    if editing.mode.contains(&Domain::Vertex) {
        for id in &editing.selected.vertices {
            if editing.hidden.vertices.contains(id) {
                continue;
            }
            let point = matrix.transform_point3(DVec3::from_array(asset.vertices[id]));
            let size = camera.position.distance(point) * 0.004;
            marker(output, point, right * size, up * size)?;
        }
    }
    if editing.mode.contains(&Domain::Edge) {
        let topology = crate::mesh::selection::topology(asset)?;
        for id in &editing.selected.edges {
            let pair = &topology.edges[id];
            if editing.hidden.edges.contains(id)
                || pair.iter().any(|v| editing.hidden.vertices.contains(v))
            {
                continue;
            }
            let [a, b] = pair
                .each_ref()
                .map(|v| matrix.transform_point3(DVec3::from_array(asset.vertices[v])));
            let center = (a + b) * 0.5;
            let half = (b - a) * 0.5;
            if half.length_squared() == 0. {
                continue;
            }
            let side = half.cross(camera.position - center).normalize_or_zero();
            if side.length_squared() == 0. {
                continue;
            }
            marker(
                output,
                center,
                half,
                side * camera.position.distance(center) * 0.0018,
            )?;
        }
    }
    Ok(())
}

pub fn ray(scene: &Scene, width: u32, height: u32, x: f64, y: f64) -> Result<(DVec3, DVec3)> {
    if !x.is_finite() || !y.is_finite() {
        return Err(SceneError("invalid pointer coordinates".into()));
    }
    let camera = camera(scene, width, height)?;
    let inverse = camera.view_projection.inverse();
    let xy = [2.0 * x / width as f64 - 1.0, 1.0 - 2.0 * y / height as f64];
    let near = inverse * DVec4::new(xy[0], xy[1], 0.0, 1.0);
    let far = inverse * DVec4::new(xy[0], xy[1], 1.0, 1.0);
    let direction = (far.truncate() / far.w - near.truncate() / near.w).normalize();
    if !direction.is_finite() {
        return Err(SceneError("cannot create picking ray".into()));
    }
    Ok((camera.position, direction))
}

pub fn pick(scene: &Scene, origin: DVec3, direction: DVec3) -> Result<Option<Hit>> {
    if !origin.is_finite()
        || !direction.is_finite()
        || (direction.length_squared() - 1.0).abs() > 1e-6
    {
        return Err(SceneError(
            "picking ray must be finite and normalized".into(),
        ));
    }
    let world = world_transforms(scene)?;
    let mut closest: Option<Hit> = None;
    for (id, entity) in &scene.entities {
        let EntityKind::Mesh { geometry, .. } = &entity.content else {
            continue;
        };
        for triangle in triangles(scene, geometry)? {
            let [a, b, c] = triangle.points.map(|p| world[id].transform_point3(p));
            let edge1 = b - a;
            let edge2 = c - a;
            let p = direction.cross(edge2);
            let determinant = edge1.dot(p);
            if determinant.abs() < 1e-12 {
                continue;
            }
            let inverse = 1.0 / determinant;
            let offset = origin - a;
            let u = offset.dot(p) * inverse;
            if !(0.0..=1.0).contains(&u) {
                continue;
            }
            let cross = offset.cross(edge1);
            let v = direction.dot(cross) * inverse;
            if v < 0.0 || u + v > 1.0 {
                continue;
            }
            let distance = edge2.dot(cross) * inverse;
            if distance >= 0.0 && closest.as_ref().is_none_or(|hit| distance < hit.distance) {
                closest = Some(Hit {
                    entity: id.clone(),
                    position: origin + direction * distance,
                    distance,
                });
            }
        }
    }
    Ok(closest)
}

pub fn door_for_entity(scene: &Scene, id: &str) -> Option<String> {
    let mut current = Some(id);
    while let Some(entity) = current {
        if let Some((id, _)) = scene.doors.iter().find(|(_, door)| door.entity == entity) {
            return Some(id.clone());
        }
        current = scene.entities.get(entity)?.parent.as_deref();
    }
    None
}

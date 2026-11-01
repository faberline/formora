//! Bounded, native static USD projection. No upstream exporter is executed.
use crate::mesh::{MeshAsset, selection::FaceRef};
use crate::scene::{EntityKind, Geometry, Result, Scene, SceneError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::fmt::Write as _;
use std::fs::OpenOptions;
use std::io::Write as _;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};

const MAX_BYTES: usize = 256 * 1024 * 1024;
static NEXT: AtomicU64 = AtomicU64::new(0);

#[derive(Debug, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExportRequest {
    pub root: String,
    pub format: String,
    pub output: String,
}
#[derive(Debug, Serialize)]
pub struct ExportReceipt {
    pub format: String,
    pub root: String,
    pub revision: u64,
    pub meshes: usize,
    pub vertices: usize,
    pub faces: usize,
    pub bytes: usize,
    pub core_elapsed_ns: u128,
    pub sha256: String,
    pub output: String,
}
#[derive(Debug)]
pub struct Projection {
    pub text: String,
    pub meshes: usize,
    pub vertices: usize,
    pub faces: usize,
}
fn error(message: impl Into<String>) -> SceneError {
    SceneError(format!("static USD: {}", message.into()))
}
/// Hex encoding is injective even for IDs beginning with a digit or containing '-'.
fn identifier(id: &str) -> String {
    let mut out = String::from("id_");
    for b in id.bytes() {
        write!(out, "{b:02x}").expect("String write");
    }
    out
}
fn quoted(s: &str) -> String {
    // JSON's UTF-8 escaping is also valid for USD quoted strings except control
    // Unicode escapes. Reject control characters instead of emitting a false name.
    serde_json::to_string(s).expect("string serializes")
}
fn text_value(s: &str) -> Result<String> {
    if s.chars().any(char::is_control) {
        return Err(error("control characters are not supported in names"));
    }
    Ok(quoted(s))
}
fn float(v: f64) -> Result<f32> {
    let f = v as f32;
    if !v.is_finite() || !f.is_finite() || (v - f64::from(f)).abs() > 1e-6 {
        return Err(error("value exceeds the 1e-6 float conversion limit"));
    }
    Ok(f)
}
fn vector<const N: usize>(v: [f64; N]) -> Result<String> {
    Ok(format!(
        "({})",
        v.into_iter()
            .map(|v| float(v).map(|v| v.to_string()))
            .collect::<Result<Vec<_>>>()?
            .join(", ")
    ))
}
fn list<T: ToString>(values: impl IntoIterator<Item = T>) -> String {
    format!(
        "[{}]",
        values
            .into_iter()
            .map(|v| v.to_string())
            .collect::<Vec<_>>()
            .join(", ")
    )
}
struct Face<'a> {
    kind: &'static str,
    id: &'a str,
    vertices: Vec<&'a str>,
    uv: BTreeMap<&'a str, Vec<[f64; 2]>>,
    material: Option<usize>,
}
fn faces(asset: &MeshAsset) -> Vec<Face<'_>> {
    asset
        .triangles
        .iter()
        .map(|(id, f)| Face {
            kind: "triangle",
            id,
            vertices: f.vertices.iter().map(String::as_str).collect(),
            uv: f
                .uv_layers
                .iter()
                .map(|(k, v)| (k.as_str(), v.to_vec()))
                .collect(),
            material: f.material_slot,
        })
        .chain(asset.polygons.iter().map(|(id, f)| {
            Face {
                kind: "polygon",
                id,
                vertices: f.vertices.iter().map(String::as_str).collect(),
                uv: f
                    .uv_layers
                    .iter()
                    .map(|(k, v)| (k.as_str(), v.clone()))
                    .collect(),
                material: f.material_slot,
            }
        }))
        .collect()
}
fn supported(asset: &MeshAsset) -> Result<()> {
    if asset.recipe.is_some()
        || asset.editing.is_some()
        || !asset.diagnostics.is_empty()
        || !asset.vertex_groups.is_empty()
        || asset.vertex_weights.is_some()
        || !asset.edge_seams.is_empty()
        || asset.integer_attributes.is_some()
    {
        return Err(error(
            "unsupported recipe, editor, diagnostic or custom mesh state",
        ));
    }
    let faces = faces(asset);
    if asset.vertices.is_empty() || faces.is_empty() {
        return Err(error("empty geometry"));
    }
    let used: HashSet<_> = faces
        .iter()
        .flat_map(|f| f.vertices.iter().copied())
        .collect();
    if used.len() != asset.vertices.len() {
        return Err(error("isolated vertices"));
    }
    let mut used_edges = HashSet::new();
    if !asset.edges.is_empty() {
        for f in &faces {
            for i in 0..f.vertices.len() {
                let a = f.vertices[i];
                let b = f.vertices[(i + 1) % f.vertices.len()];
                used_edges.insert(if a < b { (a, b) } else { (b, a) });
            }
        }
        if asset.edges.values().any(|[a, b]| {
            !used_edges.contains(
                &(if a < b {
                    (a.as_str(), b.as_str())
                } else {
                    (b.as_str(), a.as_str())
                }),
            )
        }) {
            return Err(error("loose edges"));
        }
    }
    let layers: BTreeSet<_> = faces.iter().flat_map(|f| f.uv.keys().copied()).collect();
    if faces
        .iter()
        .any(|f| f.uv.keys().copied().collect::<BTreeSet<_>>() != layers)
    {
        return Err(error("incomplete UV layer coverage"));
    }
    if let Some(layout) = &asset.uv_layout {
        if layout
            .layers
            .iter()
            .map(String::as_str)
            .collect::<BTreeSet<_>>()
            != layers
        {
            return Err(error("UV layout includes unrepresented layers"));
        }
    }
    Ok(())
}
struct Writer<'a> {
    scene: &'a Scene,
    out: String,
    vertices: usize,
    faces: usize,
    corners: usize,
    meshes: usize,
    entities: usize,
    materials: BTreeSet<String>,
}
impl Writer<'_> {
    fn entity(&mut self, id: &str, depth: usize) -> Result<()> {
        self.entities += 1;
        if depth > 128 || self.entities > 4096 {
            return Err(error("entity/depth limit exceeded"));
        }
        let entity = &self.scene.entities[id];
        let name = text_value(&entity.name)?;
        let matrix = if self.scene.object_context.is_some() {
            return Err(error("object context is not supported"));
        } else {
            crate::transforms::local(&entity.transform)?
        };
        writeln!(self.out, "def Xform {:?} {{", identifier(id)).expect("String write");
        writeln!(
            self.out,
            "custom string formora:sourceId = {}\ncustom string formora:name = {name}",
            quoted(id)
        )
        .expect("String write");
        let rows = (0..4)
            .map(|r| {
                format!(
                    "({})",
                    (0..4)
                        .map(|c| matrix[c][r].to_string())
                        .collect::<Vec<_>>()
                        .join(", ")
                )
            })
            .collect::<Vec<_>>();
        if matrix.iter().flatten().any(|v| !v.is_finite()) {
            return Err(error("nonfinite transform"));
        }
        writeln!(self.out, "matrix4d xformOp:transform = ({})\nuniform token[] xformOpOrder = [\"xformOp:transform\"]",rows.join(", ")).expect("String write");
        match &entity.content {
            EntityKind::Empty => {}
            EntityKind::Mesh {
                geometry: Geometry::Asset { id: mesh_id },
                material,
            } => {
                self.mesh(mesh_id, material.as_deref())?;
            }
            _ => {
                return Err(error(format!(
                    "unsupported entity: {id}; use explicit static meshes"
                )));
            }
        }
        let children: Vec<_> = self
            .scene
            .entities
            .iter()
            .filter(|(_, e)| e.parent.as_deref() == Some(id))
            .map(|(k, _)| k.clone())
            .collect();
        for child in children {
            self.entity(&child, depth + 1)?;
        }
        self.out.push_str("}\n");
        if self.out.len() > MAX_BYTES {
            return Err(error("output exceeds 256 MiB"));
        }
        Ok(())
    }
    fn mesh(&mut self, id: &str, fallback: Option<&str>) -> Result<()> {
        let asset = &self.scene.mesh_assets[id];
        supported(asset)?;
        for point in asset.vertices.values() {
            for value in point {
                float(*value)?;
            }
        }
        let faces = faces(asset);
        self.meshes += 1;
        self.vertices += asset.vertices.len();
        self.faces += faces.len();
        self.corners += faces.iter().map(|f| f.vertices.len()).sum::<usize>();
        if self.vertices > 200000 || self.faces > 200000 || self.corners > 800000 {
            return Err(error("geometry limit exceeded"));
        }
        let vertex_ids: Vec<_> = asset.vertices.keys().map(String::as_str).collect();
        let index: HashMap<_, _> = vertex_ids
            .iter()
            .enumerate()
            .map(|(i, id)| (*id, i))
            .collect();
        // project validated the entire immutable scene inside the core clock.
        let normals = match crate::mesh::normals::resolved_flat_validated(asset)? {
            Some(normals) => normals,
            None => crate::mesh::normals::resolved(asset)?,
        };
        let normals: BTreeMap<_, _> = normals
            .faces
            .iter()
            .map(|f| (&f.face, &f.corner_normals))
            .collect();
        let mut corner_normals = Vec::new();
        let mut bindings: BTreeMap<&str, Vec<usize>> = BTreeMap::new();
        for (i, f) in faces.iter().enumerate() {
            let key = if f.kind == "triangle" {
                FaceRef::Triangle(f.id.into())
            } else {
                FaceRef::Polygon(f.id.into())
            };
            for n in normals[&key] {
                corner_normals.push(vector(*n)?);
            }
            let material = f
                .material
                .and_then(|s| asset.material_slots[s].as_deref())
                .or(fallback)
                .ok_or_else(|| error(format!("face has no material: {}", f.id)))?;
            if !self.scene.materials.contains_key(material) {
                return Err(error("unknown material"));
            }
            bindings.entry(material).or_default().push(i);
        }
        for material in bindings.keys() {
            self.materials.insert((*material).into());
        }
        // Validate even unused slots: missing material must not become silent loss.
        if asset
            .material_slots
            .iter()
            .flatten()
            .any(|id| !self.scene.materials.contains_key(id))
        {
            return Err(error("unknown material slot"));
        }
        self.out.push_str("def Mesh \"Geometry\" (prepend apiSchemas = [\"MaterialBindingAPI\"]) {\nuniform token subdivisionScheme = \"none\"\nuniform token orientation = \"rightHanded\"\nbool doubleSided = false\n");
        writeln!(self.out, "custom string formora:meshId = {}", quoted(id)).expect("String write");
        writeln!(
            self.out,
            "custom string[] formora:vertexIds = {}",
            list(vertex_ids.iter().map(|s| quoted(s)))
        )
        .expect("String write");
        writeln!(
            self.out,
            "custom string[] formora:faceIds = {}\ncustom string[] formora:faceKinds = {}",
            list(faces.iter().map(|f| quoted(f.id))),
            list(faces.iter().map(|f| quoted(f.kind)))
        )
        .expect("String write");
        let points = asset
            .vertices
            .values()
            .map(|v| vector(*v))
            .collect::<Result<Vec<_>>>()?;
        writeln!(
            self.out,
            "point3f[] points = {}\nint[] faceVertexCounts = {}\nint[] faceVertexIndices = {}",
            list(points),
            list(faces.iter().map(|f| f.vertices.len())),
            list(
                faces
                    .iter()
                    .flat_map(|f| f.vertices.iter().map(|id| index[id]))
            )
        )
        .expect("String write");
        writeln!(
            self.out,
            "normal3f[] normals = {} (interpolation = \"faceVarying\")",
            list(corner_normals)
        )
        .expect("String write");
        for layer in faces[0].uv.keys() {
            let active = asset
                .uv_layout
                .as_ref()
                .and_then(|l| l.active.as_deref())
                .or_else(|| faces[0].uv.keys().next().copied());
            let name = if Some(*layer) == active {
                "st".into()
            } else {
                identifier(layer)
            };
            let values = faces
                .iter()
                .flat_map(|f| f.uv[layer].iter())
                .map(|v| vector(*v))
                .collect::<Result<Vec<_>>>()?;
            writeln!(self.out,"texCoord2f[] primvars:{name} = {} (interpolation = \"faceVarying\")\ncustom string formora:uv_{name} = {}",list(values),text_value(layer)?).expect("String write");
            if self.out.len() > MAX_BYTES {
                return Err(error("output exceeds 256 MiB"));
            }
        }
        if bindings.len() == 1 {
            writeln!(
                self.out,
                "rel material:binding = </Formora/Materials/{}>",
                identifier(bindings.keys().next().unwrap())
            )
            .expect("String write");
        } else {
            self.out
                .push_str("uniform token subsetFamily:materialBind:familyType = \"partition\"\n");
            for (material, indices) in bindings {
                let name = identifier(material);
                writeln!(self.out,"def GeomSubset \"{name}\" (prepend apiSchemas = [\"MaterialBindingAPI\"]) {{\nuniform token elementType = \"face\"\nuniform token familyName = \"materialBind\"\nint[] indices = {}\nrel material:binding = </Formora/Materials/{name}>\n}}",list(indices)).expect("String write");
            }
        }
        self.out.push_str("}\n");
        Ok(())
    }
}
/// Complete validation and serialization are part of the core clock.
pub fn project(scene: &Scene, root: &str) -> Result<Projection> {
    if scene.entities.len() > 4096 {
        return Err(error("scene entity limit exceeded"));
    }
    scene.validate()?;
    if scene.time_seconds != 0.
        || !scene.doors.is_empty()
        || !scene.annotations.is_empty()
        || scene.authoring_context.is_some()
        || scene.object_context.is_some()
    {
        return Err(error("scene has unsupported nonstatic or editor state"));
    }
    let entity = scene
        .entities
        .get(root)
        .ok_or_else(|| error("unknown root"))?;
    if entity.parent.is_some() {
        return Err(error("root must not have an external parent"));
    }
    let mut w = Writer {
        scene,
        out: format!(
            "#usda 1.0\n(\ndefaultPrim = \"Formora\"\nmetersPerUnit = 1\nupAxis = \"Z\"\n)\ndef Xform \"Formora\" {{\ncustom uint64 formora:revision = {}\n",
            scene.revision
        ),
        vertices: 0,
        faces: 0,
        corners: 0,
        meshes: 0,
        entities: 0,
        materials: BTreeSet::new(),
    };
    w.entity(root, 1)?;
    if w.meshes == 0 {
        return Err(error("subtree contains no mesh"));
    }
    w.out.push_str("def Scope \"Materials\" {\n");
    for id in &w.materials {
        let m = &scene.materials[id];
        let name = identifier(id);
        writeln!(w.out,"def Material \"{name}\" {{\ncustom string formora:sourceId = {}\ntoken outputs:surface.connect = </Formora/Materials/{name}/Surface.outputs:surface>\ndef Shader \"Surface\" {{\nuniform token info:id = \"UsdPreviewSurface\"\ncolor3f inputs:diffuseColor = {}\nfloat inputs:opacity = {}\nfloat inputs:roughness = {}\nfloat inputs:metallic = {}\ntoken outputs:surface\n}}\n}}",quoted(id),vector([m.base_color[0],m.base_color[1],m.base_color[2]])?,float(m.base_color[3])?,float(m.roughness)?,float(m.metallic)?).expect("String write");
    }
    w.out.push_str("}\n}\n");
    if w.out.len() > MAX_BYTES {
        return Err(error("output exceeds 256 MiB"));
    }
    Ok(Projection {
        text: w.out,
        meshes: w.meshes,
        vertices: w.vertices,
        faces: w.faces,
    })
}
/// Publish a complete file without replacing any existing target, including links.
pub fn export(scene: &Scene, request: &ExportRequest) -> Result<ExportReceipt> {
    if request.format != "usda" {
        return Err(error("unsupported format; only usda is implemented"));
    }
    let target = Path::new(&request.output);
    if target.extension().and_then(|s| s.to_str()) != Some("usda") {
        return Err(error("output must end in .usda"));
    }
    let start = std::time::Instant::now();
    let projection = project(scene, &request.root)?;
    let core_elapsed_ns = start.elapsed().as_nanos();
    let parent = target
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let (temp, mut file) = loop {
        let path = parent.join(format!(
            ".formora-usd-{}-{}.tmp",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(f) => break (path, f),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(error(e.to_string())),
        }
    };
    let result = (|| -> std::io::Result<()> {
        file.write_all(projection.text.as_bytes())?;
        file.sync_all()?;
        drop(file);
        std::fs::hard_link(&temp, target)
    })();
    let cleanup = std::fs::remove_file(&temp);
    result.map_err(|e| error(e.to_string()))?;
    // A cleanup error does not make the published, fully synced file partial.
    // Report it explicitly rather than claiming a clean export.
    cleanup.map_err(|e| {
        error(format!(
            "published output but temporary cleanup failed: {e}"
        ))
    })?;
    Ok(ExportReceipt {
        format: "usda".into(),
        root: request.root.clone(),
        revision: scene.revision,
        meshes: projection.meshes,
        vertices: projection.vertices,
        faces: projection.faces,
        bytes: projection.text.len(),
        core_elapsed_ns,
        sha256: format!("{:x}", Sha256::digest(projection.text.as_bytes())),
        output: request.output.clone(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn model() -> Scene {
        let mut scene = Scene::default();
        let request: crate::session::ApplyRequest =
            serde_json::from_str(include_str!("../baseline/static-usd/rock/create.json")).unwrap();
        // Editor's transaction is purely in memory. No Session/files/processes.
        let mut editor = crate::scene::Editor::new(scene).unwrap();
        editor
            .apply(&request.commands, Some(request.expected_revision))
            .unwrap();
        scene = editor.scene().clone();
        scene
    }
    #[test]
    fn original_geometry_material_hierarchy_and_determinism() {
        let s = model();
        let before = s.clone();
        let a = project(&s, "rock").unwrap();
        let b = project(&s, "rock").unwrap();
        assert_eq!((a.meshes, a.vertices, a.faces), (1, 6, 8));
        assert_eq!(a.text, b.text);
        assert_eq!(s, before);
        assert!(a.text.contains("metersPerUnit = 1"));
        assert!(a.text.contains("upAxis = \"Z\""));
        assert!(a.text.contains("formora:sourceId = \"rock_body\""));
        assert!(a.text.contains("UsdPreviewSurface"));
        assert!(a.text.contains("faceVarying"));
    }
    #[test]
    fn reject_lossy_and_nonstatic_inputs() {
        let mut s = model();
        s.mesh_assets
            .get_mut("rock_body")
            .unwrap()
            .vertices
            .get_mut("v0")
            .unwrap()[0] = 1e20;
        assert!(project(&s, "rock").unwrap_err().0.contains("1e-6"));
        let mut s = model();
        s.time_seconds = 1.;
        assert!(project(&s, "rock").is_err());
        let mut s = model();
        s.entities.get_mut("rock_body").unwrap().name = "bad\nname".into();
        assert!(project(&s, "rock").is_err());
        let mut s = model();
        s.mesh_assets
            .get_mut("rock_body")
            .unwrap()
            .vertex_groups
            .push("skin".into());
        assert!(project(&s, "rock").is_err());
    }
    #[test]
    fn transpose_preserves_translation_and_pivot() {
        let mut s = model();
        s.entities
            .get_mut("rock_body")
            .unwrap()
            .transform
            .translation = [0.125, -0.25, 0.5];
        let out = project(&s, "rock").unwrap().text;
        assert!(out.contains("(0.125, -0.25, 0.5, 1)"));
        assert_eq!(identifier("a-b"), "id_612d62");
        assert_ne!(identifier("a-b"), identifier("a_b"));
    }
    #[test]
    fn preserve_face_material_slots_and_uvs_or_reject_missing_corners() {
        let mut s = model();
        let second = s.materials["stone"].clone();
        s.materials.insert("second".into(), second);
        let a = s.mesh_assets.get_mut("rock_body").unwrap();
        a.material_slots = vec![Some("stone".into()), Some("second".into())];
        for (i, f) in a.triangles.values_mut().enumerate() {
            f.material_slot = Some(i % 2);
            f.uv_layers
                .insert("uv".into(), [[0., 0.], [1., 0.], [0., 1.]]);
            f.corner_normals = Some([[0., 0., 1.]; 3]);
        }
        let out = project(&s, "rock").unwrap().text;
        assert!(out.contains("def GeomSubset"));
        assert!(out.contains("partition"));
        assert!(out.contains("primvars:st"));
        assert!(out.contains("(0, 0, 1)"));
        s.mesh_assets
            .get_mut("rock_body")
            .unwrap()
            .triangles
            .get_mut("f000")
            .unwrap()
            .uv_layers
            .clear();
        assert!(project(&s, "rock").unwrap_err().0.contains("UV"));
    }
    #[test]
    fn reject_isolated_geometry_missing_materials_and_empty_subtrees() {
        let mut s = model();
        s.mesh_assets
            .get_mut("rock_body")
            .unwrap()
            .vertices
            .insert("loose".into(), [0.; 3]);
        assert!(project(&s, "rock").unwrap_err().0.contains("isolated"));
        let mut s = model();
        s.entities.get_mut("rock_body").unwrap().content = EntityKind::Mesh {
            geometry: Geometry::Asset {
                id: "rock_body".into(),
            },
            material: None,
        };
        assert!(project(&s, "rock").unwrap_err().0.contains("material"));
        assert!(project(&model(), "missing").is_err());
        let mut s = model();
        s.entities.remove("rock_body");
        assert!(project(&s, "rock").unwrap_err().0.contains("no mesh"));
    }
}

//! Fixed 100x100 selection contract. Run with --release on the specified native host.
use formora::mesh::{MeshAsset, Polygon, UvLayout, selection::*};
use formora::scene::{Command, Material, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, path::Path, time::Instant};

fn vertex(x: usize, y: usize) -> String {
    format!("v{:06}", y * 101 + x)
}
fn fixture(mode: Domain) -> MeshAsset {
    let mut mesh = MeshAsset::default();
    for y in 0..=100 {
        for x in 0..=100 {
            mesh.vertices.insert(vertex(x, y), [x as f64, y as f64, 0.]);
        }
    }
    for y in 0..=100 {
        for x in 0..=100 {
            for (nx, ny) in [(x + 1, y), (x, y + 1)] {
                if nx > 100 || ny > 100 {
                    continue;
                }
                let index = mesh.edges.len();
                let id = format!("e{index:06}");
                mesh.edges
                    .insert(id.clone(), [vertex(x, y), vertex(nx, ny)]);
                if index % 3 == 0 {
                    mesh.edge_seams.insert(id);
                }
            }
        }
    }
    for y in 0..100 {
        for x in 0..100 {
            let i = y * 100 + x;
            mesh.polygons.insert(
                format!("f{i:06}"),
                Polygon {
                    corner_colors: None,
                    vertices: vec![
                        vertex(x, y),
                        vertex(x + 1, y),
                        vertex(x + 1, y + 1),
                        vertex(x, y + 1),
                    ],
                    uv_layers: [("UV0", 1.), ("UV1", -1.)]
                        .into_iter()
                        .map(|(name, sign)| {
                            (
                                name.into(),
                                (0..4)
                                    .map(|c| {
                                        [
                                            sign * (i as f64 + c as f64 * 0.125),
                                            sign * c as f64 * 0.25,
                                        ]
                                    })
                                    .collect(),
                            )
                        })
                        .collect(),
                    corner_normals: None,
                    normal: None,
                    smooth: i % 2 != 0,
                    material_slot: Some(i % 2),
                },
            );
        }
    }
    mesh.uv_layout = Some(UvLayout {
        layers: vec!["UV0".into(), "UV1".into()],
        active: Some("UV0".into()),
    });
    mesh.material_slots = vec![Some("even".into()), Some("odd".into())];
    mesh.vertex_groups = vec!["Half".into()];
    mesh.vertex_weights = Some(VertexWeights(
        mesh.vertices
            .iter()
            .filter(|(_, p)| p[0] < 50.)
            .map(|(id, _)| {
                (
                    id.clone(),
                    GroupWeights(BTreeMap::from([("Half".into(), 1.)])),
                )
            })
            .collect(),
    ));
    let mut editing = Editing {
        mode: [mode].into(),
        ..Default::default()
    };
    match mode {
        Domain::Vertex => {
            editing.selected.vertices = mesh
                .vertices
                .iter()
                .filter(|(_, p)| p[0] < 50.)
                .map(|(id, _)| id.clone())
                .collect()
        }
        Domain::Edge => {
            editing.selected.edges = mesh
                .edges
                .iter()
                .filter(|(_, p)| (mesh.vertices[&p[0]][0] + mesh.vertices[&p[1]][0]) / 2. < 50.)
                .map(|(id, _)| id.clone())
                .collect()
        }
        Domain::Face => {
            editing.selected.faces = mesh
                .polygons
                .iter()
                .filter(|(_, p)| {
                    p.vertices.iter().map(|v| mesh.vertices[v][0]).sum::<f64>() / 4. < 50.
                })
                .map(|(id, _)| FaceRef::Polygon(id.clone()))
                .collect()
        }
    }
    set_editing(&mut mesh, Some(editing)).unwrap();
    mesh.validate().unwrap();
    assert_eq!(
        (mesh.vertices.len(), mesh.edges.len(), mesh.polygons.len()),
        (10201, 20200, 10000)
    );
    mesh
}
fn selector(feature: &str, p: &Value) -> Selector {
    let domain = |v: &Value| match v.as_str().unwrap() {
        "VERT" => Domain::Vertex,
        "EDGE" => Domain::Edge,
        "FACE" => Domain::Face,
        _ => panic!("domain"),
    };
    match feature {
        "mode" | "expand" | "contract" | "combined_modes" => Selector::Mode {
            domain: domain(&p["type"]),
            action: if p["action"] == "ENABLE" {
                ModeAction::Enable
            } else {
                ModeAction::Toggle
            },
            extend: p["use_extend"].as_bool().unwrap_or(false),
            expand: p["use_expand"].as_bool().unwrap_or(false),
        },
        "non_manifold" => Selector::NonManifold {
            extend: p["extend"].as_bool().unwrap(),
            wire: p["use_wire"].as_bool().unwrap(),
            boundary: p["use_boundary"].as_bool().unwrap(),
            multiple_faces: p["use_multi_face"].as_bool().unwrap(),
            non_contiguous: p["use_non_contiguous"].as_bool().unwrap(),
            vertices: p["use_verts"].as_bool().unwrap(),
        },
        "loose" => Selector::Loose {
            extend: p["extend"].as_bool().unwrap(),
        },
        "interior_faces" => Selector::InteriorFaces {},
        "faces_by_sides" => {
            assert_eq!(p["type"], "EQUAL");
            Selector::FacesBySides {
                count: p["number"].as_u64().unwrap() as u32,
                comparison: CountComparison::Equal,
                extend: p["extend"].as_bool().unwrap(),
            }
        }
        "poles" => {
            assert_eq!(p["type"], "NOTEQUAL");
            Selector::Poles {
                count: p["pole_count"].as_u64().unwrap() as u32,
                comparison: CountComparison::NotEqual,
                exclude_nonmanifold: p["exclude_nonmanifold"].as_bool().unwrap(),
                extend: p["extend"].as_bool().unwrap(),
            }
        }
        "ungrouped" => Selector::Ungrouped {
            extend: p["extend"].as_bool().unwrap(),
        },
        _ => panic!("feature"),
    }
}
fn digest<T: serde::Serialize>(value: &T) -> String {
    format!("{:x}", Sha256::digest(serde_json::to_vec(value).unwrap()))
}
fn unchanged(before: &MeshAsset, after: &MeshAsset) {
    let mut a = before.clone();
    let mut b = after.clone();
    a.editing = None;
    b.editing = None;
    assert_eq!(a, b);
}
fn main() {
    assert!(
        !cfg!(debug_assertions),
        "performance acceptance requires a release build"
    );
    let output = std::env::args().nth(1).expect("output directory");
    let output = Path::new(&output);
    std::fs::create_dir(output).unwrap();
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let origin = Instant::now();
    let mut records = Vec::new();
    for feature in [
        "mode",
        "expand",
        "contract",
        "combined_modes",
        "non_manifold",
        "loose",
        "interior_faces",
        "faces_by_sides",
        "poles",
        "ungrouped",
    ] {
        let path = root.join(format!("baseline/cases/mesh-selection-{feature}.json"));
        let data = std::fs::read(&path).unwrap();
        let contract: Value = serde_json::from_slice(&data).unwrap();
        let perf = &contract["fixture"]["performance_contract"];
        assert_eq!(perf["maximum_core_ms"], 100);
        assert_eq!(perf["maximum_select_save_reload_ms"], 2000);
        assert_eq!(perf["runs_per_function_and_conversion"], 3);
        let mode = match perf["initial_mode"][0].as_str().unwrap() {
            "VERT" => Domain::Vertex,
            "EDGE" => Domain::Edge,
            "FACE" => Domain::Face,
            _ => panic!("mode"),
        };
        let prepared = fixture(mode);
        let selector = selector(feature, &perf["parameters"]);
        for run in 1..=3 {
            let mut core = prepared.clone();
            let core_start = origin.elapsed().as_nanos();
            let result = apply(&mut core, &selector).unwrap();
            let core_end = origin.elapsed().as_nanos();
            assert_eq!(result, Outcome::Completed);
            unchanged(&prepared, &core);
            let mut scene = Scene::default();
            scene.mesh_assets.insert("grid".into(), prepared.clone());
            for name in ["even", "odd"] {
                scene.materials.insert(
                    name.into(),
                    Material {
                        base_color: [0.4, 0.6, 0.8, 1.],
                        roughness: 0.6,
                        metallic: 0.,
                    },
                );
            }
            let path = output.join(format!("{feature}-{run}.json"));
            let mut session = Session::create(&path, scene).unwrap();
            let pipeline_start = origin.elapsed().as_nanos();
            let receipt = session
                .apply_with_result(ApplyRequest {
                    expected_revision: 0,
                    commands: vec![Command::SelectMesh {
                        id: "grid".into(),
                        selector: selector.clone(),
                    }],
                })
                .unwrap();
            let restored = Scene::load(&path).unwrap();
            let pipeline_end = origin.elapsed().as_nanos();
            assert_eq!(receipt.selection[0].outcome, result);
            assert_eq!(restored.mesh_assets["grid"], core);
            assert_eq!(restored, *session.scene());
            let core_ms = (core_end - core_start) as f64 / 1e6;
            let pipeline_ms = (pipeline_end - pipeline_start) as f64 / 1e6;
            let record = json!({"feature":feature,"run":run,"core_start_ns":core_start,"core_end_ns":core_end,
                "pipeline_start_ns":pipeline_start,"pipeline_end_ns":pipeline_end,"core_ms":core_ms,"select_save_reload_ms":pipeline_ms,
                "passed":core_ms<=100. && pipeline_ms<=2000.,"contract_sha256":format!("{:x}",Sha256::digest(&data)),
                "input_asset_sha256":digest(&prepared),"output_asset_sha256":digest(&core),"attributes_unchanged":true,"reload_equal":true});
            println!("{record}");
            records.push(record);
            drop(session);
        }
    }
    let passed = records.iter().all(|r| r["passed"] == true);
    let report = json!({"passed":passed,"profile":"release","runs":records,"full_feature_acceptance":"unrun"});
    std::fs::write(
        output.join("report.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .unwrap();
    assert!(passed, "fixed selection performance contract failed");
}

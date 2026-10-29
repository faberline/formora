//! Fixed issue #32 sample. Run with cargo run --release --example polygon_asset_bench.
use formora::mesh::{MeshAsset, Polygon, UvLayout};
use formora::scene::{Command, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::json;
use std::collections::BTreeMap;
use std::time::Instant;

fn sample() -> MeshAsset {
    let mut asset = MeshAsset {
        uv_layout: Some(UvLayout {
            layers: vec!["UVMap".into()],
            active: Some("UVMap".into()),
        }),
        ..Default::default()
    };
    for y in 0..=100 {
        for x in 0..=100 {
            asset
                .vertices
                .insert(format!("v_{x}_{y}"), [x as f64, y as f64, 0.]);
            if x < 100 {
                asset.edges.insert(
                    format!("h_{x}_{y}"),
                    [format!("v_{x}_{y}"), format!("v_{}_{y}", x + 1)],
                );
            }
            if y < 100 {
                asset.edges.insert(
                    format!("v_{x}_{y}"),
                    [format!("v_{x}_{y}"), format!("v_{x}_{}", y + 1)],
                );
            }
            if x < 100 && y < 100 {
                asset.polygons.insert(
                    format!("p_{x}_{y}"),
                    Polygon {
                        vertices: vec![
                            format!("v_{x}_{y}"),
                            format!("v_{}_{y}", x + 1),
                            format!("v_{}_{}", x + 1, y + 1),
                            format!("v_{x}_{}", y + 1),
                        ],
                        uv_layers: BTreeMap::from([(
                            "UVMap".into(),
                            vec![[0., 0.], [1., 0.], [1., 1.], [0., 1.]],
                        )]),
                        corner_normals: Some(vec![[0., 0., 1.]; 4]),
                        normal: Some([0., 0., 1.]),
                        smooth: false,
                        material_slot: None,
                    },
                );
            }
        }
    }
    asset
}

fn main() {
    if cfg!(debug_assertions) {
        eprintln!("performance acceptance requires a release build");
        std::process::exit(64);
    }
    let asset = sample();
    assert_eq!(
        (
            asset.vertices.len(),
            asset.edges.len(),
            asset.polygons.len()
        ),
        (10201, 20200, 10000)
    );
    let root = std::env::temp_dir().join(format!("formora-polygon-bench-{}", std::process::id()));
    std::fs::create_dir(&root).unwrap();
    let mut runs = Vec::new();
    for run in 0..3 {
        let start = Instant::now();
        asset.validate().unwrap();
        let validation_ms = start.elapsed().as_secs_f64() * 1000.;
        let start = Instant::now();
        let tessellation = asset.tessellate().unwrap();
        let tessellation_ms = start.elapsed().as_secs_f64() * 1000.;
        assert_eq!(tessellation.triangles.len(), 20000);
        assert!(tessellation.diagnostics.is_empty());
        let path = root.join(format!("{run}.json"));
        let start = Instant::now();
        let mut session = Session::create(&path, Scene::default()).unwrap();
        session
            .apply(ApplyRequest {
                expected_revision: 0,
                commands: vec![Command::SetMeshAsset {
                    id: "grid".into(),
                    asset: Box::new(asset.clone()),
                }],
            })
            .unwrap();
        session
            .apply(ApplyRequest {
                expected_revision: 1,
                commands: vec![Command::SetMeshVertices {
                    id: "grid".into(),
                    positions: BTreeMap::from([("v_50_50".into(), [50., 50., 0.5])]),
                }],
            })
            .unwrap();
        let restored = Scene::load(&path).unwrap();
        let total_ms = start.elapsed().as_secs_f64() * 1000.;
        assert_eq!(session.scene(), &restored);
        assert_eq!(restored.mesh_assets["grid"].polygons, asset.polygons);
        assert_eq!(restored.mesh_assets["grid"].edges, asset.edges);
        assert_eq!(
            restored.mesh_assets["grid"].vertices["v_50_50"],
            [50., 50., 0.5]
        );
        runs.push(json!({"run":run+1,"validation_ms":validation_ms,"tessellation_ms":tessellation_ms,"create_edit_save_reload_ms":total_ms,"passed":validation_ms<=250. && tessellation_ms<=500. && total_ms<=2000.}));
    }
    std::fs::remove_dir_all(root).unwrap();
    let passed = runs.iter().all(|r| r["passed"] == true);
    println!(
        "{}",
        json!({"sample":{"vertices":10201,"edges":20200,"polygons":10000},"limits_ms":{"validation":250,"tessellation":500,"create_edit_save_reload":2000},"runs":runs,"passed":passed,"full_product_acceptance":false})
    );
    assert!(passed, "fixed polygon performance contract failed");
}

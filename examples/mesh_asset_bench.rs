//! The fixed issue #30 sample. Run with `cargo run --release --example mesh_asset_bench`.
use formora::mesh::{MeshAsset, Triangle};
use formora::scene::{Command, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::json;
use std::collections::BTreeMap;
use std::time::Instant;

fn sample() -> MeshAsset {
    let mut asset = MeshAsset::default();
    for y in 0..=100 {
        for x in 0..=100 {
            asset
                .vertices
                .insert(format!("v_{}_{}", x, y), [x as f64, y as f64, 0.]);
        }
    }
    for y in 0..100 {
        for x in 0..100 {
            let a = format!("v_{}_{}", x, y);
            let b = format!("v_{}_{}", x + 1, y);
            let c = format!("v_{}_{}", x + 1, y + 1);
            let d = format!("v_{}_{}", x, y + 1);
            for (i, vertices) in [[a.clone(), b, c.clone()], [a, c, d]]
                .into_iter()
                .enumerate()
            {
                asset.triangles.insert(
                    format!("t_{}_{}_{}", x, y, i),
                    Triangle {
                        vertices,
                        uv_layers: BTreeMap::from([(
                            "UVMap".into(),
                            [[0., 0.], [1., 0.], [1., 1.]],
                        )]),
                        corner_normals: Some([[0., 0., 1.]; 3]),
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
    assert_eq!(asset.vertices.len(), 10_201);
    assert_eq!(asset.triangles.len(), 20_000);
    let root = std::env::temp_dir().join(format!("formora-mesh-bench-{}", std::process::id()));
    std::fs::create_dir(&root).unwrap();
    let mut runs = Vec::new();
    for run in 0..3 {
        let start = Instant::now();
        asset.validate().unwrap();
        let validation_ms = start.elapsed().as_secs_f64() * 1000.;
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
        assert_eq!(
            restored.mesh_assets["grid"].vertices["v_50_50"],
            [50., 50., 0.5]
        );
        assert_eq!(restored.mesh_assets["grid"].triangles, asset.triangles);
        let passed = validation_ms <= 250. && total_ms <= 2000.;
        runs.push(json!({"run":run+1,"validation_ms":validation_ms,"create_edit_save_reload_ms":total_ms,"passed":passed}));
    }
    std::fs::remove_dir_all(root).unwrap();
    let passed = runs.iter().all(|r| r["passed"] == true);
    println!(
        "{}",
        json!({"sample":{"vertices":10201,"triangles":20000},"limits_ms":{"validation":250,"create_edit_save_reload":2000},"runs":runs,"passed":passed,"full_product_acceptance":false})
    );
    assert!(passed, "fixed performance contract failed");
}

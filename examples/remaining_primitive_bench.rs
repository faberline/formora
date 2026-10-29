//! Fixed issue #42 samples. Run with the actual Rust 1.85 toolchain and --release.
use formora::mesh::primitives::{DEFAULT_MAX_COMPONENTS, Primitive};
use formora::scene::{Command, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::json;
use std::time::Instant;

fn main() {
    assert!(
        !cfg!(debug_assertions),
        "performance acceptance requires release"
    );
    let root = std::env::temp_dir().join(format!("formora-remaining-bench-{}", std::process::id()));
    std::fs::create_dir(&root).unwrap();
    let origin = Instant::now();
    let mut records = vec![];
    for (name, initial, changed) in [
        (
            "ico_sphere_level6",
            json!({"kind":"ico_sphere","subdivisions":6}),
            json!({"kind":"ico_sphere","subdivisions":6,"radius":1.5}),
        ),
        (
            "monkey_default",
            json!({"kind":"monkey"}),
            json!({"kind":"monkey","size":3.}),
        ),
    ] {
        let initial: Primitive = serde_json::from_value(initial).unwrap();
        let changed: Primitive = serde_json::from_value(changed).unwrap();
        for run in 1..=3 {
            let generation_start = origin.elapsed().as_nanos();
            let generated = initial.generate(DEFAULT_MAX_COMPONENTS).unwrap();
            let generation_end = origin.elapsed().as_nanos();
            let path = root.join(format!("{name}-{run}.json"));
            let pipeline_start = origin.elapsed().as_nanos();
            let mut session = Session::create(&path, Scene::default()).unwrap();
            session
                .apply(ApplyRequest {
                    expected_revision: 0,
                    commands: vec![Command::CreateMeshPrimitive {
                        id: "shape".into(),
                        primitive: initial.clone(),
                        max_components: DEFAULT_MAX_COMPONENTS,
                    }],
                })
                .unwrap();
            assert_eq!(session.scene().mesh_assets["shape"], generated);
            session
                .apply(ApplyRequest {
                    expected_revision: 1,
                    commands: vec![Command::RegenerateMeshPrimitive {
                        id: "shape".into(),
                        primitive: Some(changed.clone()),
                        max_components: None,
                    }],
                })
                .unwrap();
            let restored = Scene::load(&path).unwrap();
            let pipeline_end = origin.elapsed().as_nanos();
            assert_eq!(restored, *session.scene());
            assert_eq!(
                restored.mesh_assets["shape"]
                    .recipe
                    .as_ref()
                    .unwrap()
                    .primitive,
                changed
            );
            let generation_ms = (generation_end - generation_start) as f64 / 1e6;
            let pipeline_ms = (pipeline_end - pipeline_start) as f64 / 1e6;
            records.push(json!({"sample":name,"run":run,"generation_start_ns":generation_start,"generation_end_ns":generation_end,
                "pipeline_start_ns":pipeline_start,"pipeline_end_ns":pipeline_end,"generation_ms":generation_ms,
                "create_regenerate_save_reload_ms":pipeline_ms,"passed":generation_ms<=500. && pipeline_ms<=2000.,
                "vertices":generated.vertices.len(),"edges":generated.edges.len(),"faces":generated.polygons.len(),"reload_equal":true}));
            drop(session);
        }
    }
    std::fs::remove_dir_all(root).unwrap();
    let passed = records.iter().all(|r| r["passed"] == true);
    println!(
        "{}",
        json!({"passed":passed,"limits_ms":{"generation":500,"create_regenerate_save_reload":2000},"runs":records,"full_feature_acceptance":"unrun"})
    );
    assert!(
        passed,
        "fixed remaining primitive performance contract failed"
    );
}

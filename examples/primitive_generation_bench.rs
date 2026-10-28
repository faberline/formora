//! Fixed issue #34 procedural generation samples. Run with --release.
use formora::mesh::primitives::{DEFAULT_MAX_COMPONENTS, Primitive};
use formora::scene::{Command, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::json;
use std::time::Instant;
fn primitive(value: serde_json::Value) -> Primitive {
    serde_json::from_value(value).unwrap()
}
fn main() {
    if cfg!(debug_assertions) {
        eprintln!("performance acceptance requires a release build");
        std::process::exit(64);
    }
    let root = std::env::temp_dir().join(format!("formora-primitive-bench-{}", std::process::id()));
    std::fs::create_dir(&root).unwrap();
    let mut runs = vec![];
    for (name, initial, changed) in [
        (
            "grid_100x100",
            primitive(json!({"kind":"grid","x_subdivisions":100,"y_subdivisions":100})),
            primitive(json!({"kind":"grid","x_subdivisions":100,"y_subdivisions":100,"size":3.5})),
        ),
        (
            "circle_4096_ngon",
            primitive(json!({"kind":"circle","vertices":4096,"fill_type":"ngon"})),
            primitive(json!({"kind":"circle","vertices":4096,"fill_type":"ngon","radius":1.25})),
        ),
    ] {
        for run in 0..3 {
            let start = Instant::now();
            let generated = initial.generate(DEFAULT_MAX_COMPONENTS).unwrap();
            let generation_ms = start.elapsed().as_secs_f64() * 1000.;
            let path = root.join(format!("{name}-{run}.json"));
            let start = Instant::now();
            let mut session = Session::create(&path, Scene::default()).unwrap();
            session
                .apply(ApplyRequest {
                    expected_revision: 0,
                    commands: vec![Command::CreateMeshPrimitive {
                        id: "generated".into(),
                        primitive: initial.clone(),
                        max_components: DEFAULT_MAX_COMPONENTS,
                    }],
                })
                .unwrap();
            session
                .apply(ApplyRequest {
                    expected_revision: 1,
                    commands: vec![Command::RegenerateMeshPrimitive {
                        id: "generated".into(),
                        primitive: Some(changed.clone()),
                        max_components: None,
                    }],
                })
                .unwrap();
            let loaded = Scene::load(&path).unwrap();
            let total_ms = start.elapsed().as_secs_f64() * 1000.;
            assert_eq!(session.scene(), &loaded);
            assert_eq!(
                loaded.mesh_assets["generated"]
                    .recipe
                    .as_ref()
                    .unwrap()
                    .primitive,
                changed
            );
            assert_eq!(
                loaded.mesh_assets["generated"].vertices.len(),
                generated.vertices.len()
            );
            runs.push(json!({"sample":name,"run":run+1,"generation_ms":generation_ms,"create_regenerate_save_reload_ms":total_ms,"passed":generation_ms<=500. && total_ms<=2000.}));
        }
    }
    std::fs::remove_dir_all(root).unwrap();
    let passed = runs.iter().all(|r| r["passed"] == true);
    println!(
        "{}",
        json!({"limits_ms":{"generation":500,"create_regenerate_save_reload":2000},"runs":runs,"passed":passed,"full_feature_acceptance":"unrun"})
    );
    assert!(
        passed,
        "fixed primitive generation performance contract failed"
    );
}

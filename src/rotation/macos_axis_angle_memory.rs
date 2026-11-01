//! Source-only fixtures; no CLI, session lock, filesystem or source process.
use crate::scene::{Editor, Scene};
use crate::session::{ApplyRequest, InspectRequest};
use serde::Deserialize;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;

#[derive(Deserialize)]
struct SourceCase {
    id: String,
    setup: ApplyRequest,
    request: ApplyRequest,
    references: Vec<Reference>,
}
#[derive(Deserialize)]
struct Reference {
    phases: BTreeMap<String, Phase>,
}
#[derive(Deserialize)]
struct Phase {
    world_vertices: BTreeMap<String, BTreeMap<String, [f64; 3]>>,
    rotation_channels: BTreeMap<String, Value>,
}

#[test]
fn frozen_axis_angle_world_points_match_both_native_source_captures() {
    let cases: Vec<SourceCase> = serde_json::from_str(include_str!(
        "../../baseline/static-usd-macos-axis-angle/fixtures.json"
    ))
    .unwrap();
    compare_cases(cases, 17);
}

#[test]
fn all_frozen_rotation_world_points_match_both_native_source_captures() {
    // The reader wraps embedded bytes only. No file or source process is opened.
    let mut decoder = flate2::read::GzDecoder::new(
        &include_bytes!("../../baseline/static-usd-macos-axis-angle/all-world-fixtures.json.gz")[..],
    );
    let mut raw = Vec::new();
    decoder.read_to_end(&mut raw).unwrap();
    let cases: Vec<SourceCase> = serde_json::from_slice(&raw).unwrap();
    drop(raw);
    compare_cases(cases, 2496);
}

fn compare_cases(cases: Vec<SourceCase>, expected_cases: usize) {
    assert_eq!(cases.len(), expected_cases);
    let mut failures = Vec::new();
    let mut checked = 0;
    let mut emitted = BTreeSet::new();
    for case in &cases {
        assert_eq!(case.references.len(), 2);
        let mut editor = Editor::new(Scene::default()).unwrap();
        editor
            .apply(&case.setup.commands, Some(case.setup.expected_revision))
            .unwrap();
        for phase in ["before", "after"] {
            if phase == "after" {
                editor
                    .apply(&case.request.commands, Some(case.request.expected_revision))
                    .unwrap();
            }
            for reference in &case.references {
                let expected_phase = &reference.phases[phase];
                for (entity, points) in &expected_phase.world_vertices {
                    let actual = InspectRequest {
                        entity: Some(entity.clone()),
                        world: true,
                        ..Default::default()
                    }
                    .inspect(editor.scene())
                    .unwrap();
                    let found = actual["world_vertices"].as_object().unwrap();
                    assert_eq!(
                        points.keys().collect::<BTreeSet<_>>(),
                        found.keys().collect()
                    );
                    for (vertex, position) in points {
                        for (component, &expected) in position.iter().enumerate() {
                            assert!(expected.is_finite());
                            let observed = found[vertex][component].as_f64().unwrap();
                            checked += 1;
                            if !observed.is_finite() || (expected - observed).abs() > 1e-6 {
                                let detail = json!({
                                    "case":case.id,"phase":phase,"entity":entity,
                                    "vertex":vertex,"component":component,
                                    "expected":expected,"actual":observed
                                });
                                failures.push(detail.clone());
                                if emitted.insert((case.id.clone(), phase, entity.clone())) {
                                    let rotation = &actual["entity"]["transform"]["rotation"];
                                    let angle =
                                        rotation["channels"]["axis_angle"][0].as_f64().unwrap()
                                            as f32;
                                    let (s, c) = angle.sin_cos();
                                    println!(
                                        "{}",
                                        json!({"first_point_difference":detail,"rotation":rotation,
                                            "source_rotation_channels":expected_phase.rotation_channels[entity],
                                            "angle_bits":angle.to_bits(),
                                            "paired_sin_cos_bits":[s.to_bits(),c.to_bits()],
                                            "separate_sin_cos_bits":[angle.sin().to_bits(),angle.cos().to_bits()],
                                            "f64_sin_cos_to_f32_bits":[(f64::from(angle).sin() as f32).to_bits(),(f64::from(angle).cos() as f32).to_bits()]})
                                    );
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    println!(
        "{}",
        json!({"frozen_cases":cases.len(),"source_captures":cases.len()*2,
            "point_components_checked":checked,"violations":failures.len(),
            "scope":"memory-only source replay; not CLI/MCP/full acceptance"})
    );
    // Frozen suite: 27 vertices, two mesh users, two phases, two source
    // captures, and three coordinates. Empty or reduced references cannot pass.
    assert_eq!(checked, expected_cases * 27 * 2 * 2 * 2 * 3);
    assert!(
        failures.is_empty(),
        "first differences: {:?}",
        &failures[..failures.len().min(4)]
    );
}

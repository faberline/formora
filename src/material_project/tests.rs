use super::*;
use serde_json::{Value, json};
use std::collections::BTreeMap;

const SOURCE: &[u8] = include_bytes!("../../tests/fixtures/texture/uv_panel.scene.json");
const PNG: &[u8] = include_bytes!("../../tests/fixtures/texture/four-colors.png");
const PROJECT: &[u8] = include_bytes!("../../tests/fixtures/texture/project.json");

#[test]
fn original_ashfall_fixture_manifest_and_all_seven_resources_remain_fixed() {
    let manifest = include_bytes!("../../tests/fixtures/texture/manifest.json");
    assert_eq!(
        sha256(manifest),
        "5e61b47734aa27c01dd61bf93a8897746c4e9fc964d0b2ce42ed12b985d71f6a"
    );
    let parsed: Value = serde_json::from_slice(manifest).unwrap();
    for (name, bytes) in [
        ("uv_panel.scene.json", SOURCE),
        ("four-colors.png", PNG),
        (
            "uv-requirements.json",
            include_bytes!("../../tests/fixtures/texture/uv-requirements.json").as_slice(),
        ),
        (
            "rig-requirements.json",
            include_bytes!("../../tests/fixtures/texture/rig-requirements.json").as_slice(),
        ),
        (
            "two_bone_limb.scene.json",
            include_bytes!("../../tests/fixtures/texture/two_bone_limb.scene.json").as_slice(),
        ),
        (
            ".uv_panel.scene.json.formora.lock",
            include_bytes!("../../tests/fixtures/texture/.uv_panel.scene.json.formora.lock")
                .as_slice(),
        ),
        (
            ".two_bone_limb.scene.json.formora.lock",
            include_bytes!("../../tests/fixtures/texture/.two_bone_limb.scene.json.formora.lock")
                .as_slice(),
        ),
    ] {
        assert_eq!(
            sha256(bytes),
            parsed["files"][name].as_str().unwrap(),
            "{name}"
        );
    }
}

fn files() -> BTreeMap<String, Vec<u8>> {
    BTreeMap::from([
        ("uv_panel.scene.json".into(), SOURCE.to_vec()),
        ("four-colors.png".into(), PNG.to_vec()),
    ])
}
fn query(uv: [f64; 2]) -> Query {
    Query {
        entity: "mesh".into(),
        face: Face::Polygon { id: "p0001".into() },
        uv,
    }
}
fn changed(
    source_change: impl FnOnce(&mut Value),
    project_change: impl FnOnce(&mut Value),
) -> Result<PreparedProject, Failure> {
    let mut source: Value = serde_json::from_slice(SOURCE).unwrap();
    source_change(&mut source);
    let bytes = serde_json::to_vec(&source).unwrap();
    let mut f = files();
    f.insert("uv_panel.scene.json".into(), bytes.clone());
    let mut project: Value = serde_json::from_slice(PROJECT).unwrap();
    project["scene"]["sha256"] = json!(sha256(&bytes));
    project_change(&mut project);
    let bytes = serde_json::to_vec(&project).unwrap();
    validate_bytes(&bytes, &sha256(&bytes), &f)
}
fn code(result: Result<PreparedProject, Failure>, expected: ErrorCode) {
    match result {
        Ok(_) => panic!("Unexpected success"),
        Err(e) => {
            assert_eq!(e.code, expected);
            let value = serde_json::to_value(Receipt::Failure(e)).unwrap();
            for k in [
                "project_profile",
                "scene_profile",
                "producer_commit",
                "roots",
                "images",
                "samples",
                "saved_location",
            ] {
                assert!(value.get(k).is_none());
            }
        }
    }
}

#[test]
fn original_polygon_panel_and_png_are_preserved_exactly() {
    let p = validate_bytes(PROJECT, &sha256(PROJECT), &files()).unwrap();
    assert_eq!(p.project_bytes(), PROJECT);
    assert_eq!(p.resource_bytes("uv_panel.scene.json"), Some(SOURCE));
    assert_eq!(p.resource_bytes("four-colors.png"), Some(PNG));
    assert_eq!(p.scene.mesh_assets["mesh_mesh"].polygons.len(), 6);
    assert!(p.scene.mesh_assets["mesh_mesh"].triangles.is_empty());
    assert!(p.scene.mesh_assets["mesh_mesh"].uv_layout.is_some());
    assert!(p.scene.mesh_assets["mesh_mesh"].recipe.is_none());
    assert_eq!(p.inspect().polygons, 6);
    assert_eq!(p.inspect().images["four"].width, 4);
}

#[test]
fn quadrants_origin_endpoints_and_clamp_have_exact_rgb8_results() {
    let p = validate_bytes(PROJECT, &sha256(PROJECT), &files()).unwrap();
    let uv = [
        [0.25, 0.25],
        [0.75, 0.25],
        [0.25, 0.75],
        [0.75, 0.75],
        [0.0, 0.0],
        [1.0, 1.0],
        [-2.0, 2.0],
    ];
    let result = p.samples(&uv.map(query)).unwrap();
    let actual: Vec<_> = result.samples.iter().map(|s| s.rgba8).collect();
    assert_eq!(
        actual,
        [
            [0, 0, 255, 255],
            [255, 255, 0, 255],
            [255, 0, 0, 255],
            [0, 255, 0, 255],
            [0, 0, 255, 255],
            [0, 255, 0, 255],
            [255, 0, 0, 255]
        ]
    );
    assert_eq!(result.samples[0].texel, [1, 3]);
    assert_eq!(result.samples[2].texel, [1, 1]);
}

#[test]
fn middle_gray_proves_srgb_transfer_not_only_saturated_endpoints() {
    let image = image::Image {
        width: 1,
        height: 1,
        pixels: vec![128, 128, 128],
    };
    let texel = image.sample([0.5, 0.5]).unwrap();
    assert_eq!(texel.rgba8, [128, 128, 128, 255]);
    for x in &texel.linear_rgba[..3] {
        assert!((x - 0.21586050011389926).abs() <= 1e-12);
    }
    assert_eq!(texel.linear_rgba[3], 1.0);
}

#[test]
fn descriptor_hash_binds_path_profile_and_bindings_before_resources() {
    let mut p: Value = serde_json::from_slice(PROJECT).unwrap();
    p["bindings"]["fixture_white"]["uv_layer"] = json!("other");
    let bytes = serde_json::to_vec(&p).unwrap();
    let error = match validate_bytes(&bytes, &sha256(PROJECT), &BTreeMap::new()) {
        Err(e) => e,
        Ok(_) => panic!(),
    };
    assert_eq!(error.code, ErrorCode::HashMismatch);
    assert_eq!(error.stage, "project_hash");
}

#[test]
fn missing_images_and_hash_changes_are_explicit_failures() {
    let mut f = files();
    f.remove("four-colors.png");
    code(
        validate_bytes(PROJECT, &sha256(PROJECT), &f),
        ErrorCode::ImageMissing,
    );
    let mut f = files();
    f.insert("four-colors.png".into(), b"changed".to_vec());
    code(
        validate_bytes(PROJECT, &sha256(PROJECT), &f),
        ErrorCode::HashMismatch,
    );
    let mut f = files();
    f.insert("uv_panel.scene.json".into(), b"changed".to_vec());
    code(
        validate_bytes(PROJECT, &sha256(PROJECT), &f),
        ErrorCode::HashMismatch,
    );
}

#[test]
fn missing_named_uv_does_not_generate_or_fallback() {
    code(
        changed(
            |s| {
                s["mesh_assets"]["mesh_mesh"]["polygons"]["p0001"]["uv_layers"] = json!({});
            },
            |_| {},
        ),
        ErrorCode::MissingUv,
    );
    code(
        changed(
            |_| {},
            |p| p["bindings"]["fixture_white"]["uv_layer"] = json!("missing"),
        ),
        ErrorCode::MissingUv,
    );
}

#[test]
fn native_validation_rejects_bad_corner_count_and_references() {
    code(
        changed(
            |s| {
                s["mesh_assets"]["mesh_mesh"]["polygons"]["p0001"]["uv_layers"]["uv0"] =
                    json!([[0, 0]])
            },
            |_| {},
        ),
        ErrorCode::InvalidScene,
    );
    code(
        changed(
            |s| {
                s["mesh_assets"]["mesh_mesh"]["polygons"]["p0001"]["vertices"][0] = json!("missing")
            },
            |_| {},
        ),
        ErrorCode::InvalidScene,
    );
    code(
        changed(|s| s["unknown_field"] = json!(true), |_| {}),
        ErrorCode::InvalidScene,
    );
}

#[test]
fn complete_closure_rejects_extra_entity_asset_or_material() {
    for which in ["entity", "mesh", "material"] {
        code(
            changed(
                |s| match which {
                    "entity" => s["entities"]["extra"] = s["entities"]["uv_panel"].clone(),
                    "mesh" => s["mesh_assets"]["extra"] = s["mesh_assets"]["mesh_mesh"].clone(),
                    _ => s["materials"]["extra"] = s["materials"]["fixture_white"].clone(),
                },
                |_| {},
            ),
            ErrorCode::ClosureMismatch,
        );
    }
}

#[test]
fn producer_profile_and_sampling_declarations_are_not_guessed() {
    code(
        changed(
            |_| {},
            |p| p["producer_commit"] = json!(crate::model_package::PRODUCER),
        ),
        ErrorCode::UnsupportedProducer,
    );
    code(
        changed(
            |_| {},
            |p| p["scene_profile"] = json!(crate::model_package::PROFILE),
        ),
        ErrorCode::UnsupportedProfile,
    );
    for (map, key, value) in [
        ("images", "color_space", "linear"),
        ("bindings", "filter", "bilinear"),
        ("bindings", "address_mode", "repeat"),
    ] {
        let id = if map == "images" {
            "four"
        } else {
            "fixture_white"
        };
        let expected = if map == "images" {
            ErrorCode::InvalidProject
        } else {
            ErrorCode::InvalidBinding
        };
        code(
            changed(|_| {}, |p| p[map][id][key] = json!(value)),
            expected,
        );
    }
}

#[test]
fn portable_paths_reject_absolute_traversal_windows_forms_and_reserved_descriptor() {
    for name in [
        "",
        "/tmp/x",
        "../x",
        "x/../y",
        "x/./y",
        "x//y",
        "C:/x",
        "C:\\x",
        "\\\\server\\x",
        "project.json",
        "x\0y",
    ] {
        assert!(resource_path(name).is_err(), "{name:?}");
    }
    assert!(resource_path("images/base-color.png").is_ok());
}

#[test]
fn bad_sample_or_unbound_face_never_returns_partial_success() {
    let p = validate_bytes(PROJECT, &sha256(PROJECT), &files()).unwrap();
    assert!(p.samples(&[]).is_err());
    assert_eq!(
        p.samples(&[query([f64::NAN, 0.0])]).unwrap_err().code,
        ErrorCode::InvalidSample
    );
    let mut q = query([0.0, 0.0]);
    q.face = Face::Polygon {
        id: "missing".into(),
    };
    assert_eq!(
        p.samples(&[query([0.25, 0.25]), q]).unwrap_err().code,
        ErrorCode::InvalidSample
    );
}

#[test]
fn native_source_values_context_and_unused_vertices_stay_in_raw_bytes() {
    let p = changed(
        |s| {
            s["revision"] = json!(u64::MAX);
            s["mesh_assets"]["mesh_mesh"]["recipe"] =
                json!({"primitive":{"kind":"cube","size":1.0},"max_components":1000,"edited":true});
            s["mesh_assets"]["mesh_mesh"]["vertices"]["unused"] =
                json!([-0.0, 1.0000000000000002, 0.0]);
        },
        |_| {},
    )
    .unwrap();
    assert_eq!(p.scene.revision, u64::MAX);
    assert!(p.scene.mesh_assets["mesh_mesh"].recipe.is_some());
    assert_eq!(
        p.scene.mesh_assets["mesh_mesh"].vertices["unused"][0].to_bits(),
        (-0.0f64).to_bits()
    );
    assert_eq!(
        p.scene.mesh_assets["mesh_mesh"].vertices["unused"][1].to_bits(),
        1.0000000000000002f64.to_bits()
    );
    assert!(
        p.scene.mesh_assets["mesh_mesh"].polygons["p0001"]
            .corner_normals
            .is_none()
    );
}

#[test]
fn malformed_duplicate_and_unknown_project_fields_are_rejected() {
    for bytes in [
        b"not JSON".as_slice(),
        br#"{"project_schema_version":1,"project_schema_version":1}"#,
    ] {
        code(
            validate_bytes(bytes, &sha256(bytes), &files()),
            ErrorCode::InvalidProject,
        );
    }
    code(
        changed(|_| {}, |p| p["new_field"] = json!(true)),
        ErrorCode::InvalidProject,
    );
}

#[test]
fn malformed_png_and_transparency_formats_do_not_return_fallback_pixels() {
    assert_eq!(
        image::Image::decode(b"not PNG").err().unwrap().code,
        ErrorCode::InvalidImage
    );
    assert!(image::Image::decode(&PNG[..PNG.len() - 8]).is_err());
    let mut bytes = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut bytes, 1, 1);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().unwrap();
        writer.write_image_data(&[128, 128, 128, 128]).unwrap();
    }
    assert_eq!(
        image::Image::decode(&bytes).err().unwrap().code,
        ErrorCode::UnsupportedImage
    );
}

#[test]
fn entity_material_overrides_slots_and_all_unused_slots_are_kept() {
    let p = changed(
        |s| {
            s["materials"]["slot_mat"] = s["materials"]["fixture_white"].clone();
            s["mesh_assets"]["mesh_mesh"]["material_slots"] = json!(["fixture_white", "slot_mat"]);
            for f in s["mesh_assets"]["mesh_mesh"]["polygons"]
                .as_object_mut()
                .unwrap()
                .values_mut()
            {
                f["material_slot"] = json!(1);
            }
        },
        |_| {},
    )
    .unwrap();
    assert_eq!(
        p.samples(&[query([0.25, 0.25])]).unwrap().samples[0].material,
        "fixture_white"
    );
    assert_eq!(p.scene.mesh_assets["mesh_mesh"].material_slots.len(), 2);
}

#[test]
fn duplicate_request_keys_fail_before_any_operation() {
    let receipt = request_json(
        "inspect",
        br#"{"project":"x","project":"y","expected_project_sha256":"bad"}"#,
    );
    match receipt {
        Receipt::Failure(e) => assert_eq!(e.code, ErrorCode::InvalidRequest),
        _ => panic!(),
    }
}

#[test]
fn failure_receipts_exclude_all_success_fields_even_when_null() {
    let mut value =
        serde_json::to_value(Failure::new(ErrorCode::ImageMissing, "image", "missing")).unwrap();
    value["saved_location"] = Value::Null;
    assert!(serde_json::from_value::<Receipt>(value).is_err());
}

#[test]
fn compiled_compatibility_source_matches_every_pinned_upstream_hash() {
    let provenance: Value =
        serde_json::from_str(include_str!("../../compat/bb025/PROVENANCE.json")).unwrap();
    assert_eq!(provenance["upstream_commit"], PRODUCER);
    let mut count = 0;
    for (name, bytes) in NATIVE_INPUTS {
        let expected = match *name {
            "Cargo.toml" => &provenance["wrapper_cargo_sha256"],
            "Cargo.upstream.toml" => &provenance["upstream_cargo_sha256"],
            _ => {
                count += 1;
                &provenance["upstream_source_files"][*name]
            }
        };
        assert_eq!(sha256(bytes), expected.as_str().unwrap(), "{name}");
    }
    assert_eq!(count, 54);
}

#[test]
fn export_schemas() {
    println!("MATERIAL_SCHEMAS_BEGIN{}MATERIAL_SCHEMAS_END", schemas());
}

#[test]
fn frozen_schema_bundle_matches_the_implemented_contract() {
    let frozen: Value = serde_json::from_str(include_str!(
        "../../schemas/material-project/contracts.json"
    ))
    .unwrap();
    assert_eq!(schemas(), frozen);
}

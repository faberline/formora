use super::*;
use serde_json::{Value, json};

fn scene() -> Value {
    let transform =
        json!({"translation":[1.2345678901234567,-0.0,0.0],"rotation":[0,0,0,1],"scale":[1,1,1]});
    json!({"schema_version":1,"revision":0,"time_seconds":-0.0,
        "entities":{
            "root":{"name":"source root","parent":null,"transform":transform,"content":{"kind":"empty"}},
            "part":{"name":"source part","parent":"root","transform":{"translation":[0,0,0],"rotation":[0,0,0,1],"scale":[1,1,1]},"content":{"kind":"mesh","geometry":{"kind":"asset","id":"mesh"},"material":"mat"}}
        },
        "mesh_assets":{"mesh":{"vertices":{"a":[0,0,0],"b":[1,0,0],"c":[0,1,0],"unused":[-0.0,1.0000000000000002,0]},"triangles":{"face":{"vertices":["a","b","c"],"uv_layers":{},"corner_normals":null,"material_slot":0}},"material_slots":["mat","slot_only"]}},
        "materials":{"mat":{"base_color":[0.3,0.4,0.5,1],"roughness":0.7,"metallic":0},"slot_only":{"base_color":[0.1,0.2,0.3,1],"roughness":0.5,"metallic":0}},
        "doors":{},"active_camera":null,"annotations":[]})
}

fn manifest(scene_bytes: &[u8]) -> Value {
    json!({"manifest_schema_version":1,"scene_file":"model.scene.json","scene_sha256":sha256(scene_bytes),"scene_schema_version":1,
        "scene_profile":PROFILE,"producer_commit":PRODUCER,"roots":["root"],"meters_per_unit":1.0,"up_axis":"Z","coordinate_system":"right_handed",
        "capabilities":["triangle_meshes","hierarchy","solid_color_materials"],"display_exports":[]})
}

fn validate(scene: &Value, change: impl FnOnce(&mut Value)) -> Result<PreparedPackage, Failure> {
    let source = serde_json::to_vec(scene).unwrap();
    let mut m = manifest(&source);
    change(&mut m);
    let bytes = serde_json::to_vec(&m).unwrap();
    validate_bytes(&bytes, &sha256(&bytes), &source)
}

fn failure(error: Failure, code: ErrorCode) {
    assert_eq!(error.error.code, code);
    let result = serde_json::to_value(Receipt::Failed(error)).unwrap();
    assert_eq!(result["ok"], false);
    for key in [
        "scene_profile",
        "producer_commit",
        "roots",
        "scene_sha256",
        "saved_location",
        "counts",
    ] {
        assert!(
            result.get(key).is_none(),
            "Failure must not adopt or validate {key}"
        );
    }
}

#[test]
fn preserves_source_bytes_signed_zero_unused_vertices_and_all_slots() {
    let mut source = scene();
    source["revision"] = json!(u64::MAX);
    let bytes = serde_json::to_vec(&source).unwrap();
    let manifest = serde_json::to_vec(&manifest(&bytes)).unwrap();
    let package = validate_bytes(&manifest, &sha256(&manifest), &bytes).unwrap();
    assert_eq!(package.scene_bytes, bytes);
    assert_eq!(package.manifest_bytes, manifest);
    assert_eq!(
        package.counts,
        Counts {
            entities: 2,
            mesh_assets: 1,
            vertices: 4,
            triangles: 1,
            materials: 2
        }
    );
    let decoded: crate::scene::Scene = serde_json::from_slice(&package.scene_bytes).unwrap();
    assert_eq!(decoded.revision, u64::MAX);
    assert_eq!(
        decoded.entities["root"].transform.translation[1].to_bits(),
        (-0.0f64).to_bits()
    );
    assert_eq!(
        decoded.mesh_assets["mesh"].vertices["unused"][0].to_bits(),
        (-0.0f64).to_bits()
    );
    assert_eq!(
        decoded.mesh_assets["mesh"].vertices["unused"][1].to_bits(),
        1.0000000000000002f64.to_bits()
    );
    assert_eq!(
        decoded.mesh_assets["mesh"].triangles["face"].corner_normals,
        None
    );
}

#[test]
fn multiple_roots_share_resources_and_keep_manifest_order() {
    let mut source = scene();
    let mut extra = source["entities"]["part"].clone();
    extra["parent"] = Value::Null;
    source["entities"]["other"] = extra;
    let package = validate(&source, |m| m["roots"] = json!(["other", "root"])).unwrap();
    assert_eq!(package.manifest.roots, ["other", "root"]);
    assert_eq!(package.counts.entities, 3);
    assert_eq!(package.counts.mesh_assets, 1);
}

#[test]
fn manifest_hash_binds_units_and_roots_before_source_validation() {
    let source = serde_json::to_vec(&scene()).unwrap();
    let original = manifest(&source);
    let original_bytes = serde_json::to_vec(&original).unwrap();
    for (key, value) in [("meters_per_unit", json!(2)), ("roots", json!(["other"]))] {
        let mut changed = original.clone();
        changed[key] = value;
        let bytes = serde_json::to_vec(&changed).unwrap();
        let error = validate_bytes(
            &bytes,
            &sha256(&original_bytes),
            b"source must not be parsed",
        )
        .unwrap_err();
        assert_eq!(error.error.stage, Stage::ManifestHash);
        assert!(error.observed_scene_sha256.is_none());
        failure(error, ErrorCode::HashMismatch);
    }
}

#[test]
fn manifest_parse_and_duplicate_keys_never_claim_validated_data() {
    for bytes in [
        b"not json".as_slice(),
        br#"{"manifest_schema_version":1,"manifest_schema_version":1}"#.as_slice(),
    ] {
        let error = validate_bytes(bytes, &sha256(bytes), b"unread").unwrap_err();
        assert!(error.observed_scene_sha256.is_none());
        failure(error, ErrorCode::InvalidManifest);
    }
}

#[test]
fn rejects_version_profile_producer_units_and_path_substitution() {
    for (key, value, code) in [
        (
            "manifest_schema_version",
            json!(2),
            ErrorCode::UnsupportedSchema,
        ),
        (
            "scene_schema_version",
            json!(2),
            ErrorCode::UnsupportedSchema,
        ),
        (
            "scene_profile",
            json!("formora-d25"),
            ErrorCode::UnsupportedProfile,
        ),
        (
            "producer_commit",
            json!("d25a2a7ed7c16fa8d61f70e9c2f65926e962303d"),
            ErrorCode::UnsupportedProducer,
        ),
        (
            "producer_commit",
            json!("bb025ce17432ba0419008d0cd794222127e7ff92"),
            ErrorCode::UnsupportedProducer,
        ),
        ("meters_per_unit", json!(0.5), ErrorCode::UnsupportedUnits),
        ("up_axis", json!("Y"), ErrorCode::UnsupportedUnits),
        (
            "coordinate_system",
            json!("left_handed"),
            ErrorCode::UnsupportedUnits,
        ),
        (
            "scene_file",
            json!("../outside.json"),
            ErrorCode::InvalidManifest,
        ),
        (
            "scene_file",
            json!("/absolute.json"),
            ErrorCode::InvalidManifest,
        ),
        ("unknown_field", json!(true), ErrorCode::InvalidManifest),
    ] {
        failure(validate(&scene(), |m| m[key] = value).unwrap_err(), code);
    }
}

#[test]
fn rejects_scene_hash_change_without_trusting_scene_values() {
    let source = serde_json::to_vec(&scene()).unwrap();
    let bytes = serde_json::to_vec(&manifest(&source)).unwrap();
    failure(
        validate_bytes(&bytes, &sha256(&bytes), b"different bytes").unwrap_err(),
        ErrorCode::HashMismatch,
    );
}

#[test]
fn rejects_invalid_roots_extra_entities_and_unused_resources() {
    for roots in [
        json!([]),
        json!(["root", "root"]),
        json!(["missing"]),
        json!(["part"]),
    ] {
        failure(
            validate(&scene(), |m| m["roots"] = roots).unwrap_err(),
            ErrorCode::InvalidRoots,
        );
    }
    let mut source = scene();
    source["entities"]["unselected"] = source["entities"]["root"].clone();
    failure(
        validate(&source, |_| {}).unwrap_err(),
        ErrorCode::ClosureMismatch,
    );
    let mut source = scene();
    source["mesh_assets"]["unused"] = source["mesh_assets"]["mesh"].clone();
    failure(
        validate(&source, |_| {}).unwrap_err(),
        ErrorCode::ClosureMismatch,
    );
    let mut source = scene();
    source["materials"]["unused"] = source["materials"]["mat"].clone();
    failure(
        validate(&source, |_| {}).unwrap_err(),
        ErrorCode::ClosureMismatch,
    );
}

#[test]
fn rejects_missing_references_and_cyclic_hierarchy() {
    for source in [
        {
            let mut s = scene();
            s["entities"]["part"]["content"]["geometry"]["id"] = json!("missing");
            s
        },
        {
            let mut s = scene();
            s["entities"]["part"]["content"]["material"] = json!("missing");
            s
        },
        {
            let mut s = scene();
            s["entities"]["root"]["parent"] = json!("part");
            s
        },
        {
            let mut s = scene();
            s["mesh_assets"]["mesh"]["triangles"]["face"]["vertices"] =
                json!(["a", "b", "missing"]);
            s
        },
    ] {
        failure(
            validate(&source, |_| {}).unwrap_err(),
            ErrorCode::InvalidScene,
        );
    }
}

#[test]
fn rejects_d25_attributes_instead_of_dropping_them() {
    for source in [
        {
            let mut s = scene();
            s["mesh_assets"]["mesh"]["triangles"]["face"]["corner_colors"] =
                json!([[1, 0, 0, 1], [1, 0, 0, 1], [1, 0, 0, 1]]);
            s
        },
        {
            let mut s = scene();
            s["mesh_assets"]["mesh"]["polygons"] = json!({});
            s
        },
        {
            let mut s = scene();
            s["authoring_context"] = Value::Null;
            s
        },
    ] {
        failure(
            validate(&source, |_| {}).unwrap_err(),
            ErrorCode::InvalidScene,
        );
    }
}

#[test]
fn rejects_scene_state_and_non_asset_geometry() {
    let mut source = scene();
    source["annotations"] =
        json!([{"entity":"root","position":[0,0,0],"text":"keep this, never drop it"}]);
    failure(
        validate(&source, |_| {}).unwrap_err(),
        ErrorCode::UnsupportedSceneState,
    );
    let mut source = scene();
    source["time_seconds"] = json!(1);
    failure(
        validate(&source, |_| {}).unwrap_err(),
        ErrorCode::UnsupportedSceneState,
    );
    let mut source = scene();
    source["entities"]["part"]["content"]["geometry"] = json!({"kind":"cube","size":[1,1,1]});
    failure(
        validate(&source, |_| {}).unwrap_err(),
        ErrorCode::UnsupportedFeature,
    );
}

#[test]
fn checks_capabilities_against_actual_corner_data() {
    let mut source = scene();
    source["mesh_assets"]["mesh"]["triangles"]["face"]["uv_layers"] =
        json!({"uv":[[0,0],[1,0],[0,1]]});
    source["mesh_assets"]["mesh"]["triangles"]["face"]["corner_normals"] =
        json!([[0, 0, 1], [0, 0, 1], [0, 0, 1]]);
    failure(
        validate(&source, |_| {}).unwrap_err(),
        ErrorCode::UnsupportedFeature,
    );
    let good = validate(&source, |m| {
        m["capabilities"] = json!([
            "triangle_meshes",
            "hierarchy",
            "corner_uvs",
            "corner_normals",
            "solid_color_materials"
        ])
    })
    .unwrap();
    assert_eq!(good.scene_bytes, serde_json::to_vec(&source).unwrap());
    failure(
        validate(&scene(), |m| {
            m["capabilities"] = json!([
                "triangle_meshes",
                "hierarchy",
                "hierarchy",
                "solid_color_materials"
            ])
        })
        .unwrap_err(),
        ErrorCode::InvalidManifest,
    );
    failure(
        validate(&scene(), |m| {
            m["capabilities"] = json!(["triangle_meshes", "textures"])
        })
        .unwrap_err(),
        ErrorCode::InvalidManifest,
    );
}

#[test]
fn optional_display_export_is_explicitly_unimplemented() {
    failure(validate(&scene(),|m|m["display_exports"]=json!([{"format":"usda","relative_path":"model.usda","sha256":"0".repeat(64),"scope":"static"}])).unwrap_err(),ErrorCode::UnsupportedFeature);
}

#[test]
fn failure_receipt_type_cannot_contain_validated_success_fields() {
    let error = Failure::new(ErrorCode::ManifestMissing, Stage::ReadManifest, "missing");
    let mut value = serde_json::to_value(Receipt::Failed(error)).unwrap();
    value["scene_profile"] = json!(PROFILE);
    assert!(serde_json::from_value::<Receipt>(value).is_err());
    assert!(serde_json::from_str::<Flag<true>>("false").is_err());
    assert!(serde_json::from_str::<Flag<false>>("true").is_err());
}

#[test]
fn contract_schema_export() {
    let schemas = schemas();
    assert_eq!(
        schemas["manifest"]["properties"]["scene_file"]["const"],
        "model.scene.json"
    );
    println!("SCHEMAS_BEGIN{}SCHEMAS_END", schemas);
}

#[test]
fn schema_snapshots_match_the_public_contract() {
    let schemas = schemas();
    for (key, bytes) in [
        (
            "manifest",
            include_str!("../../schemas/model-package/manifest.schema.json"),
        ),
        (
            "import_request",
            include_str!("../../schemas/model-package/import-request.schema.json"),
        ),
        (
            "receipt",
            include_str!("../../schemas/model-package/receipt.schema.json"),
        ),
    ] {
        assert_eq!(
            schemas[key],
            serde_json::from_str::<Value>(bytes).unwrap(),
            "Schema changes need an explicit contract update: {key}"
        );
    }
}

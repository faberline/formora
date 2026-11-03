use super::*;
use schemars::JsonSchema;
use serde_json::{Value, json};
use std::collections::BTreeMap;

/// Shape of the complete pinned native scene. Native Scene::validate supplies
/// reference, topology, context, numeric and attribute checks after deserialization.
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
#[allow(dead_code)]
struct NativeSource {
    schema_version: u32,
    revision: u64,
    time_seconds: f64,
    entities: BTreeMap<String, formora_native_bb025::scene::Entity>,
    materials: BTreeMap<String, formora_native_bb025::scene::Material>,
    #[serde(default)]
    mesh_assets: BTreeMap<String, formora_native_bb025::mesh::MeshAsset>,
    doors: BTreeMap<String, Value>,
    active_camera: Option<String>,
    annotations: Vec<formora_native_bb025::scene::Annotation>,
    #[serde(default)]
    authoring_context: Option<formora_native_bb025::mesh::creation::AuthoringContext>,
    #[serde(default)]
    object_context: Option<formora_native_bb025::objects::Context>,
}

pub fn schemas() -> Value {
    let mut project = json!(schemars::schema_for!(Project));
    for (field, value) in [
        ("project_schema_version", json!(1)),
        ("project_profile", json!(PROJECT_PROFILE)),
        ("scene_profile", json!(SOURCE_PROFILE)),
        ("producer_commit", json!(PRODUCER)),
    ] {
        project["properties"][field]["const"] = value;
    }
    project["properties"]["roots"]["minItems"] = json!(1);
    project["properties"]["roots"]["uniqueItems"] = json!(true);
    for map in ["images", "bindings"] {
        project["properties"][map]["minProperties"] = json!(1);
    }
    for name in ["Resource", "ImageResource"] {
        project["$defs"][name]["properties"]["sha256"]["pattern"] = json!("^[0-9a-f]{64}$");
    }
    project["$defs"]["ImageResource"]["properties"]["color_space"]["const"] = json!("srgb");
    project["$defs"]["Binding"]["properties"]["filter"]["const"] = json!("nearest");
    project["$defs"]["Binding"]["properties"]["address_mode"]["const"] = json!("clamp_to_edge");
    let mut source = json!(schemars::schema_for!(NativeSource));
    source["properties"]["schema_version"]["const"] = json!(1);
    source["properties"]["time_seconds"]["const"] = json!(0.0);
    source["properties"]["doors"]["maxProperties"] = json!(0);
    source["properties"]["active_camera"]["const"] = Value::Null;
    source["properties"]["annotations"]["maxItems"] = json!(0);
    for (name, allowed) in [
        ("EntityKind", &["empty", "mesh"][..]),
        ("Geometry", &["asset"][..]),
    ] {
        if let Some(variants) = source["$defs"][name]["oneOf"].as_array_mut() {
            variants.retain(|v| {
                v["properties"]["kind"]["const"]
                    .as_str()
                    .is_some_and(|kind| allowed.contains(&kind))
            });
        }
    }
    let mut receipt = json!(schemars::schema_for!(Receipt));
    for name in ["Success", "Failure"] {
        receipt["$defs"][name]["properties"]["receipt_schema_version"]["const"] = json!(1);
    }
    for (field, value) in [
        ("project_profile", json!(PROJECT_PROFILE)),
        ("scene_profile", json!(SOURCE_PROFILE)),
        ("producer_commit", json!(PRODUCER)),
    ] {
        receipt["$defs"]["Success"]["properties"][field]["const"] = value;
    }
    for field in ["project_sha256", "scene_sha256"] {
        receipt["$defs"]["Success"]["properties"][field]["pattern"] = json!("^[0-9a-f]{64}$");
    }
    receipt["$defs"]["Success"]["properties"]["validator_revision"]["pattern"] =
        json!("^sha256:[0-9a-f]{64}$");
    receipt["$defs"]["Success"]["allOf"] = json!([
        {"if":{"properties":{"operation":{"const":"import"}}},"then":{"required":["saved_location"],"properties":{"saved_location":{"type":"string","minLength":1}}},"else":{"not":{"required":["saved_location"]}}}
    ]);
    receipt["$defs"]["ImageInfo"]["properties"]["sha256"]["pattern"] = json!("^[0-9a-f]{64}$");
    receipt["$defs"]["ImageInfo"]["properties"]["color_space"]["const"] = json!("srgb");
    for field in ["width", "height"] {
        receipt["$defs"]["ImageInfo"]["properties"][field]["minimum"] = json!(1);
    }
    let mut result = json!({"project":project,"source":source,"inspect_request":schemars::schema_for!(InspectRequest),"sample_request":schemars::schema_for!(SampleRequest),"import_request":schemars::schema_for!(ImportRequest),"receipt":receipt});
    for name in ["inspect_request", "sample_request", "import_request"] {
        result[name]["properties"]["expected_project_sha256"]["pattern"] = json!("^[0-9a-f]{64}$");
        result[name]["properties"]["project"]["minLength"] = json!(1);
    }
    result["sample_request"]["properties"]["samples"]["minItems"] = json!(1);
    result["import_request"]["properties"]["output"]["minLength"] = json!(1);
    result
}

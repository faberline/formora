//! CPU model package validation. Import writes a new model directory, never a game save.
mod storage;
mod types;
mod validate;

pub use storage::import;
pub use types::*;
pub use validate::{PreparedPackage, validate_bytes};

use serde_json::{Value, json};
use sha2::{Digest, Sha256};

pub const PROFILE: &str = "formora-static-triangles-main-v1";
pub const PRODUCER: &str = "5761e683b01bb82e5efc3cfc931e40a3cc55a8c2";

pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn valid_hash(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

/// Identifies the source contract used by this binary, including the core parser.
/// This is deliberately not presented as a Git or reproducible-build attestation.
pub fn validator_revision() -> String {
    let mut digest = Sha256::new();
    for (name, bytes) in [
        ("mod.rs", include_str!("mod.rs")),
        ("types.rs", include_str!("types.rs")),
        ("validate.rs", include_str!("validate.rs")),
        ("storage.rs", include_str!("storage.rs")),
        ("json.rs", include_str!("../json.rs")),
        ("scene.rs", include_str!("../scene.rs")),
        ("mesh.rs", include_str!("../mesh.rs")),
        ("lib.rs", include_str!("../lib.rs")),
        ("main.rs", include_str!("../main.rs")),
        ("agent.rs", include_str!("../agent.rs")),
        ("Cargo.toml", include_str!("../../Cargo.toml")),
        ("Cargo.lock", include_str!("../../Cargo.lock")),
    ] {
        digest.update(name.as_bytes());
        digest.update([0]);
        digest.update((bytes.len() as u64).to_le_bytes());
        digest.update(bytes.as_bytes());
    }
    format!("sha256:{:x}", digest.finalize())
}

pub fn schemas() -> Value {
    let mut manifest = json!(schemars::schema_for!(Manifest));
    for (field, value) in [
        ("manifest_schema_version", json!(1)),
        ("scene_schema_version", json!(1)),
        ("scene_file", json!("model.scene.json")),
        ("scene_profile", json!(PROFILE)),
        ("producer_commit", json!(PRODUCER)),
        ("meters_per_unit", json!(1.0)),
        ("up_axis", json!("Z")),
        ("coordinate_system", json!("right_handed")),
    ] {
        manifest["properties"][field]["const"] = value;
    }
    manifest["properties"]["scene_sha256"]["pattern"] = json!("^[0-9a-f]{64}$");
    for field in ["roots", "capabilities"] {
        manifest["properties"][field]["minItems"] = json!(1);
        manifest["properties"][field]["uniqueItems"] = json!(true);
    }
    manifest["properties"]["display_exports"]["maxItems"] = json!(0);
    manifest["properties"]["capabilities"]["contains"] = json!({"const":"triangle_meshes"});
    let mut receipt = json!(schemars::schema_for!(Receipt));
    for name in ["Imported", "Failure"] {
        receipt["$defs"][name]["properties"]["receipt_schema_version"]["const"] = json!(1);
    }
    let success = &mut receipt["$defs"]["Imported"]["properties"];
    for (field, value) in [
        ("scene_profile", json!(PROFILE)),
        ("producer_commit", json!(PRODUCER)),
        ("meters_per_unit", json!(1.0)),
        ("up_axis", json!("Z")),
        ("coordinate_system", json!("right_handed")),
    ] {
        success[field]["const"] = value;
    }
    for field in ["manifest_sha256", "scene_sha256"] {
        success[field]["pattern"] = json!("^[0-9a-f]{64}$");
    }
    success["validator_revision"]["pattern"] = json!("^sha256:[0-9a-f]{64}$");
    success["roots"]["minItems"] = json!(1);
    success["roots"]["uniqueItems"] = json!(true);
    for field in ["conversion_report", "loss_report"] {
        success[field]["maxItems"] = json!(0);
    }
    let mut request = json!(schemars::schema_for!(ImportRequest));
    request["properties"]["expected_manifest_sha256"]["pattern"] = json!("^[0-9a-f]{64}$");
    for field in ["manifest", "output"] {
        request["properties"][field]["minLength"] = json!(1);
    }
    json!({"manifest":manifest,"import_request":request,"receipt":receipt})
}

#[cfg(test)]
mod tests;

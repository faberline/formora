//! CPU texture projects. Native polygon source and image bytes remain unchanged.
mod image;
mod schema;
mod storage;
mod types;
mod validate;

pub use schema::schemas;
pub use storage::{import, inspect, sample};
pub use types::*;
pub use validate::{PreparedProject, validate_bytes};

use crate::model_package::{Flag, sha256};
use sha2::{Digest, Sha256};

pub const PRODUCER: &str = "bb025ce17432ba0419008d0cd794222127e7ff92";
pub const SOURCE_PROFILE: &str = "formora-static-polygons-bb025-v1";
pub const PROJECT_PROFILE: &str = "formora-base-color-image-v1";

pub fn invalid_request(message: impl ToString) -> Receipt {
    Receipt::Failure(Failure::new(ErrorCode::InvalidRequest, "request", message))
}

/// CLI JSON input uses the same typed operation core as MCP. Duplicate keys fail.
pub fn request_json(action: &str, bytes: &[u8]) -> Receipt {
    fn parse<T: serde::de::DeserializeOwned>(bytes: &[u8]) -> Result<T, String> {
        serde_json::from_value(crate::json::value_from_slice(bytes).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())
    }
    match action {
        "inspect" => parse(bytes).map(inspect).unwrap_or_else(invalid_request),
        "sample" => parse(bytes).map(sample).unwrap_or_else(invalid_request),
        "import" => parse(bytes).map(import).unwrap_or_else(invalid_request),
        _ => invalid_request("Unknown material operation"),
    }
}

include!("../../compat/bb025/source_inputs.rs");

pub fn validator_revision() -> String {
    let mut digest = Sha256::new();
    for (name, bytes) in NATIVE_INPUTS.iter().copied().chain([
        ("material/mod.rs", include_bytes!("mod.rs").as_slice()),
        ("material/types.rs", include_bytes!("types.rs").as_slice()),
        ("material/image.rs", include_bytes!("image.rs").as_slice()),
        (
            "material/validate.rs",
            include_bytes!("validate.rs").as_slice(),
        ),
        (
            "material/storage.rs",
            include_bytes!("storage.rs").as_slice(),
        ),
        ("material/schema.rs", include_bytes!("schema.rs").as_slice()),
        ("main.rs", include_bytes!("../main.rs").as_slice()),
        ("agent.rs", include_bytes!("../agent.rs").as_slice()),
        ("lib.rs", include_bytes!("../lib.rs").as_slice()),
        (
            "model_flags.rs",
            include_bytes!("../model_package/types.rs").as_slice(),
        ),
        (
            "native_source_inputs.rs",
            include_bytes!("../../compat/bb025/source_inputs.rs").as_slice(),
        ),
        ("json.rs", include_bytes!("../json.rs").as_slice()),
        ("Cargo.toml", include_bytes!("../../Cargo.toml").as_slice()),
        ("Cargo.lock", include_bytes!("../../Cargo.lock").as_slice()),
    ]) {
        digest.update(name.as_bytes());
        digest.update([0]);
        digest.update((bytes.len() as u64).to_le_bytes());
        digest.update(bytes);
    }
    format!("sha256:{:x}", digest.finalize())
}

fn valid_hash(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}

fn resource_path(s: &str) -> Result<(), Failure> {
    if s.is_empty()
        || s.contains(['\\', ':', '\0'])
        || s.split('/')
            .any(|part| part.is_empty() || part == "." || part == "..")
        || s == "project.json"
    {
        Err(Failure::new(
            ErrorCode::InvalidPath,
            "project",
            "Resources must use portable project-relative file paths, distinct from project.json",
        ))
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests;

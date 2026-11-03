use sha2::{Digest, Sha256};
use std::{fs, path::Path};
fn main() {
    let here = Path::new(env!("CARGO_MANIFEST_DIR"));
    let data = fs::read(here.join("engine-identity.json")).expect("engine identity");
    let identity: serde_json::Value = serde_json::from_slice(&data).expect("identity JSON");
    let files = identity["files"].as_object().expect("files");
    assert_eq!(files.len(), 99);
    let documentation = identity.get("documentation_overrides").map(|value| {
        let overrides = value.as_object().expect("documentation overrides");
        assert_eq!(overrides.len(), 3);
        for (name, change) in overrides {
            assert!(
                [
                    "docs/preview.md",
                    "docs/renderer-api.md",
                    "docs/renderer-layers.md"
                ]
                .contains(&name.as_str()),
                "undeclared documentation path: {name}"
            );
            assert_eq!(change["base_sha256"], files[name]);
            let digest = change["sha256"].as_str().expect("documentation hash");
            assert_eq!(digest.len(), 64);
            assert!(digest.bytes().all(|b| b.is_ascii_hexdigit()));
        }
        overrides
    });
    for (name, expected) in files {
        let expected = documentation
            .and_then(|changes| changes.get(name))
            .map_or(expected, |change| &change["sha256"]);
        let path = here.join("../..").join(name);
        println!("cargo:rerun-if-changed={}", path.display());
        let bytes = fs::read(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        assert_eq!(
            format!("{:x}", Sha256::digest(bytes)),
            expected.as_str().unwrap(),
            "frozen d25 file or explicit documentation overlay changed: {name}"
        );
    }
    println!("cargo:rerun-if-changed=engine-identity.json");
}

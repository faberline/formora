use sha2::{Digest, Sha256};
use std::{fs, path::Path};
fn main() {
    let here = Path::new(env!("CARGO_MANIFEST_DIR"));
    let data = fs::read(here.join("engine-identity.json")).expect("engine identity");
    let identity: serde_json::Value = serde_json::from_slice(&data).expect("identity JSON");
    let files = identity["files"].as_object().expect("files");
    assert_eq!(files.len(), 99);
    for (name, expected) in files {
        let path = here.join("../..").join(name);
        println!("cargo:rerun-if-changed={}", path.display());
        let bytes = fs::read(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        assert_eq!(
            format!("{:x}", Sha256::digest(bytes)),
            expected.as_str().unwrap(),
            "frozen d25 engine file changed: {name}"
        );
    }
    println!("cargo:rerun-if-changed=engine-identity.json");
}

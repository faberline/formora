//! Product subprocess and filesystem tests. Run in CI, not as local pure units.
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
    process::{Command, Output, Stdio},
    sync::atomic::{AtomicU64, Ordering},
};

static NEXT: AtomicU64 = AtomicU64::new(0);
struct Fixture {
    root: PathBuf,
    manifest: PathBuf,
    manifest_hash: String,
    source: Vec<u8>,
    manifest_bytes: Vec<u8>,
}

fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "formora-model-package-it-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&root).unwrap();
        let source=br#"{
          "schema_version":1,"revision":18446744073709551615,"time_seconds":-0.0,
          "entities":{"root":{"name":"External measured model","parent":null,"transform":{"translation":[-0.0,1.0000000000000002,0],"rotation":[0,0,0,1],"scale":[1,1,1]},"content":{"kind":"mesh","geometry":{"kind":"asset","id":"mesh"},"material":null}}},
          "mesh_assets":{"mesh":{"vertices":{"a":[-0.0,0,0],"b":[1,0,0],"c":[0,1,0],"unused":[2,2,2]},"triangles":{"face":{"vertices":["a","b","c"],"uv_layers":{},"corner_normals":null,"material_slot":null}},"material_slots":[]}},
          "materials":{},"doors":{},"active_camera":null,"annotations":[]
        }
        "#.to_vec();
        let manifest_value = json!({"manifest_schema_version":1,"scene_file":"model.scene.json","scene_sha256":hash(&source),"scene_schema_version":1,
            "scene_profile":"formora-static-triangles-main-v1","producer_commit":"5761e683b01bb82e5efc3cfc931e40a3cc55a8c2","roots":["root"],"meters_per_unit":1.0,"up_axis":"Z","coordinate_system":"right_handed","capabilities":["triangle_meshes"],"display_exports":[]});
        let manifest_bytes = serde_json::to_vec_pretty(&manifest_value).unwrap();
        let manifest = root.join("manifest.json");
        fs::write(&manifest, &manifest_bytes).unwrap();
        fs::write(root.join("model.scene.json"), &source).unwrap();
        fs::write(
            root.join("existing-game-save.json"),
            b"existing game data must remain unchanged",
        )
        .unwrap();
        Self {
            root,
            manifest,
            manifest_hash: hash(&manifest_bytes),
            source,
            manifest_bytes,
        }
    }
    fn import(&self, output: &Path, expected: &str) -> Output {
        Command::new(env!("CARGO_BIN_EXE_formora"))
            .args(["model", "import", "--manifest"])
            .arg(&self.manifest)
            .args(["--expected-manifest-sha256", expected, "--output"])
            .arg(output)
            .output()
            .unwrap()
    }
    fn unchanged(&self) {
        assert_eq!(
            fs::read(self.root.join("model.scene.json")).unwrap(),
            self.source
        );
        assert_eq!(
            fs::read(self.root.join("existing-game-save.json")).unwrap(),
            b"existing game data must remain unchanged"
        );
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.root).unwrap();
    }
}

fn receipt(output: &Output, ok: bool) -> Value {
    assert_eq!(
        output.status.success(),
        ok,
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stderr.is_empty());
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["ok"], ok);
    value
}

#[test]
fn cli_import_reopens_exact_source_and_rejects_existing_output() {
    let f = Fixture::new();
    let output = f.root.join("owned");
    let first = receipt(&f.import(&output, &f.manifest_hash), true);
    assert_eq!(first["manifest_sha256"], f.manifest_hash);
    assert_eq!(first["scene_sha256"], hash(&f.source));
    assert_eq!(first["roots"], json!(["root"]));
    assert_eq!(fs::read(output.join("model.scene.json")).unwrap(), f.source);
    assert_eq!(
        fs::read(output.join("manifest.json")).unwrap(),
        f.manifest_bytes
    );
    let reopened = formora::scene::Scene::load(&output.join("model.scene.json")).unwrap();
    assert_eq!(reopened.revision, u64::MAX);
    assert_eq!(
        reopened.entities["root"].transform.translation[0].to_bits(),
        (-0.0f64).to_bits()
    );
    assert_eq!(
        reopened.entities["root"].transform.translation[1].to_bits(),
        1.0000000000000002f64.to_bits()
    );
    assert_eq!(
        reopened.mesh_assets["mesh"].triangles["face"].corner_normals,
        None
    );
    assert_eq!(first["counts"]["vertices"], 4);
    let second = receipt(&f.import(&output, &f.manifest_hash), false);
    assert_eq!(second["error"]["code"], "output_exists");
    assert!(second.get("saved_location").is_none());
    assert_eq!(fs::read(output.join("model.scene.json")).unwrap(), f.source);
    f.unchanged();
}

#[test]
fn changed_manifest_cannot_reuse_scene_hash_to_adopt_new_units_or_roots() {
    let f = Fixture::new();
    for (i, key, value) in [
        (0, "meters_per_unit", json!(2)),
        (1, "roots", json!(["other"])),
    ] {
        let mut changed: Value = serde_json::from_slice(&f.manifest_bytes).unwrap();
        changed[key] = value;
        fs::write(&f.manifest, serde_json::to_vec(&changed).unwrap()).unwrap();
        let output = f.root.join(format!("rejected-{i}"));
        let result = receipt(&f.import(&output, &f.manifest_hash), false);
        assert_eq!(result["error"]["code"], "hash_mismatch");
        assert_eq!(result["error"]["stage"], "manifest_hash");
        for key in [
            "scene_profile",
            "roots",
            "scene_sha256",
            "saved_location",
            "producer_commit",
        ] {
            assert!(result.get(key).is_none());
        }
        assert!(!output.exists());
        f.unchanged();
    }
}

#[test]
fn missing_or_invalid_manifest_failure_never_claims_validated_values() {
    let f = Fixture::new();
    fs::remove_file(&f.manifest).unwrap();
    let output = f.root.join("missing");
    let result = receipt(&f.import(&output, &f.manifest_hash), false);
    assert_eq!(result["error"]["code"], "manifest_missing");
    assert!(result.get("observed_manifest_sha256").is_none());
    assert!(!output.exists());
    fs::write(&f.manifest, b"not JSON").unwrap();
    let result = receipt(&f.import(&output, &hash(b"not JSON")), false);
    assert_eq!(result["error"]["code"], "invalid_manifest");
    assert!(result.get("scene_profile").is_none());
    assert!(!output.exists());
    f.unchanged();
}

#[test]
fn schema_cli_returns_the_frozen_public_contracts() {
    let output = Command::new(env!("CARGO_BIN_EXE_formora"))
        .args(["model", "schema"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let actual: Value = serde_json::from_slice(&output.stdout).unwrap();
    for (key, expected) in [
        (
            "manifest",
            include_str!("../schemas/model-package/manifest.schema.json"),
        ),
        (
            "receipt",
            include_str!("../schemas/model-package/receipt.schema.json"),
        ),
        (
            "import_request",
            include_str!("../schemas/model-package/import-request.schema.json"),
        ),
    ] {
        assert_eq!(
            actual[key],
            serde_json::from_str::<Value>(expected).unwrap()
        );
    }
}

#[test]
fn mcp_uses_the_same_import_receipts_and_preserves_the_open_scene() {
    let f = Fixture::new();
    let game = f.root.join("game.scene.json");
    formora::scene::Scene::default().save(&game).unwrap();
    let before = fs::read(&game).unwrap();
    let output = f.root.join("mcp-owned");
    let params = |expected: &str| json!({"manifest":f.manifest,"expected_manifest_sha256":expected,"output":output});
    let requests = [
        json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"model-import-test","version":"1"}}}),
        json!({"jsonrpc":"2.0","method":"notifications/initialized"}),
        json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"model_import","arguments":params(&"0".repeat(64))}}),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"model_import","arguments":params(&f.manifest_hash)}}),
    ];
    let mut child = Command::new(env!("CARGO_BIN_EXE_formora"))
        .args(["mcp", "--scene"])
        .arg(&game)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    {
        let mut stdin = child.stdin.take().unwrap();
        for request in requests {
            writeln!(stdin, "{request}").unwrap();
        }
    }
    let response = child.wait_with_output().unwrap();
    assert!(response.status.success());
    assert!(response.stderr.is_empty());
    let values: Vec<Value> = String::from_utf8(response.stdout)
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(values.len(), 3);
    assert_eq!(values[1]["result"]["isError"], true);
    assert_eq!(values[1]["result"]["structuredContent"]["ok"], false);
    assert_eq!(values[2]["result"]["isError"], false);
    assert_eq!(values[2]["result"]["structuredContent"]["ok"], true);
    assert_eq!(fs::read(&game).unwrap(), before);
    assert_eq!(fs::read(output.join("model.scene.json")).unwrap(), f.source);
    f.unchanged();
}

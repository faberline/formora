//! Product CLI/MCP and filesystem tests. Run in normal CI, not as local pure units.
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::atomic::{AtomicU64, Ordering},
};

static NEXT: AtomicU64 = AtomicU64::new(0);
const SOURCE: &[u8] = include_bytes!("fixtures/texture/uv_panel.scene.json");
const PNG: &[u8] = include_bytes!("fixtures/texture/four-colors.png");
const PROJECT: &[u8] = include_bytes!("fixtures/texture/project.json");
fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

struct Fixture {
    root: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "formora-texture-it-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&root).unwrap();
        for (name, bytes) in [
            ("uv_panel.scene.json", SOURCE),
            ("four-colors.png", PNG),
            ("project.json", PROJECT),
            ("game-save.json", b"protected game save".as_slice()),
        ] {
            fs::write(root.join(name), bytes).unwrap();
        }
        Self { root }
    }
    fn request(&self) -> Value {
        json!({"project":self.root.join("project.json"),"expected_project_sha256":hash(&fs::read(self.root.join("project.json")).unwrap())})
    }
    fn sample_request(&self) -> Value {
        let mut r = self.request();
        r["samples"] = json!(
            [[0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]]
                .map(|uv| json!({"entity":"mesh","face":{"kind":"polygon","id":"p0001"},"uv":uv}))
        );
        r
    }
    fn edit_project(&self, edit: impl FnOnce(&mut Value)) {
        let mut p: Value =
            serde_json::from_slice(&fs::read(self.root.join("project.json")).unwrap()).unwrap();
        edit(&mut p);
        fs::write(
            self.root.join("project.json"),
            serde_json::to_vec(&p).unwrap(),
        )
        .unwrap();
    }
    fn protected(&self) {
        assert_eq!(
            fs::read(self.root.join("game-save.json")).unwrap(),
            b"protected game save"
        );
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.root).unwrap();
    }
}

fn cli_raw(action: &str, bytes: &[u8], cwd: Option<&Path>, ok: bool) -> Value {
    let mut command = Command::new(env!("CARGO_BIN_EXE_formora"));
    command
        .args(["material", action, "--request", "-"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(cwd) = cwd {
        command.current_dir(cwd);
    }
    let mut child = command.spawn().unwrap();
    child.stdin.take().unwrap().write_all(bytes).unwrap();
    let output = child.wait_with_output().unwrap();
    assert_eq!(
        output.status.code(),
        Some(if ok { 0 } else { 1 }),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stderr.is_empty());
    let v: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(v["ok"], ok);
    if !ok {
        for k in [
            "project_profile",
            "scene_profile",
            "producer_commit",
            "roots",
            "images",
            "samples",
            "saved_location",
        ] {
            assert!(v.get(k).is_none(), "{k}");
        }
    }
    v
}
fn cli(action: &str, request: &Value, ok: bool) -> Value {
    cli_raw(action, &serde_json::to_vec(request).unwrap(), None, ok)
}
fn colors(result: &Value) -> Vec<Value> {
    result["samples"]
        .as_array()
        .unwrap()
        .iter()
        .map(|s| s["rgba8"].clone())
        .collect()
}
fn goldens() -> Vec<Value> {
    vec![
        json!([0, 0, 255, 255]),
        json!([255, 255, 0, 255]),
        json!([255, 0, 0, 255]),
        json!([0, 255, 0, 255]),
    ]
}

#[test]
fn polygon_project_samples_saves_reopens_and_moves_with_exact_source_bytes() {
    let f = Fixture::new();
    let inspected = cli("inspect", &f.request(), true);
    assert_eq!(inspected["polygons"], 6);
    assert_eq!(inspected["triangles"], 0);
    assert!(inspected.get("saved_location").is_none());
    assert_eq!(colors(&cli("sample", &f.sample_request(), true)), goldens());
    let out = f.root.join("owned");
    let mut request = f.request();
    request["output"] = json!(out);
    let saved = cli("import", &request, true);
    assert_eq!(saved["operation"], "import");
    assert!(saved["saved_location"].is_string());
    assert_eq!(fs::read(out.join("uv_panel.scene.json")).unwrap(), SOURCE);
    assert_eq!(fs::read(out.join("four-colors.png")).unwrap(), PNG);
    assert_eq!(fs::read(out.join("project.json")).unwrap(), PROJECT);
    assert_eq!(cli("import", &request, false)["code"], "output_exists");
    let moved = f.root.join("relocated");
    fs::rename(&out, &moved).unwrap();
    let mut sample = f.sample_request();
    sample["project"] = json!("project.json");
    let reopened = cli_raw(
        "sample",
        &serde_json::to_vec(&sample).unwrap(),
        Some(&moved),
        true,
    );
    assert_eq!(colors(&reopened), goldens());
    assert_eq!(reopened["scene_sha256"], hash(SOURCE));
    assert_eq!(fs::read(moved.join("uv_panel.scene.json")).unwrap(), SOURCE);
    assert_eq!(
        fs::read(f.root.join("uv_panel.scene.json")).unwrap(),
        SOURCE
    );
    f.protected();
}

#[test]
fn missing_image_missing_uv_and_bad_payload_fail_before_any_output() {
    for case in ["missing_image", "missing_uv", "hash", "bad_png"] {
        let f = Fixture::new();
        let expected = match case {
            "missing_image" => {
                fs::remove_file(f.root.join("four-colors.png")).unwrap();
                "image_missing"
            }
            "missing_uv" => {
                let mut s: Value = serde_json::from_slice(SOURCE).unwrap();
                s["mesh_assets"]["mesh_mesh"]["polygons"]["p0001"]["uv_layers"] = json!({});
                let b = serde_json::to_vec(&s).unwrap();
                fs::write(f.root.join("uv_panel.scene.json"), &b).unwrap();
                f.edit_project(|p| p["scene"]["sha256"] = json!(hash(&b)));
                "missing_uv"
            }
            "hash" => {
                fs::write(f.root.join("four-colors.png"), b"changed").unwrap();
                "hash_mismatch"
            }
            _ => {
                fs::write(f.root.join("four-colors.png"), b"not PNG").unwrap();
                f.edit_project(|p| p["images"]["four"]["sha256"] = json!(hash(b"not PNG")));
                "invalid_image"
            }
        };
        let out = f.root.join("rejected");
        let mut r = f.request();
        r["output"] = json!(out);
        assert_eq!(cli("import", &r, false)["code"], expected, "{case}");
        assert!(!out.exists());
        f.protected();
    }
}

#[test]
fn descriptor_hash_and_portable_path_checks_cannot_adopt_changed_data() {
    for case in ["descriptor", "traversal", "absolute", "producer"] {
        let f = Fixture::new();
        let mut r = f.request();
        let out = f.root.join("rejected");
        r["output"] = json!(out);
        f.edit_project(|p| match case {
            "descriptor" => p["roots"] = json!(["other"]),
            "traversal" => p["images"]["four"]["path"] = json!("../four-colors.png"),
            "absolute" => p["images"]["four"]["path"] = json!(f.root.join("four-colors.png")),
            _ => p["producer_commit"] = json!("unsupported"),
        });
        if case != "descriptor" {
            r["expected_project_sha256"] = f.request()["expected_project_sha256"].clone();
        }
        let expected = match case {
            "descriptor" => "hash_mismatch",
            "producer" => "unsupported_producer",
            _ => "invalid_path",
        };
        assert_eq!(cli("import", &r, false)["code"], expected);
        assert!(!out.exists());
        f.protected();
    }
}

#[test]
fn nested_resources_are_copied_without_cwd_lookup() {
    let f = Fixture::new();
    fs::create_dir(f.root.join("images")).unwrap();
    fs::rename(
        f.root.join("four-colors.png"),
        f.root.join("images/four.png"),
    )
    .unwrap();
    f.edit_project(|p| p["images"]["four"]["path"] = json!("images/four.png"));
    let mut r = f.request();
    r["output"] = json!(f.root.join("owned"));
    cli("import", &r, true);
    let mut sample = f.sample_request();
    sample["project"] = json!(f.root.join("owned/project.json"));
    assert_eq!(colors(&cli("sample", &sample, true)), goldens());
    assert_eq!(fs::read(f.root.join("owned/images/four.png")).unwrap(), PNG);
    f.protected();
}

#[test]
fn linked_image_is_rejected_even_when_its_hash_matches() {
    let f = Fixture::new();
    let from = f.root.join("four-colors.png");
    let link = f.root.join("link.png");
    #[cfg(unix)]
    std::os::unix::fs::symlink(&from, &link).unwrap();
    #[cfg(windows)]
    std::os::windows::fs::symlink_file(&from, &link).unwrap();
    f.edit_project(|p| p["images"]["four"]["path"] = json!("link.png"));
    assert_eq!(cli("inspect", &f.request(), false)["code"], "invalid_path");
    f.protected();
}

#[test]
fn schema_cli_matches_frozen_bundle_and_bad_request_never_starts_import() {
    let output = Command::new(env!("CARGO_BIN_EXE_formora"))
        .args(["material", "schema"])
        .output()
        .unwrap();
    assert!(output.status.success());
    assert_eq!(
        serde_json::from_slice::<Value>(&output.stdout).unwrap(),
        serde_json::from_str::<Value>(include_str!("../schemas/material-project/contracts.json"))
            .unwrap()
    );
    let bad = br#"{"project":"x","project":"y","expected_project_sha256":"bad"}"#;
    assert_eq!(
        cli_raw("inspect", bad, None, false)["code"],
        "invalid_request"
    );
}

#[test]
fn mcp_shares_polygon_sampler_and_does_not_change_the_open_game_scene() {
    let f = Fixture::new();
    let game = f.root.join("open.scene.json");
    formora::scene::Scene::default().save(&game).unwrap();
    let before = fs::read(&game).unwrap();
    let calls = [
        json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"material-test","version":"1"}}}),
        json!({"jsonrpc":"2.0","method":"notifications/initialized"}),
        json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"material_sample","arguments":{"samples":[]}}}),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"material_sample","arguments":f.sample_request()}}),
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
        for call in calls {
            writeln!(stdin, "{call}").unwrap();
        }
    }
    let output = child.wait_with_output().unwrap();
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    let values: Vec<Value> = String::from_utf8(output.stdout)
        .unwrap()
        .lines()
        .map(|l| serde_json::from_str(l).unwrap())
        .collect();
    assert_eq!(values.len(), 3);
    assert_eq!(values[1]["result"]["isError"], true);
    assert!(values[1]["result"].get("structuredContent").is_none());
    assert_eq!(values[2]["result"]["isError"], false);
    assert_eq!(colors(&values[2]["result"]["structuredContent"]), goldens());
    assert_eq!(fs::read(&game).unwrap(), before);
    f.protected();
}

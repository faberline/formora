use formora::scene::{Command, Scene, room_demo};
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};
use std::fs;
use std::io::Write;
use std::process::{Command as Process, Output, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);
struct Project(std::path::PathBuf);
impl Project {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "formora-agent-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&root).unwrap();
        Self(root)
    }
    fn scene(&self) -> std::path::PathBuf {
        self.0.join("scene.json")
    }
    fn create(&self) {
        drop(Session::create(&self.scene(), room_demo().unwrap()).unwrap());
    }
    fn process(&self, action: &[&str], input: &str) -> Output {
        let mut process = Process::new(env!("CARGO_BIN_EXE_formora"));
        process.args(action).arg("--scene").arg(self.scene());
        let mut child = process
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        child
            .stdin
            .take()
            .unwrap()
            .write_all(input.as_bytes())
            .unwrap();
        child.wait_with_output().unwrap()
    }
}
impl Drop for Project {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn requests(values: &[Value]) -> String {
    values.iter().map(|v| v.to_string() + "\n").collect()
}
fn lines(output: &Output) -> Vec<Value> {
    String::from_utf8(output.stdout.clone())
        .unwrap()
        .lines()
        .map(|l| serde_json::from_str(l).unwrap())
        .collect()
}
fn initialize() -> Value {
    json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"external-test-client","version":"1"}}})
}
fn initialized() -> Value {
    json!({"jsonrpc":"2.0","method":"notifications/initialized"})
}

#[test]
fn one_writer_owns_the_scene_until_its_session_exits() {
    let project = Project::new();
    project.create();
    let owner = Session::open(&project.scene()).unwrap();
    assert!(Session::open(&project.scene()).is_err());
    let inspected = project.process(&["scene", "inspect"], "");
    assert!(inspected.status.success());
    let input = json!({"expected_revision":1,"commands":[{"operation":"advance","seconds":0.1}]})
        .to_string();
    let blocked = project.process(&["scene", "apply", "--request", "-"], &input);
    assert_eq!(blocked.status.code(), Some(1));
    assert_eq!(Scene::load(&project.scene()).unwrap(), *owner.scene());
    drop(owner);
    assert!(Session::open(&project.scene()).is_ok());
}

#[test]
fn initialization_never_overwrites_an_existing_scene() {
    let project = Project::new();
    project.create();
    let before = fs::read(project.scene()).unwrap();
    assert_eq!(
        project
            .process(&["scene", "init", "--demo-room"], "")
            .status
            .code(),
        Some(1)
    );
    assert_eq!(fs::read(project.scene()).unwrap(), before);
}

#[test]
fn failed_disk_commit_rolls_back_in_memory_and_undo_history() {
    let project = Project::new();
    project.create();
    let mut session = Session::open(&project.scene()).unwrap();
    let before = session.scene().clone();
    // Force the atomic replacement to fail without moving an open lock file.
    // Windows forbids renaming its containing directory while that lock is held.
    let backup = project.0.join("scene.backup.json");
    fs::rename(project.scene(), &backup).unwrap();
    fs::create_dir(project.scene()).unwrap();
    let result = session.apply(ApplyRequest {
        expected_revision: before.revision,
        commands: vec![Command::Advance { seconds: 1.0 }],
    });
    assert!(result.is_err());
    assert_eq!(session.scene(), &before);
    assert!(fs::read_dir(&project.0).unwrap().all(|entry| {
        !entry
            .unwrap()
            .file_name()
            .to_string_lossy()
            .ends_with(".tmp")
    }));
    fs::remove_dir(project.scene()).unwrap();
    fs::rename(&backup, project.scene()).unwrap();
    assert!(
        session
            .undo(UndoRequest {
                expected_revision: before.revision
            })
            .is_err()
    );
    assert_eq!(Scene::load(&project.scene()).unwrap(), before);
}

#[test]
fn native_and_mcp_processes_apply_the_same_commands_and_save_the_same_scene() {
    let native = Project::new();
    native.create();
    let mcp = Project::new();
    mcp.create();
    let arguments = json!({"expected_revision":1,"commands":[
        {"operation":"set_door_duration","id":"front_door","duration_seconds":2.0},
        {"operation":"trigger_door","id":"front_door","open":true},
        {"operation":"advance","seconds":1.0}
    ]});
    let native_output = native.process(
        &["scene", "serve"],
        &requests(&[json!({"id":"apply","name":"scene_apply","arguments":arguments})]),
    );
    assert!(native_output.status.success());
    assert_eq!(lines(&native_output)[0]["ok"], true);
    let mcp_output=mcp.process(&["mcp"],&requests(&[initialize(),initialized(),json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"scene_apply","arguments":arguments}})]));
    assert!(
        mcp_output.status.success(),
        "{}",
        String::from_utf8_lossy(&mcp_output.stderr)
    );
    assert_eq!(lines(&mcp_output)[1]["result"]["isError"], false);
    let saved = Scene::load(&mcp.scene()).unwrap();
    assert_eq!(saved.doors["front_door"].progress, 0.5);
    assert_eq!(Scene::load(&native.scene()).unwrap(), saved);
}

#[test]
fn mcp_initialization_discovery_edits_errors_and_undo_work_in_a_real_process() {
    let project = Project::new();
    project.create();
    let messages = requests(&[
        initialize(),
        initialized(),
        json!({"jsonrpc":"2.0","id":2,"method":"tools/list"}),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"scene_apply","arguments":{"expected_revision":1,"commands":[{"operation":"set_door_duration","id":"front_door","duration_seconds":3.0}]}}}),
        json!({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"scene_apply","arguments":{"expected_revision":1,"commands":[{"operation":"advance","seconds":1.0}]}}}),
        json!({"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"scene_undo","arguments":{"expected_revision":2}}}),
        json!({"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"scene_inspect","arguments":{}}}),
    ]);
    let output = project.process(&["mcp"], &messages);
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    let responses = lines(&output);
    assert_eq!(responses.len(), 6);
    assert_eq!(responses[0]["result"]["protocolVersion"], "2025-11-25");
    let tools = responses[1]["result"]["tools"].as_array().unwrap();
    assert_eq!(tools.len(), 5);
    assert!(
        tools
            .iter()
            .any(|tool| tool["name"] == "model_package_schema")
    );
    assert!(tools.iter().any(|tool| tool["name"] == "model_import"));
    let apply = tools.iter().find(|t| t["name"] == "scene_apply").unwrap();
    assert!(apply["inputSchema"]["$defs"]["Command"].is_object());
    assert_eq!(responses[2]["result"]["structuredContent"]["revision"], 2);
    assert_eq!(responses[3]["result"]["isError"], true);
    assert_eq!(responses[4]["result"]["structuredContent"]["revision"], 3);
    assert_eq!(
        responses[5]["result"]["structuredContent"]["scene"]["doors"]["front_door"]["duration_seconds"],
        1.0
    );
    assert_eq!(Scene::load(&project.scene()).unwrap().revision, 3);
}

#[test]
fn mcp_requires_initialization_and_notifications_cannot_mutate_the_scene() {
    let project = Project::new();
    project.create();
    let before = Scene::load(&project.scene()).unwrap();
    let output=project.process(&["mcp"],&requests(&[
        json!({"jsonrpc":"2.0","id":0,"method":"tools/list"}),initialize(),
        json!({"jsonrpc":"2.0","id":2,"method":"tools/list"}),initialized(),
        json!({"jsonrpc":"2.0","method":"tools/call","params":{"name":"scene_apply","arguments":{"expected_revision":1,"commands":[{"operation":"advance","seconds":1.0}]}}}),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"unknown","arguments":{}}}),
    ]));
    let replies = lines(&output);
    assert_eq!(replies.len(), 4);
    assert_eq!(replies[0]["error"]["code"], -32600);
    assert_eq!(replies[2]["error"]["code"], -32600);
    assert_eq!(replies[3]["error"]["code"], -32602);
    assert_eq!(Scene::load(&project.scene()).unwrap(), before);
}

#[test]
fn malformed_mcp_requests_do_not_end_the_session_or_write_nonprotocol_output() {
    let project = Project::new();
    project.create();
    let mut input = "not json\n[]\n".to_owned();
    input += &requests(&[
        initialize(),
        initialized(),
        json!({"jsonrpc":"2.0","id":9,"method":"ping"}),
    ]);
    let output = project.process(&["mcp"], &input);
    assert!(output.status.success());
    let replies = lines(&output);
    assert_eq!(replies.len(), 4);
    assert_eq!(replies[0]["error"]["code"], -32700);
    assert_eq!(replies[1]["error"]["code"], -32600);
    assert_eq!(replies[3]["id"], 9);
    assert!(replies.iter().all(|r| r["jsonrpc"] == "2.0"));
}

#[test]
fn mcp_startup_errors_only_write_to_stderr() {
    let project = Project::new();
    let output = project.process(&["mcp"], "");
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    assert!(!output.stderr.is_empty());
}

#[test]
fn invalid_cli_request_and_stale_revision_do_not_change_the_file() {
    let project = Project::new();
    project.create();
    let before = fs::read(project.scene()).unwrap();
    for input in [
        "not json",
        r#"{"expected_revision":0,"commands":[{"operation":"advance","seconds":1}]}"#,
    ] {
        let output = project.process(&["scene", "apply", "--request", "-"], input);
        assert_eq!(output.status.code(), Some(1));
        assert_eq!(fs::read(project.scene()).unwrap(), before);
    }
}

#[test]
fn mesh_assets_have_the_same_cli_and_mcp_results_and_can_be_queried_and_reopened() {
    let native = Project::new();
    native.create();
    let mcp = Project::new();
    mcp.create();
    let mut asset: Value =
        serde_json::from_str(include_str!("fixtures/triangle-asset.json")).unwrap();
    asset["material_slots"][0] = json!("door_material");
    let arguments = json!({"expected_revision":1,"commands":[
        {"operation":"set_mesh_asset","id":"shared","asset":asset},
        {"operation":"create_entity","id":"imported","entity":{"name":"Imported","parent":null,"transform":{"translation":[0,0,1],"rotation":[0,0,0,1],"scale":[1,1,1]},"content":{"kind":"mesh","geometry":{"kind":"asset","id":"shared"},"material":null}}},
        {"operation":"set_mesh_vertices","id":"shared","positions":{"a":[0,0,0.5]}}
    ]});
    let output = native.process(
        &["scene", "apply", "--request", "-"],
        &arguments.to_string(),
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let output=mcp.process(&["mcp"],&requests(&[initialize(),initialized(),
        json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"scene_apply","arguments":arguments}}),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"scene_inspect","arguments":{"mesh_asset":"shared"}}}),
        json!({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"scene_apply","arguments":{"expected_revision":2,"commands":[{"operation":"delete_mesh_asset","id":"shared"}]}}}),
    ]));
    assert!(output.status.success());
    let responses = lines(&output);
    assert_eq!(responses[1]["result"]["isError"], false);
    assert_eq!(
        responses[2]["result"]["structuredContent"]["mesh_asset"]["vertices"]["a"],
        json!([0., 0., 0.5])
    );
    assert_eq!(responses[3]["result"]["isError"], true);
    assert_eq!(
        Scene::load(&native.scene()).unwrap(),
        Scene::load(&mcp.scene()).unwrap()
    );
    let output = native.process(&["scene", "inspect", "--mesh-asset", "shared"], "");
    assert!(output.status.success());
    assert_eq!(
        lines(&output)[0],
        responses[2]["result"]["structuredContent"]
    );
    let invalid = native.process(
        &[
            "scene",
            "inspect",
            "--entity",
            "imported",
            "--mesh-asset",
            "shared",
        ],
        "",
    );
    assert_eq!(invalid.status.code(), Some(1));
}

#[test]
fn duplicate_mesh_ids_in_raw_native_and_mcp_messages_cannot_mutate_the_scene() {
    let arguments = r#"{"expected_revision":1,"commands":[{"operation":"set_mesh_asset","id":"duplicate","asset":{"vertices":{"a":[0,0,0],"a":[9,0,0]},"triangles":{},"material_slots":[]}}]}"#;
    for mcp in [false, true] {
        let project = Project::new();
        project.create();
        let before = fs::read(project.scene()).unwrap();
        let input = if mcp {
            requests(&[initialize(), initialized()])
                + &format!(
                    r#"{{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{{"name":"scene_apply","arguments":{arguments}}}}}"#
                )
                + "\n"
        } else {
            format!(r#"{{"id":1,"name":"scene_apply","arguments":{arguments}}}"#) + "\n"
        };
        let output = project.process(if mcp { &["mcp"] } else { &["scene", "serve"] }, &input);
        assert!(output.status.success());
        let replies = lines(&output);
        let reply = replies.last().unwrap();
        if mcp {
            assert_eq!(reply["error"]["code"], -32700);
        } else {
            assert_eq!(reply["ok"], false);
        }
        assert_eq!(fs::read(project.scene()).unwrap(), before);
    }
}

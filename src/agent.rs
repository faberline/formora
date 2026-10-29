//! Native JSON commands and the MCP stdio adapter share one locked session.
use crate::session::{ApplyRequest, InspectRequest, Session, UndoRequest};
use serde_json::{Value, json};
use std::io::{self, BufRead, Read, Write};

const MAX_MESSAGE: usize = 16 * 1024 * 1024;

pub fn dispatch(session: &mut Session, name: &str, arguments: Value) -> Result<Value, String> {
    fn parse<T: serde::de::DeserializeOwned>(value: Value) -> Result<T, String> {
        serde_json::from_value(value).map_err(|e| e.to_string())
    }
    match name {
        "scene_inspect" => session
            .inspect(parse::<InspectRequest>(arguments)?)
            .map_err(|e| e.to_string()),
        "scene_apply" => session
            .apply_with_result(parse::<ApplyRequest>(arguments)?)
            .map(|result| json!(result))
            .map_err(|e| e.to_string()),
        "scene_undo" => session
            .undo(parse::<UndoRequest>(arguments)?)
            .map(|revision| json!({"revision":revision}))
            .map_err(|e| e.to_string()),
        _ => Err(format!("unknown tool: {name}")),
    }
}

pub fn tools() -> Value {
    json!([
        {"name":"scene_inspect","description":"Inspect the current scene, one entity, or one mesh_asset (optionally with resolved face/corner normals, or tessellated with polygon corner indices and diagnostics). No changes are made.","inputSchema":schemars::schema_for!(InspectRequest),"annotations":{"readOnlyHint":true}},
        {"name":"scene_apply","description":"Apply one atomic command batch at expected_revision. Every command must leave a valid scene. Success is saved before returning. Query the scene first to obtain its revision.","inputSchema":schemars::schema_for!(ApplyRequest),"annotations":{"readOnlyHint":false,"destructiveHint":true}},
        {"name":"scene_undo","description":"Undo the last successful batch in this process. The restored scene is saved with a new revision. Undo history is not kept across process restarts.","inputSchema":schemars::schema_for!(UndoRequest),"annotations":{"readOnlyHint":false,"destructiveHint":true}}
    ])
}

fn read_message(reader: &mut impl BufRead) -> io::Result<Option<Vec<u8>>> {
    let mut bytes = Vec::new();
    let count = Read::by_ref(reader)
        .take((MAX_MESSAGE + 1) as u64)
        .read_until(b'\n', &mut bytes)?;
    if count == 0 {
        return Ok(None);
    }
    if count > MAX_MESSAGE {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "message exceeds 16 MiB",
        ));
    }
    Ok(Some(bytes))
}

fn write_message(writer: &mut impl Write, message: &Value) -> io::Result<()> {
    serde_json::to_writer(&mut *writer, message)?;
    writer.write_all(b"\n")?;
    writer.flush()
}

pub fn native_serve(
    session: &mut Session,
    mut reader: impl BufRead,
    mut writer: impl Write,
) -> io::Result<()> {
    while let Some(bytes) = read_message(&mut reader)? {
        let response = match crate::json::value_from_slice(&bytes) {
            Ok(request) => {
                let id = request.get("id").cloned().unwrap_or(Value::Null);
                let result = match (
                    request.get("name").and_then(Value::as_str),
                    request.get("arguments"),
                ) {
                    (Some(name), Some(arguments)) => dispatch(session, name, arguments.clone()),
                    _ => Err("request needs name and arguments".into()),
                };
                match result {
                    Ok(result) => json!({"id":id,"ok":true,"result":result}),
                    Err(error) => json!({"id":id,"ok":false,"error":error}),
                }
            }
            Err(error) => json!({"id":null,"ok":false,"error":error.to_string()}),
        };
        write_message(&mut writer, &response)?;
    }
    Ok(())
}

#[derive(PartialEq, Eq)]
enum Phase {
    New,
    AwaitInitialized,
    Ready,
}

pub struct McpServer {
    phase: Phase,
}

impl Default for McpServer {
    fn default() -> Self {
        Self { phase: Phase::New }
    }
}

fn rpc_error(id: Value, code: i64, message: impl Into<String>) -> Value {
    json!({"jsonrpc":"2.0","id":id,"error":{"code":code,"message":message.into()}})
}

impl McpServer {
    pub fn handle(&mut self, session: &mut Session, request: Value) -> Option<Value> {
        if request.get("jsonrpc").and_then(Value::as_str) != Some("2.0")
            || !request.get("method").is_some_and(Value::is_string)
        {
            return Some(rpc_error(Value::Null, -32600, "invalid JSON-RPC request"));
        }
        let method = request["method"].as_str().expect("method was checked");
        let Some(id) = request.get("id").cloned() else {
            if method == "notifications/initialized" && self.phase == Phase::AwaitInitialized {
                self.phase = Phase::Ready;
            }
            // Notifications never execute request-only mutation methods.
            return None;
        };
        if !(id.is_string() || id.is_i64() || id.is_u64()) {
            return Some(rpc_error(
                Value::Null,
                -32600,
                "request ID must be a string or integer",
            ));
        }
        if let Some(params) = request.get("params") {
            if !params.is_object() {
                return Some(rpc_error(id, -32602, "params must be an object"));
            }
        }
        if method == "ping" {
            return Some(json!({"jsonrpc":"2.0","id":id,"result":{}}));
        }
        let params = request.get("params").cloned().unwrap_or_else(|| json!({}));
        if method == "initialize" {
            if self.phase != Phase::New {
                return Some(rpc_error(id, -32600, "connection is already initialized"));
            }
            let Some(requested) = params.get("protocolVersion").and_then(Value::as_str) else {
                return Some(rpc_error(id, -32602, "protocolVersion is required"));
            };
            if !params.get("capabilities").is_some_and(Value::is_object)
                || !params
                    .get("clientInfo")
                    .and_then(|c| c.get("name"))
                    .is_some_and(Value::is_string)
                || !params
                    .get("clientInfo")
                    .and_then(|c| c.get("version"))
                    .is_some_and(Value::is_string)
            {
                return Some(rpc_error(
                    id,
                    -32602,
                    "capabilities and clientInfo are required",
                ));
            }
            let version = match requested {
                "2025-11-25" | "2025-06-18" | "2025-03-26" => requested,
                _ => "2025-11-25",
            };
            self.phase = Phase::AwaitInitialized;
            return Some(
                json!({"jsonrpc":"2.0","id":id,"result":{"protocolVersion":version,"capabilities":{"tools":{}},"serverInfo":{"name":"formora","version":env!("CARGO_PKG_VERSION")},"instructions":"Inspect before editing. Edits are atomic, revision-checked and saved on success. One writer process owns this scene until it exits."}}),
            );
        }
        if self.phase != Phase::Ready {
            return Some(rpc_error(
                id,
                -32600,
                "initialize and notifications/initialized are required",
            ));
        }
        let result = match method {
            "tools/list" => {
                if params.get("cursor").is_some() {
                    return Some(rpc_error(id, -32602, "unknown pagination cursor"));
                }
                json!({"tools":tools()})
            }
            "tools/call" => {
                let Some(name) = params.get("name").and_then(Value::as_str) else {
                    return Some(rpc_error(id, -32602, "tool name is required"));
                };
                if !["scene_inspect", "scene_apply", "scene_undo"].contains(&name) {
                    return Some(rpc_error(id, -32602, "unknown tool"));
                }
                let arguments = params
                    .get("arguments")
                    .cloned()
                    .unwrap_or_else(|| json!({}));
                match dispatch(session, name, arguments) {
                    Ok(value) => {
                        json!({"content":[{"type":"text","text":value.to_string()}],"structuredContent":value,"isError":false})
                    }
                    Err(error) => json!({"content":[{"type":"text","text":error}],"isError":true}),
                }
            }
            _ => return Some(rpc_error(id, -32601, "method not found")),
        };
        Some(json!({"jsonrpc":"2.0","id":id,"result":result}))
    }
}

pub fn mcp_serve(
    session: &mut Session,
    mut reader: impl BufRead,
    mut writer: impl Write,
) -> io::Result<()> {
    let mut server = McpServer::default();
    mcp_loop(&mut reader, &mut writer, |request| {
        server.handle(session, request)
    })
}

pub fn mcp_serve_shared(
    session: std::sync::Arc<std::sync::Mutex<Session>>,
    mut reader: impl BufRead,
    mut writer: impl Write,
) -> io::Result<()> {
    let mut server = McpServer::default();
    mcp_loop(&mut reader, &mut writer, |request| match session.lock() {
        Ok(mut session) => server.handle(&mut session, request),
        Err(_) => Some(rpc_error(
            request.get("id").cloned().unwrap_or(Value::Null),
            -32603,
            "scene session is unavailable",
        )),
    })
}

fn mcp_loop(
    mut reader: impl BufRead,
    mut writer: impl Write,
    mut handle: impl FnMut(Value) -> Option<Value>,
) -> io::Result<()> {
    while let Some(bytes) = read_message(&mut reader)? {
        let response = match crate::json::value_from_slice(&bytes) {
            Ok(request) => handle(request),
            Err(error) => Some(rpc_error(Value::Null, -32700, error.to_string())),
        };
        if let Some(message) = response {
            write_message(&mut writer, &message)?;
        }
    }
    Ok(())
}

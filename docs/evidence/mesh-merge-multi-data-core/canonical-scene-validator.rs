//! Test harness only. Read authored scenes from stdin, not source answers.
use formora::scene::{Editor, Scene};
use formora::session::InspectRequest;
use serde_json::{Value, json};
use std::io::{self, BufRead, Write};

fn inspect(input: Value) -> Result<Value, String> {
    let id = input["id"].as_str().ok_or("missing case ID")?;
    let scene: Scene = serde_json::from_value(input["scene"].clone()).map_err(|e| e.to_string())?;
    let editor = Editor::new(scene).map_err(|e| e.to_string())?;
    let mut worlds = serde_json::Map::new();
    for name in editor.scene().entities.keys() {
        let query = InspectRequest {
            entity: Some(name.clone()),
            world: true,
            ..InspectRequest::default()
        };
        worlds.insert(
            name.clone(),
            query.inspect(editor.scene()).map_err(|e| e.to_string())?,
        );
    }
    Ok(json!({"id":id,"accepted":true,"scene":editor.scene(),"worlds":worlds}))
}

fn main() {
    let stdin = io::stdin();
    let mut output = io::BufWriter::new(io::stdout().lock());
    for line in stdin.lock().lines() {
        let input: Value = serde_json::from_str(&line.unwrap()).unwrap();
        let response = match inspect(input.clone()) {
            Ok(value) => value,
            Err(error) => json!({"id":input["id"],"accepted":false,"error":error}),
        };
        serde_json::to_writer(&mut output, &response).unwrap();
        output.write_all(b"\n").unwrap();
        output.flush().unwrap();
    }
}

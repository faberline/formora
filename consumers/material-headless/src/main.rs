//! External caller. Default mode has no GPU dependency or adapter/device creation.
#[cfg(feature = "gpu")]
mod gpu;
use formora::material_project::{
    self,
    render_data::{Frame, RenderScene},
};
use serde_json::{Value, json};
use std::collections::BTreeMap;
#[cfg(feature = "gpu")]
use std::path::PathBuf;

fn main() -> std::process::ExitCode {
    match run() {
        Ok(record) => {
            let ok = record["ok"] == true;
            println!("{record}");
            if ok {
                std::process::ExitCode::SUCCESS
            } else {
                std::process::ExitCode::from(1)
            }
        }
        Err(e) => {
            println!(
                "{}",
                json!({"ok":false,"error":e.to_string(),"GPU_acceptance":false})
            );
            std::process::ExitCode::from(1)
        }
    }
}
fn run() -> Result<Value, Box<dyn std::error::Error>> {
    let mut options = BTreeMap::new();
    let mut args = std::env::args().skip(1);
    let mut gpu_requested = false;
    while let Some(key) = args.next() {
        if key == "--gpu" {
            if gpu_requested {
                return Err("duplicate --gpu".into());
            }
            gpu_requested = true;
            continue;
        }
        if ![
            "--project",
            "--expected-project-sha256",
            "--case",
            "--output",
        ]
        .contains(&key.as_str())
        {
            return Err(format!("unknown option: {key}").into());
        }
        let value = args.next().ok_or("option requires value")?;
        if options.insert(key, value).is_some() {
            return Err("duplicate option".into());
        }
    }
    let project_path = options.get("--project").ok_or("--project is required")?;
    let expected = options
        .get("--expected-project-sha256")
        .ok_or("--expected-project-sha256 is required")?;
    let case = options.get("--case").map_or("panel", String::as_str);
    let project = material_project::load(&material_project::InspectRequest {
        project: project_path.into(),
        expected_project_sha256: expected.clone(),
    })
    .map_err(|e| format!("{}: {}", e.stage, e.message))?;
    let scene = RenderScene::from_project(&project)?;
    let frame = Frame::diagnostic_panel();
    let protocol: Value = serde_json::from_str(material_project::render_data::PROTOCOL)?;
    let mut cpu_pixels = Vec::new();
    let expected_rgba: Vec<[u8; 4]> = match case {
        "panel" => {
            let identity = scene.identity();
            if identity.scene_sha256
                != "c8a790703dfaad4aa061667f29830b9877252afdd13a809c0d279f0539223b29"
                || identity.encoded_image_sha256.values().any(|h| {
                    h != "71676a057ca47df88bcaa37191d0be9c2ec46eae37f882cb4ecb01140fff8607"
                })
            {
                return Err("panel case requires exact original source and image".into());
            }
            vec![
                [255, 0, 0, 255],
                [0, 255, 0, 255],
                [0, 0, 255, 255],
                [255, 255, 0, 255],
            ]
        }
        "gray128" => vec![[128, 128, 128, 255]; 4],
        "gray128-half" => vec![[92, 92, 92, 255]; 4],
        "red-half" => vec![[188, 0, 0, 255]; 4],
        _ => return Err("case must be panel, gray128, gray128-half or red-half".into()),
    };
    let expected_factor = if case.ends_with("half") {
        [0.5, 0.5, 0.5, 1.0]
    } else {
        [1.0; 4]
    };
    if scene
        .batches()
        .iter()
        .any(|b| b.factor() != expected_factor)
    {
        return Err("diagnostic requires the case's exact native material factor".into());
    }
    let descriptor: material_project::Project = serde_json::from_slice(project.project_bytes())?;
    let source_bytes = project
        .resource_bytes(&descriptor.scene.path)
        .ok_or("source resource missing")?;
    check_diagnostic_source(source_bytes, expected_factor)?;
    for (i, pixel) in protocol["pixels"]
        .as_array()
        .ok_or("bad protocol")?
        .iter()
        .enumerate()
    {
        let x = pixel["xy"][0].as_u64().ok_or("bad x")? as u32;
        let y = pixel["xy"][1].as_u64().ok_or("bad y")? as u32;
        let hit = scene
            .reference_pixel(&frame, 128, 128, x, y)?
            .ok_or("fixed probe has no surface")?;
        if hit.minimum_barycentric < 1.0 / 64.0 || hit.rgba8 != expected_rgba[i] {
            return Err("CPU baseline failed; do not move probes".into());
        }
        if case == "gray128"
            && hit.linear_rgba[..3]
                .iter()
                .any(|v| (v - 0.21586050011389926).abs() > 1e-12)
        {
            return Err("gray CPU transfer failed".into());
        }
        cpu_pixels.push(hit);
    }
    let record = json!({"ok":true,"mode":"cpu","gpu_executed":false,"case":case,"identity":scene.identity(),"frame":frame,"width":128,"height":128,"CPU_pixels":cpu_pixels,"expected_RGBA8":expected_rgba,"source_buffer_hash_matches_identity":formora::model_package::sha256(source_bytes)==scene.identity().scene_sha256});
    if gpu_requested {
        #[cfg(feature = "gpu")]
        {
            let mut record = record;
            let output = PathBuf::from(
                options
                    .get("--output")
                    .ok_or("GPU mode requires --output NEW_RAW_RGBA_FILE")?,
            );
            record["GPU"] = pollster::block_on(gpu::capture(
                &scene,
                &frame,
                &output,
                &cpu_pixels,
                &expected_rgba,
            ))?;
            record["mode"] = json!("gpu");
            record["gpu_executed"] = json!(true);
            record["ok"] = record["GPU"]["ok"].clone();
            return Ok(record);
        }
        #[cfg(not(feature = "gpu"))]
        {
            return Err("GPU mode requires an explicit build with --features gpu".into());
        }
    } else if options.contains_key("--output") {
        return Err("--output is only used with explicitly requested GPU mode".into());
    }
    Ok(record)
}

fn check_diagnostic_source(
    source_bytes: &[u8],
    expected_factor: [f32; 4],
) -> Result<(), Box<dyn std::error::Error>> {
    let mut expected_source: Value = serde_json::from_slice(include_bytes!(
        "../../../tests/fixtures/texture/uv_panel.scene.json"
    ))?;
    expected_source["materials"]["fixture_white"]["base_color"] = json!(expected_factor);
    let mut source: Value = serde_json::from_slice(source_bytes)?;
    let factor: [f64; 4] =
        serde_json::from_value(source["materials"]["fixture_white"]["base_color"].clone())?;
    if factor != expected_factor.map(f64::from) {
        return Err("diagnostic source requires the exact declared numeric factor".into());
    }
    // JSON 1 and 1.0 have the same required value. Normalize only this allowed
    // field after exact f64 comparison; keep every other source field guarded.
    source["materials"]["fixture_white"]["base_color"] = json!(expected_factor);
    if source != expected_source {
        return Err(
            "diagnostic source must be the original panel with only the declared factor change"
                .into(),
        );
    }
    Ok(())
}

#[cfg(test)]
mod source_tests {
    use super::*;
    const PANEL: &[u8] = include_bytes!("../../../tests/fixtures/texture/uv_panel.scene.json");
    const HALF: [f32; 4] = [0.5, 0.5, 0.5, 1.0];

    fn with_factor(factor: Value) -> Value {
        let mut source: Value = serde_json::from_slice(PANEL).unwrap();
        source["materials"]["fixture_white"]["base_color"] = factor;
        source
    }

    #[test]
    fn integer_and_float_alpha_are_the_same_required_factor() {
        for factor in [json!([0.5, 0.5, 0.5, 1]), json!([0.5, 0.5, 0.5, 1.0])] {
            let source = serde_json::to_vec(&with_factor(factor)).unwrap();
            assert!(check_diagnostic_source(&source, HALF).is_ok());
        }
    }

    #[test]
    fn source_guard_rejects_other_model_edits_and_nearby_factors() {
        for factor in [
            json!([0.500000001, 0.5, 0.5, 1]),
            json!([0.5, 0.5, 0.5]),
            json!([0.5, 0.5, 0.5, "1"]),
        ] {
            let source = serde_json::to_vec(&with_factor(factor)).unwrap();
            assert!(check_diagnostic_source(&source, HALF).is_err());
        }
        let mut source = with_factor(json!([0.5, 0.5, 0.5, 1.0]));
        source["mesh_assets"]["mesh_mesh"]["vertices"]["v0000"][0] = json!(42.0);
        assert!(check_diagnostic_source(&serde_json::to_vec(&source).unwrap(), HALF).is_err());
        let mut source = with_factor(json!([0.5, 0.5, 0.5, 1.0]));
        source["mesh_assets"]["mesh_mesh"]["polygons"]["p0001"]["uv_layers"]["uv0"][0][0] =
            json!(0.125);
        assert!(check_diagnostic_source(&serde_json::to_vec(&source).unwrap(), HALF).is_err());
    }

    #[test]
    fn untouched_panel_still_matches_white_factor() {
        assert!(check_diagnostic_source(PANEL, [1.0; 4]).is_ok());
    }
}

use super::*;
use crate::material_project::{self, PreparedProject};
use crate::model_package::sha256;
use serde_json::{Value, json};
use std::collections::BTreeSet;

const SOURCE: &[u8] = include_bytes!("../../../tests/fixtures/texture/uv_panel.scene.json");
const PNG: &[u8] = include_bytes!("../../../tests/fixtures/texture/four-colors.png");
const PROJECT: &[u8] = include_bytes!("../../../tests/fixtures/texture/project.json");
fn original() -> PreparedProject {
    material_project::validate_bytes(
        PROJECT,
        &sha256(PROJECT),
        &BTreeMap::from([
            ("uv_panel.scene.json".into(), SOURCE.to_vec()),
            ("four-colors.png".into(), PNG.to_vec()),
        ]),
    )
    .unwrap()
}
fn changed(change: impl FnOnce(&mut Value), image: &[u8]) -> PreparedProject {
    let mut source: Value = serde_json::from_slice(SOURCE).unwrap();
    change(&mut source);
    let raw = serde_json::to_vec(&source).unwrap();
    let mut p: Value = serde_json::from_slice(PROJECT).unwrap();
    p["scene"]["sha256"] = json!(sha256(&raw));
    p["images"]["four"]["sha256"] = json!(sha256(image));
    let p = serde_json::to_vec(&p).unwrap();
    material_project::validate_bytes(
        &p,
        &sha256(&p),
        &BTreeMap::from([
            ("uv_panel.scene.json".into(), raw),
            ("four-colors.png".into(), image.to_vec()),
        ]),
    )
    .unwrap()
}
fn rgb_png(rgb: [u8; 3]) -> Vec<u8> {
    let mut out = Vec::new();
    {
        let mut enc = png::Encoder::new(&mut out, 1, 1);
        enc.set_color(png::ColorType::Rgb);
        enc.set_depth(png::BitDepth::Eight);
        let mut writer = enc.write_header().unwrap();
        writer.write_image_data(&rgb).unwrap();
    }
    out
}

#[test]
fn all_original_polygons_keep_exact_corner_mapping_and_source_bytes() {
    let project = original();
    let packet = RenderScene::from_project(&project).unwrap();
    let id = packet.identity();
    assert_eq!(id.triangles, 12);
    assert_eq!(id.vertices, 36);
    assert_eq!(id.scene_sha256, sha256(SOURCE));
    let mut faces = BTreeSet::new();
    for batch in packet.batches() {
        for src in batch.sources() {
            let Face::Polygon { id } = &src.face else {
                panic!()
            };
            faces.insert(id.clone());
            let poly = &project.scene.mesh_assets[&src.mesh].polygons[id];
            assert_eq!(
                src.vertex_ids,
                src.corners.map(|c| poly.vertices[c].clone())
            );
            assert_eq!(
                src.source_uvs,
                Some(src.corners.map(|c| poly.uv_layers["uv0"][c]))
            );
        }
    }
    assert_eq!(faces.len(), 6);
    assert_eq!(project.resource_bytes("uv_panel.scene.json"), Some(SOURCE));
    assert_eq!(project.resource_bytes("four-colors.png"), Some(PNG));
    assert_eq!(project.project_bytes(), PROJECT);
    assert_eq!(project.scene.mesh_assets["mesh_mesh"].polygons.len(), 6);
    assert!(project.scene.mesh_assets["mesh_mesh"].triangles.is_empty());
}

#[test]
fn frozen_interior_pixels_match_goldens_and_stay_off_tessellation_seams() {
    let p = original();
    let scene = RenderScene::from_project(&p).unwrap();
    let protocol: Value = serde_json::from_str(PROTOCOL).unwrap();
    assert_eq!(protocol["render"]["extent"], json!([128, 128]));
    for pixel in protocol["pixels"].as_array().unwrap() {
        let x = pixel["xy"][0].as_u64().unwrap() as u32;
        let y = pixel["xy"][1].as_u64().unwrap() as u32;
        let result = scene
            .reference_pixel(&Frame::diagnostic_panel(), 128, 128, x, y)
            .unwrap()
            .unwrap();
        assert_eq!(json!(result.rgba8), pixel["RGBA8"]);
        assert!(result.minimum_barycentric >= 1.0 / 64.0, "{:?}", result);
        assert!(matches!(&result.source.face,Face::Polygon{id}if id=="p0001"));
    }
}

#[test]
fn gray_and_native_material_factor_are_multiplied_in_linear_space() {
    for (rgb, factor, encoded) in [
        ([128; 3], 1.0, [128, 128, 128, 255]),
        ([128; 3], 0.5, [92, 92, 92, 255]),
        ([255, 0, 0], 0.5, [188, 0, 0, 255]),
    ] {
        let image = rgb_png(rgb);
        let p = changed(
            |s| {
                s["materials"]["fixture_white"]["base_color"] = json!([factor, factor, factor, 1.0])
            },
            &image,
        );
        let packet = RenderScene::from_project(&p).unwrap();
        let pixel = packet
            .reference_pixel(&Frame::diagnostic_panel(), 128, 128, 35, 40)
            .unwrap()
            .unwrap();
        assert_eq!(pixel.rgba8, encoded);
        if factor == 1.0 {
            assert!((pixel.linear_rgba[0] - 0.21586050011389926).abs() <= 1e-12);
        }
    }
}

#[test]
fn full_native_concave_polygon_uses_derived_corner_indices_not_a_fan() {
    let p = changed(
        |s| {
            let m = &mut s["mesh_assets"]["mesh_mesh"];
            m["vertices"] = json!({"a":[-0.5,-0.025,0],"b":[0.5,-0.025,0],"c":[0.5,-0.025,1],"d":[0,-0.025,0.5],"e":[-0.5,-0.025,1]});
            m["edges"] =
                json!({"ab":["a","b"],"bc":["b","c"],"cd":["c","d"],"de":["d","e"],"ea":["e","a"]});
            m["polygons"] = json!({"concave":{"vertices":["a","b","c","d","e"],"uv_layers":{"uv0":[[0,0],[1,0],[1,1],[0.5,0.5],[0,1]]},"corner_normals":null,"normal":null,"smooth":false,"material_slot":null}});
        },
        PNG,
    );
    let packet = RenderScene::from_project(&p).unwrap();
    assert_eq!(packet.identity().triangles, 3);
    let area: f64 = packet
        .batches()
        .iter()
        .flat_map(|b| b.vertices().chunks_exact(3))
        .map(|v| {
            let a = v[0].position;
            let b = v[1].position;
            let c = v[2].position;
            f64::from(((b[0] - a[0]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[0] - a[0])).abs()) / 2.0
        })
        .sum();
    assert_eq!(area, 0.75);
    for src in packet.batches()[0].sources() {
        assert!(src.corners.iter().all(|i| *i < 5));
    }
}

#[test]
fn shared_vertices_keep_distinct_face_corner_uvs() {
    let p = changed(
        |s| {
            let m = &mut s["mesh_assets"]["mesh_mesh"];
            m["polygons"] = json!({});
            m["edges"] = json!({});
            m["triangles"] = json!({
        "first":{"vertices":["v0000","v0001","v0005"],"uv_layers":{"uv0":[[0,0],[1,0],[1,1]]},"corner_normals":null,"material_slot":null},
        "seam":{"vertices":["v0000","v0005","v0004"],"uv_layers":{"uv0":[[0.2,0.3],[0.4,0.5],[0.6,0.7]]},"corner_normals":null,"material_slot":null}});
        },
        PNG,
    );
    let scene = RenderScene::from_project(&p).unwrap();
    let b = &scene.batches()[0];
    assert_eq!(b.vertices().len(), 6);
    assert_eq!(b.vertices()[0].position, b.vertices()[3].position);
    assert_ne!(b.vertices()[0].uv, b.vertices()[3].uv);
    assert_eq!(b.sources()[1].source_uvs.unwrap()[0], [0.2, 0.3]);
}

#[test]
fn frame_updates_do_not_edit_project_and_invalid_reference_inputs_fail() {
    let p = original();
    let scene = RenderScene::from_project(&p).unwrap();
    let mut frame = Frame::diagnostic_panel();
    let before = scene
        .reference_pixel(&frame, 128, 128, 35, 40)
        .unwrap()
        .unwrap();
    frame.model_to_world[3][0] = 0.1;
    let after = scene
        .reference_pixel(&frame, 128, 128, 35, 40)
        .unwrap()
        .unwrap();
    assert_ne!(before.uv, after.uv);
    assert_eq!(p.resource_bytes("uv_panel.scene.json"), Some(SOURCE));
    assert!(scene.reference_pixel(&frame, 0, 128, 0, 0).is_err());
    frame.model_to_world[0][0] = f32::NAN;
    assert!(frame.validate().is_err());
    frame = Frame::diagnostic_panel();
    frame.view_projection[2][3] = 1.0;
    assert!(scene.reference_pixel(&frame, 128, 128, 35, 40).is_err());
}

#[test]
fn unsupported_alpha_and_gpu_range_fail_before_upload() {
    let p = changed(
        |s| s["materials"]["fixture_white"]["base_color"][3] = json!(0.5),
        PNG,
    );
    assert_eq!(
        RenderScene::from_project(&p).err().unwrap().code,
        "unsupported_alpha"
    );
    let p = changed(
        |s| {
            s["mesh_assets"]["mesh_mesh"]["polygons"]["p0001"]["uv_layers"]["uv0"][0][0] =
                json!(f64::MAX)
        },
        PNG,
    );
    assert_eq!(
        RenderScene::from_project(&p).err().unwrap().code,
        "gpu_range"
    );
}

#[test]
fn source_world_transform_is_applied_once_and_gpu_data_is_derived() {
    let p = changed(
        |s| s["entities"]["uv_panel"]["transform"]["translation"] = json!([1, 2, 3]),
        PNG,
    );
    let scene = RenderScene::from_project(&p).unwrap();
    let src = &scene.batches()[0].sources()[0];
    let local = p.scene.mesh_assets[&src.mesh].vertices[&src.vertex_ids[0]];
    assert_eq!(
        scene.batches()[0].vertices()[0].position,
        [
            local[0] as f32 + 1.0,
            local[1] as f32 + 2.0,
            local[2] as f32 + 3.0
        ]
    );
}

#[test]
fn original_crate_and_survivor_keep_bound_and_solid_native_materials() {
    for (descriptor, source, path) in [
        (
            include_bytes!("../../../tests/fixtures/texture/crate.project.json").as_slice(),
            include_bytes!("../../../tests/fixtures/texture/palette/crate.scene.json").as_slice(),
            "palette/crate.scene.json",
        ),
        (
            include_bytes!("../../../tests/fixtures/texture/survivor.project.json").as_slice(),
            include_bytes!("../../../tests/fixtures/texture/palette/survivor.scene.json")
                .as_slice(),
            "palette/survivor.scene.json",
        ),
    ] {
        let project = material_project::validate_bytes(
            descriptor,
            &sha256(descriptor),
            &BTreeMap::from([
                (path.into(), source.to_vec()),
                ("four-colors.png".into(), PNG.to_vec()),
            ]),
        )
        .unwrap();
        let scene = RenderScene::from_project(&project).unwrap();
        assert!(scene.identity().triangles > 0);
        let mut solid = 0;
        let mut textured = 0;
        for batch in scene.batches() {
            let material = batch.material().unwrap();
            let binding = project.project.bindings.get(material);
            assert_eq!(batch.image(), binding.map(|b| b.image.as_str()));
            assert!(
                batch
                    .sources()
                    .iter()
                    .all(|s| s.source_uvs.is_some() == binding.is_some())
            );
            if binding.is_some() {
                textured += 1;
            } else {
                solid += 1;
            }
            let native = &project.scene.materials[material];
            assert_eq!(batch.factor(), native.base_color.map(|v| v as f32));
        }
        assert!(solid > 0 && textured > 0);
        assert_eq!(project.resource_bytes(path), Some(source));
        assert_eq!(project.resource_bytes("four-colors.png"), Some(PNG));
    }
}

use super::*;

#[test]
fn wgsl_parses_and_validates_without_creating_a_gpu_device() {
    let module = naga::front::wgsl::parse_str(SHADER).unwrap();
    naga::valid::Validator::new(
        naga::valid::ValidationFlags::all(),
        naga::valid::Capabilities::all(),
    )
    .validate(&module)
    .unwrap();
    assert_eq!(module.entry_points.len(), 2);
}

#[test]
fn gpu_buffer_layout_matches_the_declared_vertex_and_uniform_contract() {
    assert_eq!(std::mem::size_of::<Vertex>(), 20);
    assert_eq!(std::mem::size_of::<Frame>(), 128);
    assert!(SHADER.contains("textureSampleLevel"));
    assert!(SHADER.contains("return color * material.factor"));
}

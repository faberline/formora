struct Frame {
    view_projection: mat4x4<f32>,
    model_to_world: mat4x4<f32>,
};
struct Material { factor: vec4<f32> };
@group(0) @binding(0) var<uniform> frame: Frame;
@group(1) @binding(0) var color_image: texture_2d<f32>;
@group(1) @binding(1) var color_sampler: sampler;
@group(1) @binding(2) var<uniform> material: Material;
struct VertexOut {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
};
@vertex fn vs(@location(0) position: vec3<f32>, @location(1) uv: vec2<f32>) -> VertexOut {
    var out: VertexOut;
    out.position = frame.view_projection * frame.model_to_world * vec4(position, 1.0);
    out.uv = uv;
    return out;
}
@fragment fn fs(input: VertexOut) -> @location(0) vec4<f32> {
    // The image view decodes sRGB; the sRGB target encodes the linear result.
    // Authored UV starts at the bottom; decoded PNG row zero is at the top.
    let color = textureSampleLevel(color_image, color_sampler, vec2(input.uv.x, 1.0-input.uv.y), 0.0);
    return color * material.factor;
}

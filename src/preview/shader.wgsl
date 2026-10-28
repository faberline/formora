struct Camera {
    view_projection: mat4x4<f32>,
    eye: vec4<f32>,
    light_meta: vec4<u32>,
};
@group(0) @binding(0) var<uniform> camera: Camera;
struct Light { position: vec4<f32>, color: vec4<f32> };
@group(0) @binding(1) var<storage, read> lights: array<Light>;

fn unit(value: vec3<f32>) -> vec3<f32> {
    return value * inverseSqrt(max(dot(value, value), 0.000000000001));
}

struct Output {
    @builtin(position) clip: vec4<f32>,
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec4<f32>,
    @location(3) surface: vec2<f32>,
};

@vertex fn vs(
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) color: vec4<f32>,
    @location(3) surface: vec2<f32>,
) -> Output {
    var output: Output;
    output.clip = camera.view_projection * vec4(position, 1.0);
    output.position = position;
    output.normal = normal;
    output.color = color;
    output.surface = surface;
    return output;
}

@fragment fn fs(input: Output, @builtin(front_facing) front: bool) -> @location(0) vec4<f32> {
    let normal = select(-unit(input.normal), unit(input.normal), front);
    let view = unit(camera.eye.xyz - input.position);
    let roughness = clamp(input.surface.x, 0.0, 1.0);
    let metallic = clamp(input.surface.y, 0.0, 1.0);
    let reflection = mix(vec3(0.04), input.color.rgb, metallic);
    var color = input.color.rgb * 0.18;
    for (var i = 0u; i < camera.light_meta.x; i += 1u) {
        let to_light = lights[i].position.xyz - input.position;
        let light = unit(to_light);
        let half_vector = unit(light + view);
        let diffuse = max(dot(normal, light), 0.0);
        let specular = pow(max(dot(normal, half_vector), 0.0), mix(128.0, 4.0, roughness));
        let attenuation = lights[i].color.w / (1.0 + 0.02 * dot(to_light, to_light));
        let illumination = lights[i].color.rgb * attenuation;
        color += input.color.rgb * diffuse * illumination * (1.0 - metallic)
            + specular * reflection * illumination;
    }
    return vec4(color, input.color.a);
}

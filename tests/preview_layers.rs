#![cfg(feature = "headless")]
use formora::geometry::{lights_view, world_transforms};
use formora::scene::{Entity, EntityKind, Geometry, Scene, Transform};

fn light(parent: Option<&str>) -> Entity {
    Entity {
        name: "Light".into(),
        parent: parent.map(str::to_owned),
        transform: Transform {
            translation: [1., 2., 3.],
            ..Default::default()
        },
        content: EntityKind::Light {
            color: [0.1, 0.2, 0.3],
            intensity: 123.,
        },
    }
}

#[test]
fn lights_match_validated_native_world_and_global_entity_order() {
    let mut scene = Scene::default();
    scene.entities.insert("z_sun".into(), light(None));
    scene
        .entities
        .insert("a_lamp".into(), light(Some("parent")));
    scene.entities.insert(
        "parent".into(),
        Entity {
            name: "Parent".into(),
            parent: None,
            transform: Transform {
                translation: [10., -2., 5.],
                scale: [2., 3., 4.],
                ..Default::default()
            },
            content: EntityKind::Empty,
        },
    );
    scene.object_context = Some(formora::objects::Context {
        states: std::collections::BTreeMap::from([(
            "a_lamp".into(),
            formora::objects::State {
                parent_inverse: Some([
                    [1., 0., 0., -4.],
                    [0., 1., 0., 3.],
                    [0., 0., 1., 2.],
                    [0., 0., 0., 1.],
                ]),
                ..Default::default()
            },
        )]),
        ..Default::default()
    });
    let before = scene.clone();
    let world = world_transforms(&scene).unwrap();
    let lights = lights_view(&scene).unwrap();
    assert_eq!(
        lights.iter().map(|l| l.entity.as_str()).collect::<Vec<_>>(),
        vec!["a_lamp", "z_sun"]
    );
    for l in &lights {
        assert_eq!(
            l.position.to_array().map(f64::to_bits),
            world[&l.entity]
                .transform_point3(glam::DVec3::ZERO)
                .to_array()
                .map(f64::to_bits)
        );
        assert_eq!(l.color, [0.1, 0.2, 0.3]);
        assert_eq!(l.intensity, 123.);
    }
    assert_eq!(scene, before);
    scene
        .entities
        .get_mut("parent")
        .unwrap()
        .transform
        .translation[0] += 1.;
    assert_ne!(lights_view(&scene).unwrap()[0].position, lights[0].position);
    assert_eq!(scene.revision, 0);
}

#[test]
fn light_ancestors_can_be_lights_without_duplicates() {
    let mut scene = Scene::default();
    scene.entities.insert("child".into(), light(Some("parent")));
    scene.entities.insert("parent".into(), light(None));
    let lights = lights_view(&scene).unwrap();
    assert_eq!(lights.len(), 2);
    assert_eq!(lights[0].position, glam::DVec3::new(2., 4., 6.));
}

#[test]
fn explicit_light_view_excludes_unrelated_mesh_failures_but_not_ancestor_transforms() {
    let mut scene = Scene::default();
    let mut bad = light(None);
    bad.content = EntityKind::Mesh {
        geometry: Geometry::Asset {
            id: "missing".into(),
        },
        material: None,
    };
    bad.transform.translation[0] = f64::NAN;
    scene.entities.insert("bad".into(), bad);
    assert!(scene.validate().is_err());
    assert!(lights_view(&scene).unwrap().is_empty());
    scene.entities.insert("light".into(), light(None));
    assert_eq!(lights_view(&scene).unwrap().len(), 1);
    scene.entities.get_mut("light").unwrap().parent = Some("bad".into());
    assert!(lights_view(&scene).is_err());
}

#[test]
fn missing_ancestors_cycles_and_invalid_light_values_fail_without_mutation() {
    let mut scene = Scene::default();
    scene
        .entities
        .insert("light".into(), light(Some("missing")));
    assert!(lights_view(&scene).is_err());
    scene.entities.get_mut("light").unwrap().parent = Some("light".into());
    assert!(lights_view(&scene).is_err());
    scene.entities.get_mut("light").unwrap().parent = None;
    for intensity in [-1., f64::NAN, f64::INFINITY] {
        scene.entities.get_mut("light").unwrap().content = EntityKind::Light {
            color: [1.; 3],
            intensity,
        };
        assert!(lights_view(&scene).is_err());
    }
    scene.entities.get_mut("light").unwrap().content = EntityKind::Light {
        color: [1., f64::NAN, 1.],
        intensity: 1.,
    };
    assert!(lights_view(&scene).is_err());
}

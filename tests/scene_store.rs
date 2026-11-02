use formora::mesh::{MeshAsset, Triangle};
use formora::scene::{Annotation, Entity, EntityKind, Geometry, Material, Scene, Transform};
use formora::scene_store::{SceneStore, SceneUpdate};
use std::collections::BTreeMap;

fn scene() -> Scene {
    let mut s = Scene::default();
    s.mesh_assets.insert(
        "mesh".into(),
        MeshAsset {
            vertices: BTreeMap::from([
                ("a".into(), [0., 0., 0.]),
                ("b".into(), [1., 0., 0.]),
                ("c".into(), [0., 1., 0.]),
            ]),
            triangles: BTreeMap::from([(
                "t".into(),
                Triangle {
                    vertices: ["a", "b", "c"].map(str::to_owned),
                    uv_layers: BTreeMap::new(),
                    corner_normals: Some([[0., 0., 1.]; 3]),
                    corner_colors: Some([[0.2, 0.4, 0.6, 1.]; 3]),
                    material_slot: Some(0),
                },
            )]),
            material_slots: vec![Some("paint".into())],
            ..Default::default()
        },
    );
    s.materials.insert(
        "paint".into(),
        Material {
            base_color: [1.; 4],
            roughness: 0.5,
            metallic: 0.,
        },
    );
    s.entities.insert(
        "object".into(),
        Entity {
            name: "Object".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "mesh".into() },
                material: None,
            },
        },
    );
    s
}

#[test]
fn ownership_stamps_and_transform_only_payload_identity() {
    let raw = scene();
    let mut caller = raw.clone();
    let mut store = SceneStore::new(raw).unwrap();
    let mesh = store.mesh_stamp("mesh").unwrap();
    let material = store.material_stamp("paint").unwrap();
    let entity = store.entity_stamp("object").unwrap();
    let settings = store.settings_stamp();
    let global = store.stamp();
    let address = std::ptr::from_ref(&store.scene().mesh_assets["mesh"].vertices["a"]);
    assert!(!store.apply(SceneUpdate::default()).unwrap());
    assert_eq!(global, store.stamp());
    caller
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .vertices
        .get_mut("a")
        .unwrap()[0] = 9.;
    assert_eq!(store.scene().mesh_assets["mesh"].vertices["a"][0], 0.);
    let transform = Transform {
        translation: [-0., 2., 3.],
        ..Default::default()
    };
    store
        .apply(SceneUpdate {
            transforms: BTreeMap::from([("object".into(), transform)]),
            ..Default::default()
        })
        .unwrap();
    assert_eq!(
        address,
        std::ptr::from_ref(&store.scene().mesh_assets["mesh"].vertices["a"])
    );
    assert_eq!(mesh, store.mesh_stamp("mesh").unwrap());
    assert_eq!(material, store.material_stamp("paint").unwrap());
    assert_eq!(settings, store.settings_stamp());
    assert_ne!(entity, store.entity_stamp("object").unwrap());
    assert_ne!(global, store.stamp());
    assert_eq!(store.scene().revision, 0);
    assert_eq!(
        store.scene().entities["object"].transform.translation[0].to_bits(),
        (-0f64).to_bits()
    );
}

#[test]
fn rejected_transaction_restores_all_values_and_stamps() {
    let mut store = SceneStore::new(scene()).unwrap();
    let bytes = serde_json::to_vec(store.scene()).unwrap();
    let stamp = store.stamp();
    let mesh = store.mesh_stamp("mesh");
    let entity = store.entity_stamp("object");
    let material = store.material_stamp("paint");
    let settings = store.settings_stamp();
    let mut bad_mesh = store.scene().mesh_assets["mesh"].clone();
    bad_mesh.vertices.get_mut("a").unwrap()[0] = f64::NAN;
    let mut candidate = store.scene().clone();
    candidate
        .mesh_assets
        .insert("unused".into(), bad_mesh.clone());
    candidate.revision = 99;
    candidate.time_seconds = 3.;
    candidate.annotations = vec![Annotation {
        entity: None,
        position: [1.; 3],
        text: "mark".into(),
    }];
    candidate.materials.get_mut("paint").unwrap().roughness = 0.2;
    let expected = candidate.validate().unwrap_err();
    let actual = store
        .apply(SceneUpdate {
            mesh_assets: BTreeMap::from([("unused".into(), Some(bad_mesh))]),
            materials: BTreeMap::from([(
                "paint".into(),
                candidate.materials.get("paint").cloned(),
            )]),
            revision: Some(99),
            time_seconds: Some(3.),
            annotations: Some(candidate.annotations),
            ..Default::default()
        })
        .unwrap_err();
    assert_eq!(actual, expected);
    assert_eq!(bytes, serde_json::to_vec(store.scene()).unwrap());
    assert_eq!(stamp, store.stamp());
    assert_eq!(mesh, store.mesh_stamp("mesh"));
    assert_eq!(entity, store.entity_stamp("object"));
    assert_eq!(material, store.material_stamp("paint"));
    assert_eq!(settings, store.settings_stamp());
}

#[test]
fn missing_transform_and_removed_transform_target_are_atomic() {
    let mut store = SceneStore::new(scene()).unwrap();
    let before = store.stamp();
    for (id, entities) in [
        ("missing", BTreeMap::new()),
        ("object", BTreeMap::from([("object".into(), None)])),
    ] {
        assert!(
            store
                .apply(SceneUpdate {
                    entities,
                    transforms: BTreeMap::from([(id.into(), Transform::default())]),
                    revision: Some(4),
                    ..Default::default()
                })
                .is_err()
        );
        assert_eq!(before, store.stamp());
        assert_eq!(store.scene(), &scene());
    }
}

#[test]
fn full_scene_rules_and_error_order_remain_in_force() {
    let original = scene();
    for case in 0..8 {
        let mut expected = original.clone();
        let mut update = SceneUpdate::default();
        match case {
            0 => {
                expected.schema_version = 7;
                update.schema_version = Some(7);
            }
            1 => {
                expected.time_seconds = f64::NAN;
                update.time_seconds = Some(f64::NAN);
            }
            2 => {
                expected.active_camera = Some("object".into());
                update.active_camera = Some(expected.active_camera.clone());
            }
            3 => {
                expected.materials.remove("paint");
                update.materials.insert("paint".into(), None);
            }
            4 => {
                expected.entities.get_mut("object").unwrap().parent = Some("object".into());
                update
                    .entities
                    .insert("object".into(), expected.entities.get("object").cloned());
            }
            5 => {
                expected.mesh_assets.remove("mesh");
                update.mesh_assets.insert("mesh".into(), None);
            }
            6 => {
                expected.entities.get_mut("object").unwrap().transform.scale[1] = f64::INFINITY;
                update.transforms.insert(
                    "object".into(),
                    expected.entities["object"].transform.clone(),
                );
            }
            _ => {
                expected.annotations.push(Annotation {
                    entity: Some("missing".into()),
                    position: [0.; 3],
                    text: "mark".into(),
                });
                update.annotations = Some(expected.annotations.clone());
            }
        }
        let error = expected.validate().unwrap_err();
        assert_eq!(SceneStore::new(expected.clone()).err().unwrap(), error);
        let mut store = SceneStore::new(original.clone()).unwrap();
        let stamp = store.stamp();
        assert_eq!(store.apply(update).unwrap_err(), error);
        assert_eq!(store.scene(), &original);
        assert_eq!(store.stamp(), stamp);
        assert_eq!(store.replace_all(expected).unwrap_err(), error);
        assert_eq!(store.scene(), &original);
        assert_eq!(store.stamp(), stamp);
    }
}

#[test]
fn accepted_batch_supports_dependency_changes_and_complete_replacement() {
    let mut store = SceneStore::new(scene()).unwrap();
    let mut entity = store.scene().entities["object"].clone();
    entity.content = EntityKind::Empty;
    store
        .apply(SceneUpdate {
            entities: BTreeMap::from([("object".into(), Some(entity))]),
            mesh_assets: BTreeMap::from([("mesh".into(), None)]),
            materials: BTreeMap::from([("paint".into(), None)]),
            active_camera: Some(None),
            annotations: Some(Vec::new()),
            doors: Some(BTreeMap::new()),
            authoring_context: Some(None),
            object_context: Some(None),
            ..Default::default()
        })
        .unwrap();
    assert!(store.mesh_stamp("mesh").is_none());
    assert!(store.material_stamp("paint").is_none());
    let stamp = store.stamp();
    store.replace_all(scene()).unwrap();
    assert_ne!(stamp, store.stamp());
    assert_eq!(store.into_scene(), scene());
}

#[cfg(feature = "headless")]
#[test]
fn store_vertices_match_raw_bits_and_keep_old_branches_after_failures() {
    use formora::geometry::{self, GeometryCache, Vertex};
    use std::sync::Arc;
    let mut store = SceneStore::new(scene()).unwrap();
    let mut cache = GeometryCache::default();
    let first = cache.vertices_store(&store).unwrap();
    let saved = cache.clone();
    assert!(Arc::ptr_eq(&first, &cache.vertices_store(&store).unwrap()));
    for i in 0..4 {
        let mut changed = store.scene().mesh_assets["mesh"].clone();
        changed
            .triangles
            .get_mut("t")
            .unwrap()
            .corner_colors
            .as_mut()
            .unwrap()[0][0] = 0.25 + f64::from(i) * 0.1;
        store
            .apply(SceneUpdate {
                mesh_assets: BTreeMap::from([("mesh".into(), Some(changed))]),
                transforms: BTreeMap::from([(
                    "object".into(),
                    Transform {
                        translation: [f64::from(i), -0., 0.],
                        ..Default::default()
                    },
                )]),
                ..Default::default()
            })
            .unwrap();
        let vertices = cache.vertices_store(&store).unwrap();
        let raw = geometry::vertices(store.scene()).unwrap();
        assert_eq!(
            bytemuck::cast_slice::<Vertex, u8>(&vertices),
            bytemuck::cast_slice::<Vertex, u8>(&raw)
        );
    }
    let valid = store.scene().clone();
    store
        .apply(SceneUpdate {
            transforms: BTreeMap::from([(
                "object".into(),
                Transform {
                    translation: [f64::MAX, 0., 0.],
                    ..Default::default()
                },
            )]),
            ..Default::default()
        })
        .unwrap();
    assert!(cache.vertices_store(&store).is_err());
    store.replace_all(valid).unwrap();
    let fixed = cache.vertices_store(&store).unwrap();
    let raw = geometry::vertices(store.scene()).unwrap();
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(&fixed),
        bytemuck::cast_slice::<Vertex, u8>(&raw)
    );
    let mut branch = saved;
    let original = SceneStore::new(scene()).unwrap();
    assert!(Arc::ptr_eq(
        &first,
        &branch.vertices_store(&original).unwrap()
    ));
    let mut mutable = original.into_scene();
    mutable
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .vertices
        .get_mut("a")
        .unwrap()[0] = f64::NAN;
    assert_eq!(
        branch.vertices(&mutable).err().unwrap(),
        mutable.validate().unwrap_err()
    );
}

#[cfg(feature = "headless")]
#[test]
fn recipe_and_weights_keep_full_validation_on_owned_paths() {
    use formora::geometry::GeometryCache;
    for recipe in [false, true] {
        let mut raw = scene();
        let asset = raw.mesh_assets.get_mut("mesh").unwrap();
        if recipe {
            asset.recipe = Some(formora::mesh::primitives::PrimitiveRecipe {
                primitive: serde_json::from_value(
                    serde_json::json!({"kind":"plane","size":2.,"calc_uvs":false}),
                )
                .unwrap(),
                max_components: 1000,
                edited: true,
                creation_frame: None,
            });
        } else {
            asset.vertex_groups = vec!["pin".into()];
            asset.vertex_weights =
                Some(formora::mesh::selection::VertexWeights(BTreeMap::from([(
                    "a".into(),
                    formora::mesh::selection::GroupWeights(BTreeMap::from([("pin".into(), 0.5)])),
                )])));
        }
        let mut store = SceneStore::new(raw.clone()).unwrap();
        let mut cache = GeometryCache::default();
        cache.vertices_store(&store).unwrap();
        cache.vertices_store(&store).unwrap();
        let asset = raw.mesh_assets.get_mut("mesh").unwrap();
        if recipe {
            asset.recipe.as_mut().unwrap().max_components = 0;
        } else {
            asset
                .vertex_weights
                .as_mut()
                .unwrap()
                .0
                .get_mut("a")
                .unwrap()
                .0
                .insert("pin".into(), f64::NAN);
        }
        let expected = raw.validate().unwrap_err();
        let stamp = store.stamp();
        assert_eq!(
            store
                .apply(SceneUpdate {
                    mesh_assets: BTreeMap::from([("mesh".into(), raw.mesh_assets.remove("mesh"))]),
                    ..Default::default()
                })
                .unwrap_err(),
            expected
        );
        assert_eq!(stamp, store.stamp());
        cache.vertices_store(&store).unwrap();
    }
}

#[cfg(feature = "headless")]
fn owned_world_bits(store: &SceneStore) -> BTreeMap<String, [u64; 16]> {
    use formora::geometry;
    let actual = geometry::world_transforms_store(store).unwrap();
    let expected = geometry::world_transforms(store.scene()).unwrap();
    let bits = |world: BTreeMap<String, glam::DMat4>| {
        world
            .into_iter()
            .map(|(id, matrix)| (id, matrix.to_cols_array().map(f64::to_bits)))
            .collect::<BTreeMap<_, _>>()
    };
    assert_eq!(bits(actual.clone()), bits(expected));
    bits(actual)
}

#[cfg(feature = "headless")]
#[test]
fn owned_world_query_is_current_native_ancestry_precision_delta_and_parent_inverse() {
    let mut raw = scene();
    raw.entities.insert(
        "parent".into(),
        Entity {
            name: "Parent".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Empty,
        },
    );
    raw.entities.get_mut("object").unwrap().parent = Some("parent".into());
    let mut inverse = formora::objects::identity();
    inverse[0][3] = -2.;
    raw.object_context = Some(formora::objects::Context {
        states: BTreeMap::from([(
            "object".into(),
            formora::objects::State {
                parent_inverse: Some(inverse),
                ..Default::default()
            },
        )]),
        ..Default::default()
    });
    let mut store = SceneStore::new(raw).unwrap();
    let first = owned_world_bits(&store);
    for (index, scale) in [[1., 2., -3.], [0., 1., 1.], [-0., -1., 2.], [0.25, 4., 1.]]
        .into_iter()
        .enumerate()
    {
        let mut child = store.scene().entities["object"].transform.clone();
        child.precision = if index % 2 == 0 {
            formora::transforms::Precision::F32
        } else {
            formora::transforms::Precision::F64
        };
        child.translation = [0.123456789, -0., 2.5];
        child.delta.translation = [0.1, 0.2, 0.3];
        child.delta.scale = [1.25, 0.75, 1.];
        child.rotation = [0., 0., 0.3826834323650898, 0.9238795325112867].into();
        let parent = Transform {
            translation: [index as f64 + 2., -0., 4.],
            scale,
            ..Default::default()
        };
        let mut context = store.scene().object_context.clone().unwrap();
        context
            .states
            .get_mut("object")
            .unwrap()
            .parent_inverse
            .as_mut()
            .unwrap()[1][3] = index as f64 * 0.5;
        let revision = store.scene().revision;
        store
            .apply(SceneUpdate {
                transforms: BTreeMap::from([("parent".into(), parent), ("object".into(), child)]),
                object_context: Some(Some(context)),
                ..Default::default()
            })
            .unwrap();
        let current = owned_world_bits(&store);
        assert_ne!(first, current);
        assert_eq!(store.scene().revision, revision);
    }
}

#[cfg(feature = "headless")]
#[test]
fn owned_world_query_keeps_native_f64_when_gpu_f32_fails_and_matches_overflow_errors() {
    use formora::geometry::{self, GeometryCache};
    let valid = scene();
    let mut store = SceneStore::new(valid.clone()).unwrap();
    store
        .apply(SceneUpdate {
            transforms: BTreeMap::from([(
                "object".into(),
                Transform {
                    translation: [f64::MAX, 0., 0.],
                    ..Default::default()
                },
            )]),
            ..Default::default()
        })
        .unwrap();
    assert!(GeometryCache::default().vertices_store(&store).is_err());
    assert!(!owned_world_bits(&store).is_empty());
    let mut parent = store.scene().entities["object"].clone();
    parent.content = EntityKind::Empty;
    parent.transform = Transform {
        scale: [f64::MAX; 3],
        ..Default::default()
    };
    let mut child = store.scene().entities["object"].clone();
    child.parent = Some("parent".into());
    child.transform = Transform {
        scale: [f64::MAX; 3],
        ..Default::default()
    };
    store
        .apply(SceneUpdate {
            entities: BTreeMap::from([
                ("parent".into(), Some(parent)),
                ("object".into(), Some(child)),
            ]),
            ..Default::default()
        })
        .unwrap();
    let stamp = store.stamp();
    let before = serde_json::to_vec(store.scene()).unwrap();
    let error = geometry::world_transforms(store.scene()).unwrap_err();
    assert_eq!(geometry::world_transforms_store(&store).unwrap_err(), error);
    assert_eq!(store.stamp(), stamp);
    assert_eq!(before, serde_json::to_vec(store.scene()).unwrap());
    store.replace_all(valid).unwrap();
    assert_eq!(owned_world_bits(&store).len(), 1);
}

#[cfg(feature = "headless")]
#[test]
fn owned_world_query_keeps_last_valid_state_after_rejected_unused_mesh_and_parent_updates() {
    let mut store = SceneStore::new(scene()).unwrap();
    let original = owned_world_bits(&store);
    let stamp = store.stamp();
    let mut bad = store.scene().mesh_assets["mesh"].clone();
    bad.vertices.get_mut("a").unwrap()[0] = f64::NAN;
    assert!(
        store
            .apply(SceneUpdate {
                mesh_assets: BTreeMap::from([("unused".into(), Some(bad))]),
                ..Default::default()
            })
            .is_err()
    );
    let mut entity = store.scene().entities["object"].clone();
    entity.parent = Some("missing".into());
    assert!(
        store
            .apply(SceneUpdate {
                entities: BTreeMap::from([("object".into(), Some(entity))]),
                ..Default::default()
            })
            .is_err()
    );
    assert_eq!(owned_world_bits(&store), original);
    assert_eq!(store.stamp(), stamp);
}

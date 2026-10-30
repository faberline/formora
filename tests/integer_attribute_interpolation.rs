//! Fixed source integer interpolation: f32 accumulation and half-away rounding.
use formora::mesh::attributes::{IntegerAttributes, IntegerLayer};
use std::collections::BTreeMap;

fn layer(values: &[(&str, i32)]) -> IntegerLayer {
    IntegerLayer(
        values
            .iter()
            .map(|(id, value)| (id.to_string(), *value))
            .collect(),
    )
}

#[test]
fn signed_half_values_follow_the_fixed_source_and_leave_other_ids_and_domains() {
    let mut attributes = IntegerAttributes {
        vertices: BTreeMap::from([
            ("signed".into(), layer(&[("a", -1), ("b", 0), ("other", 7)])),
            ("tag".into(), layer(&[("a", 0), ("b", 1), ("other", 2)])),
        ]),
        edges: BTreeMap::from([("tag".into(), layer(&[("edge", 9)]))]),
        ..IntegerAttributes::default()
    };
    let before = attributes.clone();
    attributes.interpolate_vertices("a", &["a", "b"]).unwrap();
    assert_eq!(attributes.vertices["signed"].0["a"], -1);
    assert_eq!(attributes.vertices["tag"].0["a"], 1);
    for name in ["signed", "tag"] {
        assert_eq!(
            attributes.vertices[name].0["b"],
            before.vertices[name].0["b"]
        );
        assert_eq!(
            attributes.vertices[name].0["other"],
            before.vertices[name].0["other"]
        );
    }
    assert_eq!(attributes.edges, before.edges);
    assert_eq!(attributes.polygons, before.polygons);
    assert_eq!(attributes.triangles, before.triangles);
}

#[test]
fn duplicate_integer_values_do_not_identify_or_remove_components() {
    let mut attributes = IntegerAttributes {
        vertices: BTreeMap::from([("tag".into(), layer(&[("a", 3), ("b", 3), ("c", 4)]))]),
        ..IntegerAttributes::default()
    };
    attributes
        .interpolate_vertices("a", &["a", "b", "c"])
        .unwrap();
    assert_eq!(
        attributes.vertices["tag"].0,
        layer(&[("a", 3), ("b", 3), ("c", 4)]).0
    );
}

#[test]
fn missing_or_duplicate_contributors_do_not_write_any_partial_layer() {
    for contributors in [vec![], vec!["a", "a"], vec!["a", "missing"], vec!["b", "a"]] {
        let mut attributes = IntegerAttributes {
            vertices: BTreeMap::from([
                ("first".into(), layer(&[("a", 0), ("b", 1)])),
                ("last".into(), layer(&[("a", 5), ("b", 8)])),
            ]),
            ..IntegerAttributes::default()
        };
        let before = attributes.clone();
        assert!(attributes.interpolate_vertices("a", &contributors).is_err());
        assert_eq!(attributes, before);
    }
}

#[test]
fn unchanged_singleton_retains_full_i32_data_and_overflow_is_atomic() {
    let mut attributes = IntegerAttributes {
        vertices: BTreeMap::from([("tag".into(), layer(&[("a", i32::MAX), ("b", i32::MAX)]))]),
        ..IntegerAttributes::default()
    };
    let before = attributes.clone();
    attributes.interpolate_vertices("a", &["a"]).unwrap();
    assert_eq!(attributes, before);
    assert!(attributes.interpolate_vertices("a", &["a", "b"]).is_err());
    assert_eq!(attributes, before);
}

#[test]
fn a_missing_late_layer_value_does_not_publish_an_earlier_interpolation() {
    let mut attributes = IntegerAttributes {
        vertices: BTreeMap::from([
            ("first".into(), layer(&[("a", 0), ("b", 1)])),
            ("last".into(), layer(&[("a", 5)])),
        ]),
        ..IntegerAttributes::default()
    };
    let before = attributes.clone();
    assert!(attributes.interpolate_vertices("a", &["a", "b"]).is_err());
    assert_eq!(attributes, before);
}

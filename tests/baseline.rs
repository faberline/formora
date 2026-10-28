use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);

struct Fixture(PathBuf);

impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "formora-contract-test-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(root.join("baseline/cases")).unwrap();
        fs::write(root.join("baseline/source.txt"), "pinned source").unwrap();
        let fixture = Self(root);
        fs::create_dir_all(fixture.0.join("baseline/builds")).unwrap();
        for (product, version, manual, build) in [
            ("blender", "5.2.3", "5.2", "test-blender-build"),
            ("unreal", "5.8.4", "5.8", "test-unreal-build"),
        ] {
            fixture.write(&format!("builds/{product}"), json!({
                "schema_version":1,"product":product,"version":version,
                "documentation_version":manual,"build_id":build,
                "version_probe_status":"passed","product_acceptance":"unrun",
                "entry_executable":"test-only-reference-executable",
                "files":{"test-only-reference-executable":{
                    "sha256":format!("{:x}",Sha256::digest(b"synthetic test fixture")),"bytes":22
                }}
            }));
        }
        fixture.write(
            "manifest",
            json!({"schema_version":1,"products":[
                {"id":"blender","retrieval_complete":true,"source_ids":["blender-transform"]},
                {"id":"unreal","retrieval_complete":true,"source_ids":["unreal-transform"]}
            ]}),
        );
        let manifest_hash = format!(
            "{:x}",
            Sha256::digest(fs::read(fixture.0.join("baseline/manifest.json")).unwrap())
        );
        fixture.write("lock", json!({
            "schema_version":2,"frozen_at":"2026-10-29",
            "products":[
                {"id":"blender","version":"5.2.3","documentation_version":"5.2","manual_root":"https://docs.blender.org/manual/en/5.2/","release_url":"https://www.blender.org/releases/","release_status":"stable","reference_build":{"id":"test-blender-build","evidence_path":"baseline/builds/blender.json"}},
                {"id":"unreal","version":"5.8.4","documentation_version":"5.8","manual_root":"https://dev.epicgames.com/documentation/unreal-engine","release_url":"https://forums.unrealengine.com/t/5-8-4-hotfix-released/2842775","release_status":"stable","reference_build":{"id":"test-unreal-build","evidence_path":"baseline/builds/unreal.json"}}
            ],
            "platforms":["macos","windows","linux"],"exclusions":["native_project_compatibility"],
            "source_manifest_path":"baseline/manifest.json",
            "artifacts":[
                {"path":"baseline/source.txt","url":"https://docs.blender.org/manual/en/5.2/objects.inv","sha256":format!("{:x}",Sha256::digest(b"pinned source"))},
                {"path":"baseline/manifest.json","url":"https://docs.blender.org/manual/en/5.2/objects.inv","sha256":manifest_hash}
            ]
        }));
        for product in ["blender", "unreal"] {
            let path = format!("baseline/builds/{product}.json");
            let hash = format!(
                "{:x}",
                Sha256::digest(fs::read(fixture.0.join(&path)).unwrap())
            );
            fixture.edit("lock", |v| {
                v["artifacts"].as_array_mut().unwrap().push(json!({
                    "path":path,"url":"https://example.com/test-fixture","sha256":hash
                }))
            });
        }
        fixture.write("inventory", json!({
            "schema_version":1,"complete_products":["blender","unreal"],
            "sources":[
                {"id":"blender-transform","product":"blender","title":"Translation","url":"https://docs.blender.org/manual/en/5.2/modeling/meshes/editing/mesh/transform/basic.html","decision":"include","rationale":"","feature_ids":["translate"]},
                {"id":"unreal-transform","product":"unreal","title":"Transforming Actors","url":"https://dev.epicgames.com/documentation/unreal-engine/transforming-actors-in-unreal-engine?application_version=5.8","decision":"include","rationale":"","feature_ids":["translate"]}
            ]
        }));
        fixture.write("catalog", json!({"schema_version":1,"features":[{
            "id":"translate","title":"Translate an object","source_ids":["blender-transform","unreal-transform"],
            "milestone":"0.1","case_path":"baseline/cases/translate.json","review":"accepted"
        }]}));
        fixture.write("cases/translate", json!({
            "schema_version":1,"feature_id":"translate",
            "fixture":{"object":{"position":[0,0,0]}},
            "steps":["Translate the object by [1, 2, 3] in world coordinates."],
            "assertions":[{"target":"object.position.x","expected":1,"absolute_tolerance":0.000001}],
            "evidence":["operation receipt","saved scene inspection"]
        }));
        fixture
    }

    fn write(&self, name: &str, value: Value) {
        fs::write(
            self.0.join(format!("baseline/{name}.json")),
            serde_json::to_vec_pretty(&value).unwrap(),
        )
        .unwrap();
    }

    fn edit(&self, name: &str, edit: impl FnOnce(&mut Value)) {
        let path = self.0.join(format!("baseline/{name}.json"));
        let mut value: Value = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
        edit(&mut value);
        self.write(name, value);
    }

    fn check(&self) -> formora::baseline::Report {
        formora::baseline::check(&self.0).unwrap()
    }

    fn repin(&self, relative: &str) {
        let hash = format!(
            "{:x}",
            Sha256::digest(fs::read(self.0.join(relative)).unwrap())
        );
        self.edit("lock", |v| {
            let artifact = v["artifacts"]
                .as_array_mut()
                .unwrap()
                .iter_mut()
                .find(|a| a["path"] == relative)
                .unwrap();
            artifact["sha256"] = json!(hash);
        });
    }

    fn problem(&self, code: &str) {
        let report = self.check();
        assert!(!report.structurally_valid);
        assert!(!report.baseline_ready);
        assert!(
            report.problems.iter().any(|p| p.code == code),
            "{report:#?}"
        );
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn complete_contract_does_not_claim_product_acceptance() {
    let f = Fixture::new();
    let report = f.check();
    assert!(report.structurally_valid, "{report:#?}");
    assert!(report.baseline_ready);
    assert_eq!(report.product_acceptance, "unrun");
}

#[test]
fn patch_product_versions_use_the_matching_manual_family() {
    let f = Fixture::new();
    assert!(f.check().baseline_ready);
    f.edit("lock", |v| {
        v["products"][1]["documentation_version"] = json!("5.7")
    });
    f.problem("product_documentation_version");
}

#[test]
fn incomplete_or_prerelease_product_versions_cannot_be_frozen_as_stable() {
    for version in ["5.8", "5.8.4-preview", "5.8.4.0", "05.8.4"] {
        let f = Fixture::new();
        f.edit("lock", |v| v["products"][1]["version"] = json!(version));
        f.problem("product_documentation_version");
    }
}

#[test]
fn legacy_lock_schema_cannot_claim_the_full_build_baseline() {
    let f = Fixture::new();
    f.edit("lock", |v| v["schema_version"] = json!(1));
    f.problem("schema_version");
}

#[test]
fn missing_build_probe_keeps_the_strict_baseline_closed() {
    let f = Fixture::new();
    f.edit("lock", |v| {
        v["products"][1]["reference_build"] = Value::Null
    });
    let report = f.check();
    assert!(report.structurally_valid);
    assert!(!report.baseline_ready);
    assert_eq!(report.unverified_builds, ["unreal"]);
    assert_eq!(report.product_acceptance, "unrun");
}

#[test]
fn hash_pinned_build_evidence_must_match_the_declared_reference() {
    for (field, wrong) in [
        ("product", "blender"),
        ("version", "5.8.3"),
        ("documentation_version", "5.7"),
        ("build_id", "other-build"),
        ("version_probe_status", "unrun"),
        ("product_acceptance", "passed"),
    ] {
        let f = Fixture::new();
        f.edit("builds/unreal", |v| v[field] = json!(wrong));
        f.repin("baseline/builds/unreal.json");
        f.problem("build_evidence");
    }
}

#[test]
fn build_evidence_must_identify_a_measured_executable() {
    let f = Fixture::new();
    f.edit("builds/unreal", |v| {
        v["entry_executable"] = json!("missing-executable")
    });
    f.repin("baseline/builds/unreal.json");
    f.problem("build_evidence");
    let f = Fixture::new();
    f.edit("builds/unreal", |v| {
        v["files"]["test-only-reference-executable"]["sha256"] = json!("invalid")
    });
    f.repin("baseline/builds/unreal.json");
    f.problem("build_evidence");
}

#[test]
fn build_evidence_cannot_bypass_the_artifact_hash_pin() {
    let f = Fixture::new();
    f.edit("lock", |v| {
        v["artifacts"]
            .as_array_mut()
            .unwrap()
            .retain(|a| a["path"] != "baseline/builds/unreal.json")
    });
    f.problem("build_pin");
}

#[test]
fn pending_source_keeps_strict_gate_closed() {
    let f = Fixture::new();
    f.edit("inventory", |v| {
        v["sources"][0]["decision"] = json!("pending");
        v["sources"][0]["feature_ids"] = json!([]);
    });
    f.edit("catalog", |v| {
        v["features"][0]["source_ids"] = json!(["unreal-transform"])
    });
    let report = f.check();
    assert!(report.structurally_valid);
    assert!(!report.baseline_ready);
    assert_eq!(report.pending_sources, 1);
}

#[test]
fn incomplete_upstream_inventory_cannot_pass_even_when_known_sources_are_covered() {
    let f = Fixture::new();
    f.edit("inventory", |v| v["complete_products"] = json!(["blender"]));
    let report = f.check();
    assert!(report.structurally_valid);
    assert!(!report.baseline_ready);
    assert_eq!(report.incomplete_products, ["unreal"]);
}

#[test]
fn included_source_needs_coverage() {
    let f = Fixture::new();
    f.edit("inventory", |v| v["sources"][0]["feature_ids"] = json!([]));
    f.edit("catalog", |v| {
        v["features"][0]["source_ids"] = json!(["unreal-transform"])
    });
    let report = f.check();
    assert!(report.structurally_valid);
    assert!(!report.baseline_ready);
    assert_eq!(report.uncovered_sources, 1);
}

#[test]
fn pending_feature_review_is_not_readiness() {
    let f = Fixture::new();
    f.edit("catalog", |v| v["features"][0]["review"] = json!("pending"));
    let report = f.check();
    assert!(report.structurally_valid);
    assert!(!report.baseline_ready);
    assert_eq!(report.pending_features, 1);
}

#[test]
fn source_cannot_claim_a_nonexistent_feature() {
    let f = Fixture::new();
    f.edit("inventory", |v| {
        v["sources"][0]["feature_ids"] = json!(["missing"])
    });
    f.problem("source_feature");
}

#[test]
fn unknown_or_wrong_version_sources_are_rejected() {
    let f = Fixture::new();
    f.edit("inventory", |v| v["sources"][1]["url"] = json!("https://dev.epicgames.com/documentation/unreal-engine/transforming-actors-in-unreal-engine?application_version=5.7"));
    f.problem("source_version");
    f.edit("inventory", |v| {
        v["sources"][0]["product"] = json!("unknown")
    });
    f.problem("source_version");
}

#[test]
fn floating_latest_manual_is_rejected() {
    let f = Fixture::new();
    f.edit("inventory", |v| {
        v["sources"][0]["url"] =
            json!("https://docs.blender.org/manual/en/latest/modeling/index.html")
    });
    f.problem("source_version");
}

#[test]
fn duplicate_feature_and_source_ids_are_rejected() {
    let f = Fixture::new();
    f.edit("catalog", |v| {
        let copy = v["features"][0].clone();
        v["features"].as_array_mut().unwrap().push(copy);
    });
    f.problem("duplicate_feature");
    f.edit("inventory", |v| {
        let copy = v["sources"][0].clone();
        v["sources"].as_array_mut().unwrap().push(copy);
    });
    f.problem("duplicate_source");
}

#[test]
fn source_artifact_tampering_is_rejected() {
    let f = Fixture::new();
    fs::write(f.0.join("baseline/source.txt"), "changed source").unwrap();
    f.problem("artifact_hash");
}

#[test]
fn tests_require_actions_assertions_and_evidence() {
    for field in ["steps", "assertions", "evidence"] {
        let f = Fixture::new();
        f.edit("cases/translate", |v| v[field] = json!([]));
        f.problem("case_contract");
    }
}

#[test]
fn case_identity_and_numeric_tolerances_are_checked() {
    let f = Fixture::new();
    f.edit("cases/translate", |v| v["feature_id"] = json!("other"));
    f.problem("case_identity");
    f.edit("cases/translate", |v| {
        v["assertions"][0]["absolute_tolerance"] = json!(-1)
    });
    f.problem("case_assertion");
    f.edit("cases/translate", |v| {
        v["assertions"][0]["expected"] = json!("text")
    });
    f.problem("case_tolerance");
}

#[test]
fn exclusion_requires_a_reason_and_cannot_also_claim_coverage() {
    let f = Fixture::new();
    f.edit("inventory", |v| {
        v["sources"][0]["decision"] = json!("exclude")
    });
    f.problem("exclusion");
}

#[test]
fn an_empty_catalog_cannot_pass() {
    let f = Fixture::new();
    f.edit("inventory", |v| v["sources"] = json!([]));
    f.edit("catalog", |v| v["features"] = json!([]));
    let report = f.check();
    assert!(!report.structurally_valid);
    assert!(!report.baseline_ready);
}

#[test]
fn removing_an_upstream_source_cannot_reduce_the_acceptance_scope() {
    let f = Fixture::new();
    f.edit("inventory", |v| {
        v["sources"].as_array_mut().unwrap().remove(0);
    });
    f.edit("catalog", |v| {
        v["features"][0]["source_ids"] = json!(["unreal-transform"])
    });
    f.problem("manifest_coverage");
}

#[test]
fn incomplete_retrieval_cannot_be_declared_complete() {
    let f = Fixture::new();
    f.edit("manifest", |v| {
        v["products"][1]["retrieval_complete"] = json!(false)
    });
    let hash = format!(
        "{:x}",
        Sha256::digest(fs::read(f.0.join("baseline/manifest.json")).unwrap())
    );
    f.edit("lock", |v| v["artifacts"][1]["sha256"] = json!(hash));
    f.problem("incomplete_retrieval");
}

#[test]
fn source_manifest_cannot_be_replaced_without_updating_its_pin() {
    let f = Fixture::new();
    f.edit("manifest", |v| v["products"][0]["source_ids"] = json!([]));
    f.problem("artifact_hash");
}

#[test]
fn case_paths_cannot_leave_the_repository() {
    let f = Fixture::new();
    f.edit("catalog", |v| {
        v["features"][0]["case_path"] = json!("../case.json")
    });
    f.problem("case_file");
}

#[cfg(unix)]
#[test]
fn case_symlinks_cannot_leave_the_repository() {
    let f = Fixture::new();
    std::os::unix::fs::symlink(std::env::temp_dir(), f.0.join("outside")).unwrap();
    f.edit("catalog", |v| {
        v["features"][0]["case_path"] = json!("outside")
    });
    f.problem("case_file");
}

#[test]
fn unknown_fields_are_not_silently_ignored() {
    let f = Fixture::new();
    f.edit("catalog", |v| v["features"][0]["accepted"] = json!(true));
    assert!(
        formora::baseline::check(&f.0)
            .unwrap_err()
            .contains("unknown field")
    );
}

fn cli(root: &Path, strict: bool) -> std::process::Output {
    let mut command = Command::new(env!("CARGO_BIN_EXE_formora"));
    command.args(["baseline", "check", "--root"]).arg(root);
    if strict {
        command.arg("--strict");
    }
    command.output().unwrap()
}

#[test]
fn cli_distinguishes_invalid_incomplete_and_ready_contracts() {
    let f = Fixture::new();
    assert_eq!(cli(&f.0, true).status.code(), Some(0));
    f.edit("inventory", |v| v["complete_products"] = json!([]));
    let incomplete = cli(&f.0, true);
    assert_eq!(incomplete.status.code(), Some(2));
    assert_eq!(cli(&f.0, false).status.code(), Some(0));
    let report: Value = serde_json::from_slice(&incomplete.stdout).unwrap();
    assert_eq!(report["product_acceptance"], "unrun");
    f.edit("lock", |v| v["schema_version"] = json!(99));
    assert_eq!(cli(&f.0, true).status.code(), Some(1));
}

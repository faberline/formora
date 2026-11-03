use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Component, Path};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Lock {
    pub schema_version: u32,
    pub frozen_at: String,
    pub products: Vec<Product>,
    pub platforms: Vec<String>,
    pub exclusions: Vec<String>,
    pub source_manifest_path: String,
    pub artifacts: Vec<Artifact>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SourceManifest {
    pub schema_version: u32,
    pub products: Vec<ManifestProduct>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ManifestProduct {
    pub id: String,
    pub retrieval_complete: bool,
    pub source_ids: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Product {
    pub id: String,
    pub version: String,
    pub documentation_version: String,
    pub manual_root: String,
    pub release_url: String,
    pub release_status: String,
    pub reference_build: Option<ReferenceBuild>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReferenceBuild {
    pub id: String,
    pub evidence_path: String,
}

// Capture-specific details remain in the evidence file. These common fields
// bind a version probe to its product pin without claiming feature acceptance.
#[derive(Debug, Deserialize)]
struct BuildEvidence {
    schema_version: u32,
    product: String,
    version: String,
    documentation_version: String,
    build_id: String,
    version_probe_status: String,
    product_acceptance: String,
    entry_executable: String,
    files: BTreeMap<String, BuildFile>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct BuildFile {
    sha256: String,
    bytes: u64,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Artifact {
    pub path: String,
    pub url: String,
    pub sha256: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Inventory {
    pub schema_version: u32,
    pub complete_products: Vec<String>,
    pub sources: Vec<Source>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Source {
    pub id: String,
    pub product: String,
    pub title: String,
    pub url: String,
    pub decision: Decision,
    pub rationale: String,
    pub feature_ids: Vec<String>,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Decision {
    Pending,
    Include,
    Exclude,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Catalog {
    pub schema_version: u32,
    pub features: Vec<Feature>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Feature {
    pub id: String,
    pub title: String,
    pub source_ids: Vec<String>,
    pub milestone: String,
    pub case_path: String,
    pub review: Review,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Review {
    Pending,
    Accepted,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Case {
    pub schema_version: u32,
    pub feature_id: String,
    pub fixture: serde_json::Value,
    pub steps: Vec<String>,
    pub assertions: Vec<Assertion>,
    pub evidence: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Assertion {
    pub target: String,
    pub expected: serde_json::Value,
    pub absolute_tolerance: Option<f64>,
}

#[derive(Debug, Serialize)]
pub struct Report {
    pub structurally_valid: bool,
    pub baseline_ready: bool,
    pub product_acceptance: &'static str,
    pub sources: usize,
    pub features: usize,
    pub pending_sources: usize,
    pub pending_features: usize,
    pub uncovered_sources: usize,
    pub incomplete_products: Vec<String>,
    pub unverified_builds: Vec<String>,
    pub problems: Vec<Problem>,
}

#[derive(Debug, Serialize)]
pub struct Problem {
    pub code: &'static str,
    pub item: String,
    pub detail: String,
}

impl Report {
    fn error(&mut self, code: &'static str, item: impl Into<String>, detail: impl Into<String>) {
        self.problems.push(Problem {
            code,
            item: item.into(),
            detail: detail.into(),
        });
    }
}

fn read<T: for<'de> Deserialize<'de>>(root: &Path, relative: &str) -> Result<T, String> {
    let path = local_path(root, relative)?;
    let bytes = fs::read(&path).map_err(|e| format!("{relative}: {e}"))?;
    serde_json::from_slice(&bytes).map_err(|e| format!("{relative}: {e}"))
}

fn local_path(root: &Path, relative: &str) -> Result<std::path::PathBuf, String> {
    if relative.is_empty()
        || !Path::new(relative)
            .components()
            .all(|c| matches!(c, Component::Normal(_)))
    {
        return Err(format!("path must be repository-relative: {relative}"));
    }
    let root = root.canonicalize().map_err(|e| e.to_string())?;
    let path = root
        .join(relative)
        .canonicalize()
        .map_err(|e| format!("{relative}: {e}"))?;
    if !path.starts_with(root) {
        return Err(format!("path leaves the repository: {relative}"));
    }
    Ok(path)
}

fn pinned_url(product: &Product, url: &str) -> bool {
    if !url.starts_with(&product.manual_root) || url.contains("/latest/") || url.contains("/dev/") {
        return false;
    }
    let suffix = &url[product.manual_root.len()..];
    if !product.manual_root.ends_with('/')
        && !suffix.is_empty()
        && !suffix.starts_with(['/', '?', '#'])
    {
        return false;
    }
    if product.id == "unreal" {
        let query = url
            .split_once('?')
            .map(|(_, q)| q.split('#').next().unwrap_or(q));
        return query.is_some_and(|q| {
            q.split('&')
                .any(|p| p == format!("application_version={}", product.documentation_version))
        });
    }
    product
        .manual_root
        .contains(&format!("/{}/", product.documentation_version))
}

pub fn check(root: &Path) -> Result<Report, String> {
    let lock: Lock = read(root, "baseline/lock.json")?;
    let inventory: Inventory = read(root, "baseline/inventory.json")?;
    let catalog: Catalog = read(root, "baseline/catalog.json")?;
    inspect(root, &lock, &inventory, &catalog)
}

pub fn inspect(
    root: &Path,
    lock: &Lock,
    inventory: &Inventory,
    catalog: &Catalog,
) -> Result<Report, String> {
    let mut report = Report {
        structurally_valid: false,
        baseline_ready: false,
        product_acceptance: "unrun",
        sources: inventory.sources.len(),
        features: catalog.features.len(),
        pending_sources: 0,
        pending_features: 0,
        uncovered_sources: 0,
        incomplete_products: Vec::new(),
        unverified_builds: Vec::new(),
        problems: Vec::new(),
    };
    for (name, version, expected) in [
        ("lock", lock.schema_version, 2),
        ("inventory", inventory.schema_version, 1),
        ("catalog", catalog.schema_version, 1),
    ] {
        if version != expected {
            report.error(
                "schema_version",
                name,
                format!("expected schema version {expected}"),
            );
        }
    }
    if lock.frozen_at.len() != 10 || lock.platforms.is_empty() || lock.exclusions.is_empty() {
        report.error(
            "lock_metadata",
            "lock",
            "date, platforms and exclusions must be specified",
        );
    }
    let mut products = BTreeMap::new();
    for p in &lock.products {
        if products.insert(p.id.as_str(), p).is_some() {
            report.error("duplicate_product", &p.id, "product IDs must be unique");
        }
        if p.version.trim().is_empty()
            || p.release_status != "stable"
            || !p.release_url.starts_with("https://")
        {
            report.error(
                "unverified_release",
                &p.id,
                "a stable release and its source must be pinned",
            );
        }
        let parts: Vec<_> = p.version.split('.').collect();
        if parts.len() != 3
            || parts.iter().any(|part| {
                part.parse::<u32>()
                    .map_or(true, |number| number.to_string() != *part)
            })
            || p.documentation_version != parts[..parts.len().min(2)].join(".")
        {
            report.error(
                "product_documentation_version",
                &p.id,
                "pin an exact major.minor.patch product version and its matching major.minor manual",
            );
        }
        if p.reference_build.is_none() {
            report.unverified_builds.push(p.id.clone());
        }
    }
    for required in ["blender", "unreal"] {
        if !products.contains_key(required) {
            report.error(
                "missing_product",
                required,
                "both reference products are required",
            );
        }
    }
    for id in &inventory.complete_products {
        if !products.contains_key(id.as_str()) {
            report.error("unknown_product", id, "unknown completed inventory");
        }
    }
    for p in &lock.products {
        if !inventory.complete_products.contains(&p.id) {
            report.incomplete_products.push(p.id.clone());
        }
    }
    if lock.artifacts.is_empty() {
        report.error(
            "missing_artifacts",
            "lock",
            "at least one pinned source artifact is required",
        );
    }
    let mut artifact_paths = BTreeSet::new();
    for artifact in &lock.artifacts {
        if !artifact_paths.insert(&artifact.path) {
            report.error(
                "duplicate_artifact",
                &artifact.path,
                "artifact paths must be unique",
            );
        }
        if !artifact.url.starts_with("https://") {
            report.error("artifact_url", &artifact.path, "source must use HTTPS");
        }
        match local_path(root, &artifact.path).and_then(|p| fs::read(p).map_err(|e| e.to_string()))
        {
            Ok(bytes) if format!("{:x}", Sha256::digest(&bytes)) == artifact.sha256 => {}
            Ok(_) => report.error(
                "artifact_hash",
                &artifact.path,
                "source artifact differs from its pinned SHA-256",
            ),
            Err(e) => report.error("artifact_missing", &artifact.path, e),
        }
    }
    for p in &lock.products {
        let Some(pin) = &p.reference_build else {
            continue;
        };
        if pin.id.trim().is_empty() || !lock.artifacts.iter().any(|a| a.path == pin.evidence_path) {
            report.error(
                "build_pin",
                &p.id,
                "a reference build needs an ID and hash-pinned evidence",
            );
        }
        match read::<BuildEvidence>(root, &pin.evidence_path) {
            Ok(evidence) => {
                let valid_files = !evidence.files.is_empty()
                    && evidence.files.contains_key(&evidence.entry_executable)
                    && evidence.files.values().all(|file| {
                        file.bytes > 0
                            && file.sha256.len() == 64
                            && file.sha256.bytes().all(|b| b.is_ascii_hexdigit())
                    });
                if evidence.schema_version != 1
                    || evidence.product != p.id
                    || evidence.version != p.version
                    || evidence.documentation_version != p.documentation_version
                    || evidence.build_id != pin.id
                    || evidence.version_probe_status != "passed"
                    || evidence.product_acceptance != "unrun"
                    || !valid_files
                {
                    report.error(
                        "build_evidence",
                        &p.id,
                        "version probe and executable evidence must match the frozen product and build",
                    );
                }
            }
            Err(error) => report.error("build_evidence", &p.id, error),
        }
    }
    let mut sources = BTreeMap::new();
    let mut source_urls = BTreeSet::new();
    for s in &inventory.sources {
        if s.id.trim().is_empty() || sources.insert(s.id.as_str(), s).is_some() {
            report.error(
                "duplicate_source",
                &s.id,
                "source IDs must be nonempty and unique",
            );
        }
        if !source_urls.insert((&s.product, &s.url)) {
            report.error(
                "duplicate_source_url",
                &s.id,
                "the source URL is already inventoried",
            );
        }
        match products.get(s.product.as_str()) {
            Some(p) if pinned_url(p, &s.url) => {}
            _ => report.error(
                "source_version",
                &s.id,
                "source must belong to a known, pinned manual version",
            ),
        }
        if s.title.trim().is_empty() {
            report.error("source_title", &s.id, "source title must be specified");
        }
        match s.decision {
            Decision::Pending => report.pending_sources += 1,
            Decision::Include if s.feature_ids.is_empty() => report.uncovered_sources += 1,
            Decision::Exclude => {
                if s.rationale.trim().is_empty() || !s.feature_ids.is_empty() {
                    report.error(
                        "exclusion",
                        &s.id,
                        "an exclusion needs a reason and must not claim feature coverage",
                    );
                }
            }
            Decision::Include => {}
        }
    }
    if !lock
        .artifacts
        .iter()
        .any(|a| a.path == lock.source_manifest_path)
    {
        report.error(
            "manifest_unpinned",
            &lock.source_manifest_path,
            "source manifest must be a hashed artifact",
        );
    }
    match read::<SourceManifest>(root, &lock.source_manifest_path) {
        Ok(manifest) => {
            if manifest.schema_version != 1 {
                report.error(
                    "schema_version",
                    "source manifest",
                    "expected schema version 1",
                );
            }
            let mut manifest_products = BTreeSet::new();
            for p in &manifest.products {
                if !manifest_products.insert(p.id.as_str()) || !products.contains_key(p.id.as_str())
                {
                    report.error(
                        "manifest_product",
                        &p.id,
                        "manifest products must be known and unique",
                    );
                }
                let expected: BTreeSet<_> = p.source_ids.iter().map(String::as_str).collect();
                let actual: BTreeSet<_> = inventory
                    .sources
                    .iter()
                    .filter(|s| s.product == p.id)
                    .map(|s| s.id.as_str())
                    .collect();
                if expected.len() != p.source_ids.len() || expected != actual {
                    report.error(
                        "manifest_coverage",
                        &p.id,
                        "inventory must retain every pinned source exactly once",
                    );
                }
                if !p.retrieval_complete && inventory.complete_products.contains(&p.id) {
                    report.error(
                        "incomplete_retrieval",
                        &p.id,
                        "incomplete upstream retrieval cannot be declared a complete inventory",
                    );
                }
            }
            for p in &lock.products {
                if !manifest_products.contains(p.id.as_str()) {
                    report.error(
                        "manifest_missing_product",
                        &p.id,
                        "every reference product needs a source manifest",
                    );
                }
            }
        }
        Err(e) => report.error("manifest_file", &lock.source_manifest_path, e),
    }
    let mut features = BTreeMap::new();
    for f in &catalog.features {
        if f.id.trim().is_empty() || features.insert(f.id.as_str(), f).is_some() {
            report.error(
                "duplicate_feature",
                &f.id,
                "feature IDs must be nonempty and unique",
            );
        }
        if f.title.trim().is_empty() || f.source_ids.is_empty() {
            report.error(
                "feature_metadata",
                &f.id,
                "a feature needs a title and official sources",
            );
        }
        if ![
            "0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9",
        ]
        .contains(&f.milestone.as_str())
        {
            report.error(
                "milestone",
                &f.id,
                "feature must belong to an implementation milestone from 0.1 through 0.9",
            );
        }
        if f.review == Review::Pending {
            report.pending_features += 1;
        }
        for id in &f.source_ids {
            match sources.get(id.as_str()) {
                Some(s) if s.decision == Decision::Include && s.feature_ids.contains(&f.id) => {}
                _ => report.error(
                    "feature_source",
                    &f.id,
                    format!("source {id} must include this feature in both directions"),
                ),
            }
        }
        match read::<Case>(root, &f.case_path) {
            Ok(case) => {
                if case.schema_version != 1 || case.feature_id != f.id {
                    report.error(
                        "case_identity",
                        &f.id,
                        "case version and feature ID must match",
                    );
                }
                if !case.fixture.is_object()
                    || case.steps.is_empty()
                    || case.steps.iter().any(|s| s.trim().is_empty())
                    || case.assertions.is_empty()
                    || case.evidence.is_empty()
                    || case.evidence.iter().any(|s| s.trim().is_empty())
                {
                    report.error(
                        "case_contract",
                        &f.id,
                        "case needs a fixture, actions, assertions and evidence requirements",
                    );
                }
                for a in &case.assertions {
                    if a.target.trim().is_empty()
                        || a.expected.is_null()
                        || a.absolute_tolerance
                            .is_some_and(|n| !n.is_finite() || n < 0.0)
                    {
                        report.error(
                            "case_assertion",
                            &f.id,
                            "assertions need a target, expected value and valid tolerance",
                        );
                    }
                    if a.absolute_tolerance.is_some() && !a.expected.is_number() {
                        report.error(
                            "case_tolerance",
                            &f.id,
                            "a numeric tolerance requires a numeric expected value",
                        );
                    }
                }
            }
            Err(e) => report.error("case_file", &f.id, e),
        }
    }
    for s in &inventory.sources {
        for id in &s.feature_ids {
            match features.get(id.as_str()) {
                Some(f) if f.source_ids.contains(&s.id) => {}
                _ => report.error(
                    "source_feature",
                    &s.id,
                    format!("feature {id} must exist and refer back to this source"),
                ),
            }
        }
    }
    report.structurally_valid = report.problems.is_empty();
    report.baseline_ready = report.structurally_valid
        && !inventory.sources.is_empty()
        && !catalog.features.is_empty()
        && report.pending_sources == 0
        && report.pending_features == 0
        && report.uncovered_sources == 0
        && report.unverified_builds.is_empty()
        && report.incomplete_products.is_empty();
    Ok(report)
}

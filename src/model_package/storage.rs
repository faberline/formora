use super::*;
use std::{
    fs,
    io::{self, Write},
    path::Path,
};

fn read_regular(path: &Path) -> io::Result<Vec<u8>> {
    let metadata = fs::symlink_metadata(path)?;
    if !metadata.file_type().is_file() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "Package inputs must be regular files, not links or directories",
        ));
    }
    fs::read(path)
}

fn write_new(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut options = fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(path)?;
    file.write_all(bytes)?;
    file.sync_all()
}

/// Create an owned package only. No active model pointer or game save is changed.
/// On an I/O failure a new incomplete output may remain for inspection.
/// It is never returned as an adopted model and no existing path is removed.
pub fn import(request: ImportRequest) -> Receipt {
    match execute(request) {
        Ok(imported) => Receipt::Imported(Box::new(imported)),
        Err(error) => Receipt::Failed(error),
    }
}

fn execute(request: ImportRequest) -> Result<Imported, Failure> {
    if request.manifest.as_os_str().is_empty() || request.output.as_os_str().is_empty() {
        return Err(Failure::new(
            ErrorCode::InvalidRequest,
            Stage::Request,
            "Manifest and new output paths must not be empty",
        ));
    }
    if !valid_hash(&request.expected_manifest_sha256) {
        return Err(Failure::new(
            ErrorCode::InvalidRequest,
            Stage::Request,
            "Expected manifest hash must be 64 lowercase hexadecimal digits",
        ));
    }
    let manifest_bytes = read_regular(&request.manifest).map_err(|error| {
        Failure::new(
            if error.kind() == io::ErrorKind::NotFound {
                ErrorCode::ManifestMissing
            } else {
                ErrorCode::IoError
            },
            Stage::ReadManifest,
            error.to_string(),
        )
    })?;
    let (_, manifest_hash) =
        validate::parse_manifest(&manifest_bytes, &request.expected_manifest_sha256)?;
    let scene_path = request
        .manifest
        .parent()
        .unwrap_or(Path::new("."))
        .join("model.scene.json");
    let scene_bytes = read_regular(&scene_path).map_err(|error| {
        let mut failure = Failure::new(
            if error.kind() == io::ErrorKind::NotFound {
                ErrorCode::SceneMissing
            } else {
                ErrorCode::IoError
            },
            Stage::ReadScene,
            error.to_string(),
        );
        failure.observed_manifest_sha256 = Some(manifest_hash.clone());
        failure
    })?;
    let package = validate_bytes(
        &manifest_bytes,
        &request.expected_manifest_sha256,
        &scene_bytes,
    )?;
    let io_failure = |stage, error: io::Error| {
        let mut failure = Failure::new(ErrorCode::IoError, stage, error.to_string());
        failure.observed_manifest_sha256 = Some(package.manifest_sha256.clone());
        failure.observed_scene_sha256 = Some(package.scene_sha256.clone());
        failure
    };
    let builder = {
        #[cfg(unix)]
        {
            use std::os::unix::fs::DirBuilderExt;
            let mut builder = fs::DirBuilder::new();
            builder.mode(0o700);
            builder
        }
        #[cfg(not(unix))]
        {
            fs::DirBuilder::new()
        }
    };
    // create_dir is the exclusive reservation. Never rename over an existing directory.
    builder.create(&request.output).map_err(|error| {
        let mut failure = io_failure(
            Stage::StageOutput,
            io::Error::new(error.kind(), error.to_string()),
        );
        if error.kind() == io::ErrorKind::AlreadyExists {
            failure.error.code = ErrorCode::OutputExists;
        }
        failure
    })?;
    let saved_location = request
        .output
        .canonicalize()
        .map_err(|error| io_failure(Stage::StageOutput, error))?;
    write_new(
        &saved_location.join("model.scene.json"),
        &package.scene_bytes,
    )
    .map_err(|error| io_failure(Stage::SaveModel, error))?;
    // Publish the manifest after the exact source bytes have been synced.
    write_new(
        &saved_location.join("manifest.json"),
        &package.manifest_bytes,
    )
    .map_err(|error| io_failure(Stage::SaveModel, error))?;
    Ok(Imported {
        receipt_schema_version: 1,
        ok: Flag,
        manifest_sha256: package.manifest_sha256,
        scene_sha256: package.scene_sha256,
        scene_profile: package.manifest.scene_profile,
        producer_commit: package.manifest.producer_commit,
        validator_revision: validator_revision(),
        roots: package.manifest.roots,
        meters_per_unit: package.manifest.meters_per_unit,
        up_axis: package.manifest.up_axis,
        coordinate_system: package.manifest.coordinate_system,
        counts: package.counts,
        saved_location,
        conversion_report: Vec::new(),
        loss_report: Vec::new(),
    })
}

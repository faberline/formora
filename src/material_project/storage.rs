use super::*;
use std::{
    collections::BTreeMap,
    fs,
    io::{self, Write},
    path::Path,
};

fn read_file(path: &Path, missing: ErrorCode, stage: &str) -> Result<Vec<u8>, Failure> {
    let fail = |e: io::Error| {
        Failure::new(
            if e.kind() == io::ErrorKind::NotFound {
                missing
            } else {
                ErrorCode::IoError
            },
            stage,
            e,
        )
    };
    let meta = fs::symlink_metadata(path).map_err(fail)?;
    if !meta.file_type().is_file() {
        return Err(Failure::new(
            ErrorCode::InvalidPath,
            stage,
            "Expected a regular file, not a link or directory",
        ));
    }
    fs::read(path).map_err(fail)
}

fn load(request: &InspectRequest) -> Result<PreparedProject, Failure> {
    if request.project.as_os_str().is_empty() || !valid_hash(&request.expected_project_sha256) {
        return Err(Failure::new(
            ErrorCode::InvalidRequest,
            "request",
            "Require project path and lowercase SHA-256",
        ));
    }
    let bytes = read_file(&request.project, ErrorCode::ProjectMissing, "read_project")?;
    let observed = sha256(&bytes);
    let result = (|| {
        let project = validate::parse_project(&bytes, &request.expected_project_sha256)?;
        let root = request
            .project
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new("."))
            .canonicalize()
            .map_err(|e| Failure::new(ErrorCode::IoError, "read_project", e))?;
        let mut files = BTreeMap::new();
        for (name, missing) in
            std::iter::once((project.scene.path.as_str(), ErrorCode::SceneMissing)).chain(
                project
                    .images
                    .values()
                    .map(|i| (i.path.as_str(), ErrorCode::ImageMissing)),
            )
        {
            let mut path = root.clone();
            let parts: Vec<_> = name.split('/').collect();
            for (index, part) in parts.iter().enumerate() {
                path.push(part);
                let meta = fs::symlink_metadata(&path).map_err(|e| {
                    Failure::new(
                        if e.kind() == io::ErrorKind::NotFound {
                            missing
                        } else {
                            ErrorCode::IoError
                        },
                        "read_resource",
                        e,
                    )
                })?;
                if meta.file_type().is_symlink() || (index + 1 < parts.len() && !meta.is_dir()) {
                    return Err(Failure::new(
                        ErrorCode::InvalidPath,
                        "read_resource",
                        "Resource components must stay inside the project without links",
                    ));
                }
            }
            let canonical = path
                .canonicalize()
                .map_err(|e| Failure::new(ErrorCode::IoError, "read_resource", e))?;
            if !canonical.starts_with(&root) {
                return Err(Failure::new(
                    ErrorCode::InvalidPath,
                    "read_resource",
                    "Resource is outside the project",
                ));
            }
            files.insert(name.into(), read_file(&path, missing, "read_resource")?);
        }
        validate_bytes(&bytes, &request.expected_project_sha256, &files)
    })();
    result.map_err(|mut error: Failure| {
        error.observed_project_sha256 = Some(observed);
        error
    })
}

fn receipt(result: Result<Success, Failure>) -> Receipt {
    match result {
        Ok(s) => Receipt::Success(Box::new(s)),
        Err(e) => Receipt::Failure(e),
    }
}

pub fn inspect(request: InspectRequest) -> Receipt {
    receipt(load(&request).map(|p| p.inspect()))
}

pub fn sample(request: SampleRequest) -> Receipt {
    receipt(
        load(&InspectRequest {
            project: request.project,
            expected_project_sha256: request.expected_project_sha256,
        })
        .and_then(|p| p.samples(&request.samples)),
    )
}

fn create_dir(path: &Path) -> io::Result<()> {
    let builder = {
        #[cfg(unix)]
        {
            use std::os::unix::fs::DirBuilderExt;
            let mut b = fs::DirBuilder::new();
            b.mode(0o700);
            b
        }
        #[cfg(not(unix))]
        {
            fs::DirBuilder::new()
        }
    };
    builder.create(path)
}

fn write_new(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut options = fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut f = options.open(path)?;
    f.write_all(bytes)?;
    f.sync_all()
}

/// Saves a NEW owned texture project. Never changes a scene/game save or deletes output.
/// An I/O failure may leave a new incomplete directory; no success receipt is returned.
pub fn import(request: ImportRequest) -> Receipt {
    receipt((|| {
        if request.output.as_os_str().is_empty() {
            return Err(Failure::new(
                ErrorCode::InvalidRequest,
                "request",
                "New output path must not be empty",
            ));
        }
        let p = load(&InspectRequest {
            project: request.project,
            expected_project_sha256: request.expected_project_sha256,
        })?;
        create_dir(&request.output).map_err(|e| {
            Failure::new(
                if e.kind() == io::ErrorKind::AlreadyExists {
                    ErrorCode::OutputExists
                } else {
                    ErrorCode::IoError
                },
                "stage_output",
                e,
            )
        })?;
        let out = request
            .output
            .canonicalize()
            .map_err(|e| Failure::new(ErrorCode::IoError, "save", e))?;
        let io_fail = |e| Failure::new(ErrorCode::IoError, "save", e);
        let mut made = std::collections::BTreeSet::new();
        for (name, bytes) in &p.files {
            let mut parent = out.clone();
            let components: Vec<_> = name.split('/').collect();
            for component in &components[..components.len() - 1] {
                parent.push(component);
                if made.insert(parent.clone()) {
                    create_dir(&parent).map_err(io_fail)?;
                }
            }
            write_new(&out.join(name), bytes).map_err(io_fail)?;
        }
        // The descriptor is published last, after all exact source/image bytes are synced.
        write_new(&out.join("project.json"), &p.project_bytes).map_err(io_fail)?;
        let mut result = p.inspect();
        result.operation = Operation::Import;
        result.saved_location = Some(out);
        Ok(result)
    })())
}

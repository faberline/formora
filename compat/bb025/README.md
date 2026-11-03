# Pinned native source compatibility dependency

This directory contains all 54 `src` files from
`bb025ce17432ba0419008d0cd794222127e7ff92`, without Rust source patches.
`PROVENANCE.json` records each SHA-256 and both Cargo manifest identities.
Original source headers remain intact.

`Cargo.upstream.toml` is unchanged. `Cargo.toml` renames the package to avoid
a local lockfile collision. It keeps the original library name for upstream references.
`source_inputs.rs` includes all source bytes for pure provenance checks and validator identity.

The root uses this as an excluded path dependency with default features disabled.
It calls the complete native scene validator. It does not run the old agent/CLI/window.
The original repository's baseline and test datasets are not copied here.
Root tests do not claim to rerun those upstream suites.
Use the original frozen source and evidence for their acceptance.

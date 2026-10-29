//! Formora's source-backed acceptance contracts.
//!
//! A valid catalog is not proof that any product capability works.
pub mod agent;
pub mod baseline;
mod json;
pub mod mesh;
#[cfg(feature = "preview")]
pub mod preview;
pub mod rotation;
pub mod scene;
pub mod session;
pub mod transforms;

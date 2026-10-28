//! Formora's source-backed acceptance contracts.
//!
//! A valid catalog is not proof that any product capability works.
pub mod agent;
pub mod baseline;
#[cfg(feature = "preview")]
pub mod preview;
pub mod scene;
pub mod session;

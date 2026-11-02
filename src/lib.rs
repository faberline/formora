//! Formora's source-backed acceptance contracts.
//!
//! A valid catalog is not proof that any product capability works.
pub mod agent;
pub mod baseline;
#[cfg(feature = "headless")]
#[path = "preview/math.rs"]
pub mod geometry;
#[cfg(feature = "headless")]
pub mod headless;
mod json;
pub mod mesh;
pub mod objects;
#[cfg(feature = "preview")]
pub mod preview;
pub mod rotation;
pub mod scene;
pub mod session;
pub mod transforms;
pub mod usd;

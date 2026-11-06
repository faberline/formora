//! Saved delta channels follow the normal object's rotation mode.
use crate::rotation::{Channels, RotationAngles, TransformRotation};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Delta {
    pub translation: [f64; 3],
    pub euler: [f64; 3],
    /// Actual raw channels in W/X/Y/Z order, including inactive values.
    pub quaternion_wxyz: [f64; 4],
    pub scale: [f64; 3],
}

impl Default for Delta {
    fn default() -> Self {
        Self {
            translation: [0.; 3],
            euler: [0.; 3],
            quaternion_wxyz: [1., 0., 0., 0.],
            scale: [1.; 3],
        }
    }
}

impl Delta {
    pub fn is_identity(&self) -> bool {
        let identity = Self::default();
        self.values()
            .zip(identity.values())
            .all(|(a, b)| a.to_bits() == b.to_bits())
    }

    fn values(&self) -> impl Iterator<Item = &f64> {
        self.translation
            .iter()
            .chain(&self.euler)
            .chain(&self.quaternion_wxyz)
            .chain(&self.scale)
    }

    pub(crate) fn valid(&self) -> bool {
        self.values().all(|v| v.is_finite())
    }

    pub(super) fn rotation(self, normal: TransformRotation) -> TransformRotation {
        TransformRotation::Authored(RotationAngles::Channels {
            channels: Channels {
                mode: Channels::from_rotation(normal).mode,
                euler: self.euler,
                quaternion_wxyz: self.quaternion_wxyz,
                // The source public path has no authored delta axis-angle.
                axis_angle: [0., 0., 1., 0.],
            },
        })
    }
}

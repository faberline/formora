// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! Stored authoring modes with one physical quaternion interpretation.
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "lowercase")]
pub enum EulerOrder {
    #[default]
    Xyz,
    Xzy,
    Yxz,
    Yzx,
    Zxy,
    Zyx,
}
impl EulerOrder {
    pub(crate) fn axes(self) -> ([usize; 3], bool) {
        match self {
            Self::Xyz => ([0, 1, 2], false),
            Self::Xzy => ([0, 2, 1], true),
            Self::Yxz => ([1, 0, 2], true),
            Self::Yzx => ([1, 2, 0], false),
            Self::Zxy => ([2, 0, 1], false),
            Self::Zyx => ([2, 1, 0], true),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum RotationAngles {
    Euler {
        angles: [f64; 3],
        #[serde(default)]
        order: EulerOrder,
    },
    AxisAngle {
        axis: [f64; 3],
        radians: f64,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(untagged)]
pub enum TransformRotation {
    /// The legacy x/y/z/w unit-quaternion representation.
    Quaternion([f64; 4]),
    Authored(RotationAngles),
}
impl Default for TransformRotation {
    fn default() -> Self {
        Self::Quaternion([0., 0., 0., 1.])
    }
}
impl From<[f64; 4]> for TransformRotation {
    fn from(value: [f64; 4]) -> Self {
        Self::Quaternion(value)
    }
}
impl TransformRotation {
    pub fn valid(self) -> bool {
        match self {
            Self::Quaternion(q) => {
                q.iter().all(|v| v.is_finite())
                    && (q.iter().map(|v| v * v).sum::<f64>() - 1.).abs() <= 1e-6
            }
            Self::Authored(RotationAngles::Euler { angles, .. }) => {
                angles.iter().all(|v| v.is_finite())
            }
            Self::Authored(RotationAngles::AxisAngle { axis, radians }) => {
                radians.is_finite()
                    && axis.iter().all(|v| v.is_finite())
                    && axis.iter().any(|v| *v != 0.)
            }
        }
    }

    /// Resolve the authored physical pose. Callers validate scene data first.
    pub fn quaternion(self) -> [f64; 4] {
        match self {
            Self::Quaternion(q) => q,
            Self::Authored(RotationAngles::Euler { angles, order }) => {
                let ([i, j, k], parity) = order.axes();
                let (si, ci) = (angles[i] * 0.5).sin_cos();
                let (sj, cj) = (angles[j] * if parity { -0.5 } else { 0.5 }).sin_cos();
                let (sh, ch) = (angles[k] * 0.5).sin_cos();
                let (cc, cs, sc, ss) = (ci * ch, ci * sh, si * ch, si * sh);
                let mut q = [0.; 4];
                q[i] = cj * sc - sj * cs;
                q[j] = cj * ss + sj * cc;
                q[k] = cj * cs - sj * sc;
                q[3] = cj * cc + sj * ss;
                if parity {
                    q[j] = -q[j];
                }
                q
            }
            Self::Authored(RotationAngles::AxisAngle { axis, radians }) => {
                // Scaling first keeps finite, nonzero axes usable across f64 range.
                let scale = axis.iter().map(|v| v.abs()).fold(0., f64::max);
                let axis = axis.map(|v| v / scale);
                let length = axis.iter().map(|v| v * v).sum::<f64>().sqrt();
                let (s, c) = (radians * 0.5).sin_cos();
                [
                    axis[0] / length * s,
                    axis[1] / length * s,
                    axis[2] / length * s,
                    c,
                ]
            }
        }
    }
}

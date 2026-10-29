// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! Stored authoring modes with one physical quaternion interpretation.
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

pub(crate) mod source;

/// Authored representation, independent of its evaluated physical pose.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Mode {
    Xyz,
    Xzy,
    Yxz,
    Yzx,
    Zxy,
    Zyx,
    Quaternion,
    AxisAngle,
}
impl Mode {
    pub fn euler_order(self) -> Option<EulerOrder> {
        Some(match self {
            Self::Xyz => EulerOrder::Xyz,
            Self::Xzy => EulerOrder::Xzy,
            Self::Yxz => EulerOrder::Yxz,
            Self::Yzx => EulerOrder::Yzx,
            Self::Zxy => EulerOrder::Zxy,
            Self::Zyx => EulerOrder::Zyx,
            _ => return None,
        })
    }
}
impl From<EulerOrder> for Mode {
    fn from(value: EulerOrder) -> Self {
        match value {
            EulerOrder::Xyz => Self::Xyz,
            EulerOrder::Xzy => Self::Xzy,
            EulerOrder::Yxz => Self::Yxz,
            EulerOrder::Yzx => Self::Yzx,
            EulerOrder::Zxy => Self::Zxy,
            EulerOrder::Zyx => Self::Zyx,
        }
    }
}

/// Actual active and inactive source channels. Quaternion order is W/X/Y/Z.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Channels {
    pub mode: Mode,
    pub euler: [f64; 3],
    pub quaternion_wxyz: [f64; 4],
    /// Angle in radians, then X/Y/Z axis. The stored axis need not be unit.
    pub axis_angle: [f64; 4],
}
impl Channels {
    pub(crate) fn from_rotation(rotation: TransformRotation) -> Self {
        let mut result = Self {
            mode: Mode::Xyz,
            euler: [0.; 3],
            quaternion_wxyz: [1., 0., 0., 0.],
            axis_angle: [0., 0., 1., 0.],
        };
        match rotation {
            TransformRotation::Authored(RotationAngles::Channels { channels }) => return channels,
            TransformRotation::Quaternion([x, y, z, w]) => {
                result.mode = Mode::Quaternion;
                result.quaternion_wxyz = [w, x, y, z];
            }
            TransformRotation::Authored(RotationAngles::Euler { angles, order }) => {
                result.mode = order.into();
                result.euler = angles;
            }
            TransformRotation::Authored(RotationAngles::AxisAngle { axis, radians }) => {
                result.mode = Mode::AxisAngle;
                result.axis_angle = [radians, axis[0], axis[1], axis[2]];
            }
        }
        result
    }
    pub fn valid(self) -> bool {
        self.euler
            .iter()
            .chain(&self.quaternion_wxyz)
            .chain(&self.axis_angle)
            .all(|v| v.is_finite())
    }
    pub(crate) fn matrix(self) -> crate::scene::Result<[[f32; 3]; 3]> {
        if let Some(order) = self.mode.euler_order() {
            source::finite(&self.euler)?;
            Ok(crate::transforms::euler_matrix(
                self.euler.map(|v| v as f32),
                order,
            ))
        } else if self.mode == Mode::Quaternion {
            source::quaternion_matrix(self.quaternion_wxyz)
        } else {
            crate::transforms::single_rotation(TransformRotation::Authored(
                RotationAngles::AxisAngle {
                    axis: [self.axis_angle[1], self.axis_angle[2], self.axis_angle[3]],
                    radians: self.axis_angle[0],
                },
            ))
        }
    }
    /// Clear only the active representation, as the native cursor setter does.
    pub(crate) fn clear(&mut self) {
        match self.mode {
            Mode::Quaternion => self.quaternion_wxyz = [1., 0., 0., 0.],
            Mode::AxisAngle => self.axis_angle = [0., 0., 1., 0.],
            _ => self.euler = [0.; 3],
        }
    }
    fn quaternion(self) -> [f64; 4] {
        if let Some(order) = self.mode.euler_order() {
            TransformRotation::Authored(RotationAngles::Euler {
                angles: self.euler,
                order,
            })
            .quaternion()
        } else if self.mode == Mode::AxisAngle {
            let axis = [self.axis_angle[1], self.axis_angle[2], self.axis_angle[3]];
            if axis.iter().all(|v| *v == 0.) {
                return [0., 0., 0., 1.];
            }
            TransformRotation::Authored(RotationAngles::AxisAngle {
                axis,
                radians: self.axis_angle[0],
            })
            .quaternion()
        } else {
            let scale = self
                .quaternion_wxyz
                .iter()
                .map(|v| v.abs())
                .fold(0., f64::max);
            if scale == 0. {
                return [1., 0., 0., 0.];
            }
            let q = self.quaternion_wxyz.map(|v| v / scale);
            let length = q.iter().map(|v| v * v).sum::<f64>().sqrt();
            [q[1] / length, q[2] / length, q[3] / length, q[0] / length]
        }
    }
}

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
    Channels {
        channels: Channels,
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
            Self::Authored(RotationAngles::Channels { channels }) => channels.valid(),
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
            Self::Authored(RotationAngles::Channels { channels }) => channels.quaternion(),
        }
    }
}

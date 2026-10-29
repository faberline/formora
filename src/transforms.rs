// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! Shared physical frames, with explicit authored precision boundaries.
use crate::rotation::{EulerOrder, RotationAngles, TransformRotation};
use crate::scene::{Result, Scene, SceneError, Transform};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

pub type Matrix = [[f64; 4]; 4];
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "lowercase")]
pub enum Precision {
    F32,
    #[default]
    F64,
}
impl Precision {
    pub fn is_default(&self) -> bool {
        *self == Self::F64
    }
}
fn error() -> SceneError {
    SceneError("physical transform exceeds its finite precision range".into())
}
fn f32_value(value: f64) -> Result<f32> {
    let v = value as f32;
    if v.is_finite() { Ok(v) } else { Err(error()) }
}
pub(crate) fn euler_matrix(angles: [f32; 3], order: EulerOrder) -> [[f32; 3]; 3] {
    let ([i, j, k], parity) = order.axes();
    let a = angles.map(|v| f64::from(if parity { -v } else { v }));
    let (si, ci) = a[i].sin_cos();
    let (sj, cj) = a[j].sin_cos();
    let (sh, ch) = a[k].sin_cos();
    let (cc, cs, sc, ss) = (ci * ch, ci * sh, si * ch, si * sh);
    let mut m = [[0.; 3]; 3];
    m[i][i] = (cj * ch) as f32;
    m[i][j] = (sj * sc - cs) as f32;
    m[i][k] = (sj * cc + ss) as f32;
    m[j][i] = (cj * sh) as f32;
    m[j][j] = (sj * ss + cc) as f32;
    m[j][k] = (sj * cs - sc) as f32;
    m[k][i] = -sj as f32;
    m[k][j] = (cj * si) as f32;
    m[k][k] = (cj * ci) as f32;
    m
}
fn single_rotation(rotation: TransformRotation) -> Result<[[f32; 3]; 3]> {
    Ok(match rotation {
        TransformRotation::Authored(RotationAngles::Euler { angles, order }) => euler_matrix(
            [
                f32_value(angles[0])?,
                f32_value(angles[1])?,
                f32_value(angles[2])?,
            ],
            order,
        ),
        TransformRotation::Quaternion(q) => {
            let mut q = [
                f32_value(q[3])?,
                f32_value(q[0])?,
                f32_value(q[1])?,
                f32_value(q[2])?,
            ];
            let length = (q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]).sqrt();
            if !length.is_finite() || length == 0. {
                return Err(error());
            }
            let inverse = 1. / length;
            for v in &mut q {
                *v *= inverse;
            }
            let [w, x, y, z] = q.map(|v| std::f64::consts::SQRT_2 * f64::from(v));
            [
                [
                    (1. - y * y - z * z) as f32,
                    (x * y - w * z) as f32,
                    (w * y + x * z) as f32,
                ],
                [
                    (w * z + x * y) as f32,
                    (1. - x * x - z * z) as f32,
                    (y * z - w * x) as f32,
                ],
                [
                    (x * z - w * y) as f32,
                    (w * x + y * z) as f32,
                    (1. - x * x - y * y) as f32,
                ],
            ]
        }
        TransformRotation::Authored(RotationAngles::AxisAngle { axis, radians }) => {
            let axis = [
                f32_value(axis[0])?,
                f32_value(axis[1])?,
                f32_value(axis[2])?,
            ];
            let radians = f32_value(radians)?;
            let length = axis.iter().map(|v| v * v).sum::<f32>();
            if !length.is_finite() {
                return Err(error());
            }
            if length <= 1e-35 {
                [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
            } else {
                let inverse = 1. / length.sqrt();
                let [x, y, z] = axis.map(|v| v * inverse);
                let (s, c) = radians.sin_cos();
                let t = 1. - c;
                [
                    [x * x * t + c, x * y * t - z * s, x * z * t + y * s],
                    [x * y * t + z * s, y * y * t + c, y * z * t - x * s],
                    [x * z * t - y * s, y * z * t + x * s, z * z * t + c],
                ]
            }
        }
    })
}
pub fn local(transform: &Transform) -> Result<Matrix> {
    let mut result = [[0.; 4]; 4];
    result[3][3] = 1.;
    if transform.precision == Precision::F32 {
        let rotation = single_rotation(transform.rotation)?;
        for i in 0..3 {
            result[i][3] = f64::from(f32_value(transform.translation[i])?);
            for j in 0..3 {
                result[i][j] = f64::from(rotation[i][j] * f32_value(transform.scale[j])?);
            }
        }
    } else {
        let q = transform.rotation.quaternion();
        let length = q.iter().map(|v| v * v).sum::<f64>().sqrt();
        let [x, y, z, w] = q.map(|v| v / length);
        let rotation = [
            [
                1. - 2. * (y * y + z * z),
                2. * (x * y - z * w),
                2. * (x * z + y * w),
            ],
            [
                2. * (x * y + z * w),
                1. - 2. * (x * x + z * z),
                2. * (y * z - x * w),
            ],
            [
                2. * (x * z - y * w),
                2. * (y * z + x * w),
                1. - 2. * (x * x + y * y),
            ],
        ];
        for i in 0..3 {
            result[i][3] = transform.translation[i];
            for j in 0..3 {
                result[i][j] = rotation[i][j] * transform.scale[j];
            }
        }
    }
    if result.iter().flatten().all(|v| v.is_finite()) {
        Ok(result)
    } else {
        Err(error())
    }
}
pub fn compose(parent: Matrix, local: Matrix, precision: Precision) -> Result<Matrix> {
    let result = std::array::from_fn(|r| {
        std::array::from_fn(|c| {
            if precision == Precision::F32 {
                let p = std::array::from_fn::<_, 4, _>(|k| {
                    (parent[r][k] as f32) * (local[k][c] as f32)
                });
                f64::from((p[0] + p[1]) + (p[2] + p[3]))
            } else {
                parent[r][0] * local[0][c]
                    + parent[r][1] * local[1][c]
                    + parent[r][2] * local[2][c]
                    + parent[r][3] * local[3][c]
            }
        })
    });
    if result.iter().flatten().all(|v| v.is_finite()) {
        Ok(result)
    } else {
        Err(error())
    }
}
pub fn world(scene: &Scene, id: &str) -> Result<Matrix> {
    let mut chain = Vec::new();
    let mut current = Some(id);
    while let Some(id) = current {
        let entity = scene
            .entities
            .get(id)
            .ok_or_else(|| SceneError(format!("unknown physical transform entity: {id}")))?;
        if chain.len() > scene.entities.len() {
            return Err(SceneError("physical transform parent cycle".into()));
        }
        chain.push((local(&entity.transform)?, entity.transform.precision));
        current = entity.parent.as_deref();
    }
    let mut result = std::array::from_fn(|r| std::array::from_fn(|c| if r == c { 1. } else { 0. }));
    for (matrix, precision) in chain.into_iter().rev() {
        result = compose(result, matrix, precision)?;
    }
    Ok(result)
}
pub fn point(matrix: Matrix, point: [f64; 3], precision: Precision) -> Result<[f64; 3]> {
    let result = if precision == Precision::F32 {
        let p = [
            f32_value(point[0])?,
            f32_value(point[1])?,
            f32_value(point[2])?,
            1.,
        ];
        matrix.map(|row| {
            f64::from(
                (f64::from(row[0] as f32 * p[0])
                    + f64::from(row[1] as f32 * p[1])
                    + f64::from(row[2] as f32 * p[2])
                    + f64::from(row[3] as f32 * p[3])) as f32,
            )
        })[..3]
            .try_into()
            .unwrap()
    } else {
        std::array::from_fn(|r| {
            matrix[r][0] * point[0]
                + matrix[r][1] * point[1]
                + matrix[r][2] * point[2]
                + matrix[r][3]
        })
    };
    if result.iter().all(|v| v.is_finite()) {
        Ok(result)
    } else {
        Err(error())
    }
}

// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
use super::{IDENTITY, Matrix, Vector, dot, math};
use crate::rotation::{EulerOrder, RotationAngles, TransformRotation};
use crate::scene::{Entity, Result, Scene, SceneError};

fn overflow() -> SceneError {
    SceneError("gimbal orientation arithmetic exceeded finite f32 range".into())
}
fn checked(v: Vector) -> Result<Vector> {
    if v.iter().all(|v| v.is_finite()) {
        Ok(v)
    } else {
        Err(overflow())
    }
}
fn unit(v: Vector) -> Result<Vector> {
    let d = dot(v, v);
    if !d.is_finite() {
        return Err(overflow());
    }
    if d > 1e-35 {
        checked(v.map(|v| v * (1. / d.sqrt())))
    } else {
        Ok([0.; 3])
    }
}
fn cross(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[(i + 1) % 3] * b[(i + 2) % 3] - a[(i + 2) % 3] * b[(i + 1) % 3])
}
fn euler_matrix(angles: Vector, order: EulerOrder) -> Matrix {
    let ([i, j, k], parity) = order.axes();
    let angles = angles.map(|v| f64::from(if parity { -v } else { v }));
    let (si, ci) = angles[i].sin_cos();
    let (sj, cj) = angles[j].sin_cos();
    let (sh, ch) = angles[k].sin_cos();
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
fn euler(angles: [f64; 3], order: EulerOrder) -> Result<Matrix> {
    let mut angles = checked(angles.map(|v| v as f32))?;
    let ([i, j, k], _) = order.axes();
    let first = euler_matrix(angles, order);
    angles[i] = 0.;
    let second = euler_matrix(angles, order);
    Ok(std::array::from_fn(|r| {
        std::array::from_fn(|c| {
            if c == i {
                first[r][c]
            } else if c == j {
                second[r][c]
            } else if r == k {
                1.
            } else {
                0.
            }
        })
    }))
}
fn axis_quaternion(axis: Vector, radians: f32) -> Result<[f32; 4]> {
    let axis = unit(axis)?;
    if axis == [0.; 3] {
        return Ok([1., 0., 0., 0.]);
    }
    let (s, c) = (0.5 * radians).sin_cos();
    Ok([c, axis[0] * s, axis[1] * s, axis[2] * s])
}
fn rotate(q: [f32; 4], v: Vector) -> Result<Vector> {
    let t0 = -q[1] * v[0] - q[2] * v[1] - q[3] * v[2];
    let t1 = q[0] * v[0] + q[2] * v[2] - q[3] * v[1];
    let t2 = q[0] * v[1] + q[3] * v[0] - q[1] * v[2];
    let v = [t1, t2, q[0] * v[2] + q[1] * v[1] - q[2] * v[0]];
    checked([
        t0 * (-q[1]) + v[0] * q[0] - v[1] * q[3] + v[2] * q[2],
        t0 * (-q[2]) + v[1] * q[0] - v[2] * q[1] + v[0] * q[3],
        t0 * (-q[3]) + v[2] * q[0] - v[0] * q[2] + v[1] * q[1],
    ])
}
fn axis_angle(axis: [f64; 3], radians: f64) -> Result<Matrix> {
    let axis = checked(axis.map(|v| v as f32))?;
    let radians = radians as f32;
    if !radians.is_finite() {
        return Err(overflow());
    }
    let cross_vec = [axis[1], axis[2], axis[0]];
    let x = rotate(
        axis_quaternion(axis, radians)?,
        unit(cross(cross_vec, axis))?,
    )?;
    let y = rotate(axis_quaternion(axis, std::f32::consts::FRAC_PI_2)?, x)?;
    let columns = [unit(x)?, unit(y)?, unit(axis)?];
    Ok(std::array::from_fn(|r| {
        std::array::from_fn(|c| columns[c][r])
    }))
}
pub(super) fn basis(scene: &Scene, target: &Entity) -> Result<Matrix> {
    let parent = if let Some(parent) = &target.parent {
        let world = math::world(scene, parent)?;
        let columns = (0..3)
            .map(|c| unit(std::array::from_fn(|r| world[r][c] as f32)))
            .collect::<Result<Vec<_>>>()?;
        std::array::from_fn(|r| std::array::from_fn(|c| columns[c][r]))
    } else {
        IDENTITY
    };
    let local = match target.transform.rotation {
        TransformRotation::Quaternion(_) => return Ok(parent),
        TransformRotation::Authored(RotationAngles::Euler { angles, order }) => {
            euler(angles, order)?
        }
        TransformRotation::Authored(RotationAngles::AxisAngle { axis, radians }) => {
            axis_angle(axis, radians)?
        }
    };
    let result = math::multiply(parent, local);
    for row in result {
        checked(row)?;
    }
    Ok(result)
}

// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! Pinned source arithmetic on evaluated copies, never normalized stored data.
use super::{Channels, EulerOrder, Mode};
use crate::scene::{Result, SceneError};
type Matrix = [[f32; 3]; 3];

pub(crate) fn finite(values: &[f64]) -> Result<()> {
    if values
        .iter()
        .all(|v| v.is_finite() && (*v as f32).is_finite())
    {
        Ok(())
    } else {
        Err(SceneError(
            "rotation exceeds finite source arithmetic".into(),
        ))
    }
}
fn checked<const N: usize>(values: [f32; N]) -> Result<[f32; N]> {
    finite(&values.map(f64::from))?;
    Ok(values)
}
fn normalize_quaternion(q: &mut [f32; 4]) -> Result<()> {
    let length = (q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]).sqrt();
    checked([length])?;
    if length == 0. {
        *q = [0., 1., 0., 0.];
    } else {
        let factor = 1. / length;
        *q = q.map(|v| v * factor);
    }
    checked(*q)?;
    Ok(())
}
pub(crate) fn quaternion_matrix(values: [f64; 4]) -> Result<Matrix> {
    finite(&values)?;
    let mut q = values.map(|v| v as f32);
    normalize_quaternion(&mut q)?;
    let [w, x, y, z] = q.map(|v| std::f64::consts::SQRT_2 * f64::from(v));
    Ok([
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
    ])
}
fn normalize_columns(m: &mut Matrix) {
    for c in 0..3 {
        let d = m[0][c] * m[0][c] + m[1][c] * m[1][c] + m[2][c] * m[2][c];
        if d > 1e-35 {
            let factor = 1. / d.sqrt();
            for row in &mut *m {
                row[c] *= factor;
            }
        } else {
            for row in &mut *m {
                row[c] = 0.;
            }
        }
    }
}
// Host atan2f differs by one f32 step for the same pinned matrix on glibc and
// Darwin (including the positive pi/2 gimbal case). Evaluate the same f32 input
// in f64, then quantize once to the source's stored f32 channel precision.
fn source_atan2(y: f32, x: f32) -> f32 {
    f64::from(y).atan2(f64::from(x)) as f32
}
/// Mat3-to-Euler uses normalized columns and the smaller L1 solution.
pub(crate) fn euler(mut m: Matrix, order: EulerOrder) -> [f32; 3] {
    normalize_columns(&mut m);
    let ([i, j, k], parity) = order.axes();
    let cy = m[i][i].hypot(m[j][i]);
    let (mut a, mut b) = ([0.; 3], [0.; 3]);
    if cy > 0.0000375 {
        a[i] = source_atan2(m[k][j], m[k][k]);
        a[j] = source_atan2(-m[k][i], cy);
        a[k] = source_atan2(m[j][i], m[i][i]);
        b[i] = source_atan2(-m[k][j], -m[k][k]);
        b[j] = source_atan2(-m[k][i], -cy);
        b[k] = source_atan2(-m[j][i], -m[i][i]);
    } else {
        a[i] = source_atan2(-m[j][k], m[j][j]);
        a[j] = source_atan2(-m[k][i], cy);
        a[k] = 0.;
        b = a;
    }
    if parity {
        a = a.map(|v| -v);
        b = b.map(|v| -v);
    }
    let sum = |v: [f32; 3]| v[0].abs() + v[1].abs() + v[2].abs();
    if sum(a) > sum(b) { b } else { a }
}
fn matrix_quaternion(mut m: Matrix, normalize: bool) -> Result<[f32; 4]> {
    for row in m {
        checked(row)?;
    }
    if normalize {
        normalize_columns(&mut m);
    }
    // Same determinant expansion as determinant_m3_array on column-major data.
    let det = m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2])
        - m[0][1] * (m[1][0] * m[2][2] - m[2][0] * m[1][2])
        + m[0][2] * (m[1][0] * m[2][1] - m[2][0] * m[1][1]);
    if !det.is_finite() {
        m = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]];
    } else if det < 0. {
        m = m.map(|r| r.map(|v| -v));
    }
    let (trace, component, negative) = if m[2][2] < 0. {
        if m[0][0] > m[1][1] {
            (1. + m[0][0] - m[1][1] - m[2][2], 1, m[2][1] < m[1][2])
        } else {
            (1. - m[0][0] + m[1][1] - m[2][2], 2, m[0][2] < m[2][0])
        }
    } else if m[0][0] < -m[1][1] {
        (1. - m[0][0] - m[1][1] + m[2][2], 3, m[1][0] < m[0][1])
    } else {
        (1. + m[0][0] + m[1][1] + m[2][2], 0, false)
    };
    let mut s = 2. * trace.sqrt();
    if negative {
        s = -s;
    }
    let value = 0.25 * s;
    s = 1. / s;
    let mut q = match component {
        1 => [
            (m[2][1] - m[1][2]) * s,
            value,
            (m[1][0] + m[0][1]) * s,
            (m[0][2] + m[2][0]) * s,
        ],
        2 => [
            (m[0][2] - m[2][0]) * s,
            (m[1][0] + m[0][1]) * s,
            value,
            (m[2][1] + m[1][2]) * s,
        ],
        3 => [
            (m[1][0] - m[0][1]) * s,
            (m[0][2] + m[2][0]) * s,
            (m[2][1] + m[1][2]) * s,
            value,
        ],
        _ => [
            value,
            (m[2][1] - m[1][2]) * s,
            (m[0][2] - m[2][0]) * s,
            (m[1][0] - m[0][1]) * s,
        ],
    };
    if trace == 1.
        && q.iter()
            .enumerate()
            .all(|(i, v)| i == component || *v == 0.)
    {
        q[component] = 1.;
    }
    let length = q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3];
    if (length - 1.).abs() >= 0.0002 * 3. {
        normalize_quaternion(&mut q)?;
    }
    checked(q)
}
fn matrix_axis_angle(m: Matrix) -> Result<[f32; 4]> {
    let q = matrix_quaternion(m, true)?;
    let half = q[0].acos();
    let mut sine = half.sin();
    if sine.abs() < 0.0005 {
        sine = 1.;
    }
    let mut axis = [q[1] / sine, q[2] / sine, q[3] / sine];
    if axis == [0.; 3] {
        axis[1] = 1.;
    }
    checked([half * 2., axis[0], axis[1], axis[2]])
}
pub(crate) fn assign(
    target: &mut Channels,
    cursor: Channels,
    basis: Matrix,
    unparented: bool,
    locks: [bool; 3],
    lock_w: bool,
) -> Result<()> {
    let direct = unparented && target.mode == cursor.mode;
    match target.mode {
        Mode::Quaternion => {
            let values = if direct {
                finite(&cursor.quaternion_wxyz)?;
                cursor.quaternion_wxyz.map(|v| v as f32)
            } else {
                matrix_quaternion(basis, false)?
            };
            for (i, locked) in [lock_w, locks[0], locks[1], locks[2]]
                .into_iter()
                .enumerate()
            {
                if !locked {
                    target.quaternion_wxyz[i] = f64::from(values[i]);
                }
            }
        }
        Mode::AxisAngle => {
            let values = if direct {
                finite(&cursor.axis_angle)?;
                cursor.axis_angle.map(|v| v as f32)
            } else {
                matrix_axis_angle(basis)?
            };
            for (i, locked) in [lock_w, locks[0], locks[1], locks[2]]
                .into_iter()
                .enumerate()
            {
                if !locked {
                    target.axis_angle[i] = f64::from(values[i]);
                }
            }
        }
        _ => {
            let values = if direct {
                finite(&cursor.euler)?;
                cursor.euler.map(|v| v as f32)
            } else {
                checked(euler(basis, target.mode.euler_order().unwrap()))?
            };
            for i in 0..3 {
                if !locks[i] {
                    target.euler[i] = f64::from(values[i]);
                }
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod cross_platform_tests {
    use super::*;
    #[test]
    fn gimbal_channels_keep_the_exact_frozen_source_float_bits() {
        let input: [f64; 4] = [0.5, 0.5, -0.5, 0.5];
        let matrix = quaternion_matrix(input).unwrap();
        let result = euler(matrix, EulerOrder::Xyz);
        assert_eq!(result.map(f32::to_bits), [0x3fc90fdb, 0xbfc90fdb, 0]);
        assert_eq!(source_atan2(1., -f32::EPSILON).to_bits(), 0x3fc90fdc);
        assert_eq!(source_atan2(1., 0.).to_bits(), 0x3fc90fdb);
    }
}

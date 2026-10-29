// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! Linear and affine inverse paths have distinct pinned source behavior.
use super::{IDENTITY, Matrix, Vector, dot};
use crate::scene::{Result, SceneError};
mod rank;
mod svd;

fn error() -> SceneError {
    SceneError("safe transform inverse arithmetic exceeded finite f32 range".into())
}
fn checked<const N: usize>(m: [[f32; N]; N]) -> Result<[[f32; N]; N]> {
    if m.iter().flatten().all(|v| v.is_finite()) {
        Ok(m)
    } else {
        Err(error())
    }
}
fn adjugate(m: Matrix) -> Result<Matrix> {
    checked(std::array::from_fn(|i| {
        std::array::from_fn(|j| {
            m[(j + 1) % 3][(i + 1) % 3] * m[(j + 2) % 3][(i + 2) % 3]
                - m[(j + 1) % 3][(i + 2) % 3] * m[(j + 2) % 3][(i + 1) % 3]
        })
    }))
}
fn regular(m: Matrix) -> Result<(Matrix, bool)> {
    checked(m)?;
    let adj = adjugate(m)?;
    let det = m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2])
        - m[0][1] * (m[1][0] * m[2][2] - m[2][0] * m[1][2])
        + m[0][2] * (m[1][0] * m[2][1] - m[2][0] * m[1][1]);
    if !det.is_finite() {
        return Err(error());
    }
    if det == 0. {
        return Ok((adj, false));
    }
    let reciprocal = 1. / det;
    Ok((checked(adj.map(|r| r.map(|v| v * reciprocal)))?, true))
}
pub(super) fn object(m: Matrix) -> Result<(Matrix, bool)> {
    let (inverse, invertible) = regular(m)?;
    if invertible {
        Ok((inverse, false))
    } else {
        Ok((svd::pseudoinverse(m, 200)?, true))
    }
}
/// The source normal path retains the adjugate when its ordinary inverse fails.
pub(super) fn normal(m: Matrix) -> Result<Matrix> {
    Ok(regular(m)?.0)
}

fn unit(v: Vector) -> Result<Vector> {
    let d = dot(v, v);
    if !d.is_finite() {
        return Err(error());
    }
    Ok(if d > 1e-35 {
        let inverse = 1. / d.sqrt();
        v.map(|v| v * inverse)
    } else {
        [0.; 3]
    })
}
fn cross(a: Vector, b: Vector) -> Vector {
    std::array::from_fn(|i| a[(i + 1) % 3] * b[(i + 2) % 3] - a[(i + 2) % 3] * b[(i + 1) % 3])
}
pub(super) fn columns(m: Matrix) -> Result<Matrix> {
    let cols = (0..3)
        .map(|c| unit(std::array::from_fn(|r| m[r][c])))
        .collect::<Result<Vec<_>>>()?;
    Ok(std::array::from_fn(|r| std::array::from_fn(|c| cols[c][r])))
}
pub(super) fn local_axes(m: Matrix) -> Result<Matrix> {
    let m = columns(m)?;
    let mut cols: Matrix = std::array::from_fn(|c| std::array::from_fn(|r| m[r][c]));
    let zero: Vec<_> = (0..3).filter(|i| cols[*i] == [0.; 3]).collect();
    if zero.is_empty() {
        return Ok(m);
    }
    if zero.len() == 1 {
        let i = zero[0];
        cols[i] = unit(cross(cols[(i + 1) % 3], cols[(i + 2) % 3]))?;
        if cols[i] != [0.; 3] {
            return checked(std::array::from_fn(|r| std::array::from_fn(|c| cols[c][r])));
        }
    } else if zero.len() == 2 {
        let i = (0..3)
            .find(|i| cols[*i] != [0.; 3])
            .expect("one nonzero axis");
        for j in [(i + 1) % 3, (i + 2) % 3] {
            cols[j][j] = 1.;
            let d = dot(cols[i], cols[i]);
            let factor = dot(cols[j], cols[i]) / d;
            cols[j] = unit(std::array::from_fn(|k| cols[j][k] - cols[i][k] * factor))?;
        }
        if zero.iter().all(|i| cols[*i] != [0.; 3]) {
            return checked(std::array::from_fn(|r| std::array::from_fn(|c| cols[c][r])));
        }
    }
    Ok(IDENTITY)
}

/// Production first tries the already verified pinned Eigen inverse.
pub(super) fn source_pivot(world: [[f32; 4]; 4], point: Vector) -> Result<Vector> {
    if let Ok(inverse) = crate::mesh::creation::inverse4::inverse(world) {
        let result = std::array::from_fn(|r| {
            inverse[r][0] * point[0]
                + inverse[r][1] * point[1]
                + inverse[r][2] * point[2]
                + inverse[r][3]
        });
        if result.iter().all(|v| v.is_finite()) {
            return Ok(result);
        }
        return Err(error());
    }
    pivot(world, point)
}

/// Source fallback operates on column-major storage and retains partial elimination.
pub(super) fn pivot(world: [[f32; 4]; 4], point: Vector) -> Result<Vector> {
    checked(world)?;
    let mut raw: [[f32; 4]; 4] = std::array::from_fn(|i| std::array::from_fn(|j| world[j][i]));
    let mut inverse: [[f32; 4]; 4] =
        std::array::from_fn(|i| std::array::from_fn(|j| if i == j { 1. } else { 0. }));
    for i in 0..4 {
        let mut max = raw[i][i].abs();
        let mut row = i;
        for (j, values) in raw.iter().enumerate().skip(i + 1) {
            if values[i].abs() > max {
                max = values[i].abs();
                row = j;
            }
        }
        if row != i {
            raw.swap(i, row);
            inverse.swap(i, row);
        }
        if raw[i][i] == 0. {
            break;
        }
        let divisor = f64::from(raw[i][i]);
        for k in 0..4 {
            raw[i][k] = (f64::from(raw[i][k]) / divisor) as f32;
            inverse[i][k] = (f64::from(inverse[i][k]) / divisor) as f32;
        }
        for j in 0..4 {
            if j == i {
                continue;
            }
            let factor = f64::from(raw[j][i]);
            for k in 0..4 {
                raw[j][k] -= (f64::from(raw[i][k]) * factor) as f32;
                inverse[j][k] -= (f64::from(inverse[i][k]) * factor) as f32;
            }
        }
        checked(raw)?;
        checked(inverse)?;
    }
    let result = std::array::from_fn(|r| {
        inverse[0][r] * point[0]
            + inverse[1][r] * point[1]
            + inverse[2][r] * point[2]
            + inverse[3][r]
    });
    if result.iter().all(|v| v.is_finite()) {
        Ok(result)
    } else {
        Err(error())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mesh::frame_math::multiply;
    fn near(a: Matrix, b: Matrix) {
        for r in 0..3 {
            for c in 0..3 {
                assert!((a[r][c] - b[r][c]).abs() <= 1e-6, "{a:?} != {b:?}");
            }
        }
    }
    fn transpose(m: Matrix) -> Matrix {
        std::array::from_fn(|r| std::array::from_fn(|c| m[c][r]))
    }
    #[test]
    fn regular_inverse_preserves_full_rank_scales_below_svd_cutoff() {
        let (inverse, singular) = object([[1e-9, 0., 0.], [0., 1., 0.], [0., 0., 1.]]).unwrap();
        assert!(!singular);
        assert!((inverse[0][0] * 1e-9 - 1.).abs() < 1e-6);
        near(
            multiply(inverse, [[1e-9, 0., 0.], [0., 1., 0.], [0., 0., 1.]]),
            IDENTITY,
        );
    }
    #[test]
    fn rank_zero_one_two_and_dense_rank_loss_satisfy_moore_penrose_identities() {
        for a in [
            [[0.; 3]; 3],
            [[1., 0., 0.], [0., 0., 0.], [0., 0., 2.]],
            [[1., 2., 3.], [2., 4., 6.], [-1., -2., -3.]],
            [[1., 2., 0.], [0., 1., 1.], [1., 3., 1.]],
        ] {
            let (p, singular) = object(a).unwrap();
            assert!(singular);
            near(multiply(multiply(a, p), a), a);
            near(multiply(multiply(p, a), p), p);
            near(multiply(a, p), transpose(multiply(a, p)));
            near(multiply(p, a), transpose(multiply(p, a)));
        }
    }
    #[test]
    fn singular_normal_keeps_adjugate_instead_of_linear_pseudoinverse() {
        let a = [[2., 0., 0.], [0., 0., 0.], [0., 0., 3.]];
        near(
            normal(a).unwrap(),
            [[0., 0., 0.], [0., 6., 0.], [0., 0., 0.]],
        );
        near(
            object(a).unwrap().0,
            [[0.5, 0., 0.], [0., 0., 0.], [0., 0., 1. / 3.]],
        );
    }
    #[test]
    fn singular_affine_pivot_retains_column_major_partial_elimination() {
        let world = [
            [1., 0., 0., 2.],
            [0., 0., 0., 3.],
            [0., 0., 1., 4.],
            [0., 0., 0., 1.],
        ];
        let p = pivot(world, [2., 3., 4.]).unwrap();
        // Elimination of the translation row also removes the Z offset.
        for (a, b) in p.into_iter().zip([0., 1., 0.]) {
            assert!((a - b).abs() <= 1e-6, "{p:?}");
        }
        assert_ne!(p, [0.; 3]);
    }
    #[test]
    fn missing_local_axes_follow_cross_projection_and_identity_fallbacks() {
        near(
            local_axes([[1., 0., 0.], [0., 0., 0.], [0., 0., 1.]]).unwrap(),
            IDENTITY,
        );
        near(
            local_axes([[1., 0., 0.], [0., 0., 0.], [0., 0., 0.]]).unwrap(),
            IDENTITY,
        );
        near(local_axes([[0.; 3]; 3]).unwrap(), IDENTITY);
        near(
            local_axes([[-2., 0., 0.], [0., 0., 0.], [0., 0., 3.]]).unwrap(),
            [[-1., 0., 0.], [0., -1., 0.], [0., 0., 1.]],
        );
    }
    #[test]
    fn arithmetic_overflow_and_nonconvergence_are_explicit_errors() {
        assert!(object([[1e30, 0., 0.], [0., 1e30, 0.], [0., 0., 0.]]).is_err());
        assert!(object([[f32::NAN; 3]; 3]).is_err());
        assert!(
            svd::pseudoinverse([[1., 0., 0.], [0., 0., 0.], [0., 0., 2.]], 0)
                .unwrap_err()
                .0
                .contains("step budget")
        );
    }
}

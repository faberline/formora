// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
//! Fixed source operations on row-major matrices.
use crate::mesh::{frame_math, snap::point};
use crate::rotation::EulerOrder;
use crate::scene::{Result, Scene};
use crate::transforms::{Matrix, Precision};

pub(super) fn mul(a: Matrix, b: Matrix) -> Result<Matrix> {
    crate::transforms::compose(a, b, Precision::F32)
}
pub(super) fn inverse(m: Matrix) -> Result<Matrix> {
    for row in &m {
        for v in row {
            crate::mesh::snap::finite(*v)?;
        }
    }
    Ok(
        crate::mesh::creation::inverse4::inverse_or_zero(m.map(|r| r.map(|v| v as f32)))?
            .map(|r| r.map(f64::from)),
    )
}
pub(super) fn basis(m: Matrix) -> [[f32; 3]; 3] {
    std::array::from_fn(|r| std::array::from_fn(|c| m[r][c] as f32))
}
pub(super) fn location(m: Matrix) -> [f32; 3] {
    std::array::from_fn(|r| m[r][3] as f32)
}
pub(super) fn world(scene: &Scene, id: &str) -> Result<Matrix> {
    frame_math::world(scene, id)
}
pub(super) fn parent_space(scene: &Scene, id: &str) -> Result<Matrix> {
    let entity = &scene.entities[id];
    let Some(parent) = &entity.parent else {
        return Ok(super::identity());
    };
    let inverse = scene
        .object_context
        .as_ref()
        .map(|c| c.state(id))
        .unwrap_or_default()
        .parent_inverse
        .unwrap_or_else(super::identity);
    mul(world(scene, parent)?, inverse)
}

pub(super) fn center(points: &[[f32; 3]], bounds: bool) -> Option<[f32; 3]> {
    let first = *points.first()?;
    if !bounds {
        return Some(crate::mesh::snap::average(points.iter().copied()));
    }
    let (mut low, mut high) = (first, first);
    for p in &points[1..] {
        for i in 0..3 {
            low[i] = low[i].min(p[i]);
            high[i] = high[i].max(p[i]);
        }
    }
    Some(crate::mesh::snap::add(low, high).map(|v| v * 0.5))
}

/// Normalize columns, then choose the Euler solution with the smaller L1 sum.
pub(super) fn euler(mut m: [[f32; 3]; 3], order: EulerOrder) -> Result<[f32; 3]> {
    for c in 0..3 {
        let d = m[0][c] * m[0][c] + m[1][c] * m[1][c] + m[2][c] * m[2][c];
        if d > 1e-35 {
            let factor = 1. / d.sqrt();
            for row in &mut m {
                row[c] *= factor;
            }
        } else {
            for row in &mut m {
                row[c] = 0.;
            }
        }
    }
    let ([i, j, k], parity) = order.axes();
    let cy = m[i][i].hypot(m[j][i]);
    let (mut a, mut b) = ([0.; 3], [0.; 3]);
    if cy > 0.0000375 {
        a[i] = m[k][j].atan2(m[k][k]);
        a[j] = (-m[k][i]).atan2(cy);
        a[k] = m[j][i].atan2(m[i][i]);
        b[i] = (-m[k][j]).atan2(-m[k][k]);
        b[j] = (-m[k][i]).atan2(-cy);
        b[k] = (-m[j][i]).atan2(-m[i][i]);
    } else {
        a[i] = (-m[j][k]).atan2(m[j][j]);
        a[j] = (-m[k][i]).atan2(cy);
        a[k] = 0.;
        b = a;
    }
    if parity {
        a = a.map(|v| -v);
        b = b.map(|v| -v);
    }
    let sum = |v: [f32; 3]| v[0].abs() + v[1].abs() + v[2].abs();
    let result = if sum(a) > sum(b) { b } else { a };
    point(result.map(f64::from))
}

// SPDX-FileCopyrightText: 2004 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
// Shared authoring matrix order, with explicit single-precision steps.
use crate::scene::{Result, Scene, SceneError};
pub(super) type Mat3 = [[f32; 3]; 3];
pub(super) type Mat4 = [[f64; 4]; 4];

pub(super) fn euler(angles: [f64; 3], single: bool) -> Mat3 {
    let trig = angles.map(|angle| {
        let angle = angle as f32;
        if single {
            let (s, c) = angle.sin_cos();
            (s as f64, c as f64)
        } else {
            (angle as f64).sin_cos()
        }
    });
    let [(si, ci), (sj, cj), (sh, ch)] = trig;
    let (cc, cs, sc, ss) = (ci * ch, ci * sh, si * ch, si * sh);
    [
        [
            (cj * ch) as f32,
            (sj * sc - cs) as f32,
            (sj * cc + ss) as f32,
        ],
        [
            (cj * sh) as f32,
            (sj * ss + cc) as f32,
            (sj * cs - sc) as f32,
        ],
        [-sj as f32, (cj * si) as f32, (cj * ci) as f32],
    ]
}
pub(super) fn inverse(m: Mat3) -> Result<Mat3> {
    let adj: Mat3 = std::array::from_fn(|i| {
        std::array::from_fn(|j| {
            m[(j + 1) % 3][(i + 1) % 3] * m[(j + 2) % 3][(i + 2) % 3]
                - m[(j + 1) % 3][(i + 2) % 3] * m[(j + 2) % 3][(i + 1) % 3]
        })
    });
    let det = m[0][0] * adj[0][0] + m[0][1] * adj[1][0] + m[0][2] * adj[2][0];
    if !det.is_finite() || det == 0. {
        return Err(SceneError(
            "singular or nonfinite creation target transform".into(),
        ));
    }
    let r = 1. / det;
    let result = adj.map(|row| row.map(|v| v * r));
    if result.iter().flatten().any(|v| !v.is_finite()) {
        return Err(SceneError("creation inverse exceeds finite range".into()));
    }
    Ok(result)
}
pub(super) fn multiply(a: Mat3, b: Mat3) -> Mat3 {
    std::array::from_fn(|i| {
        std::array::from_fn(|j| a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j])
    })
}
pub(super) fn vector(m: Mat3, p: [f32; 3]) -> [f32; 3] {
    m.map(|r| r[0] * p[0] + r[1] * p[1] + r[2] * p[2])
}
pub(super) fn quaternion(matrix: Mat3) -> [f64; 4] {
    let m = matrix.map(|r| r.map(f64::from));
    let trace = m[0][0] + m[1][1] + m[2][2];
    let q = if trace > 0. {
        let s = (trace + 1.).sqrt() * 2.;
        [
            (m[2][1] - m[1][2]) / s,
            (m[0][2] - m[2][0]) / s,
            (m[1][0] - m[0][1]) / s,
            s / 4.,
        ]
    } else {
        let i = (0..3)
            .max_by(|a, b| m[*a][*a].total_cmp(&m[*b][*b]))
            .unwrap();
        let j = (i + 1) % 3;
        let k = (i + 2) % 3;
        let s = (1. + m[i][i] - m[j][j] - m[k][k]).sqrt() * 2.;
        let mut q = [0.; 4];
        q[i] = s / 4.;
        q[j] = (m[i][j] + m[j][i]) / s;
        q[k] = (m[i][k] + m[k][i]) / s;
        q[3] = (m[k][j] - m[j][k]) / s;
        q
    };
    let length = q.iter().map(|v| v * v).sum::<f64>().sqrt();
    q.map(|v| v / length)
}
pub(super) fn world(scene: &Scene, id: &str) -> Result<Mat4> {
    let result = crate::transforms::world(scene, id)?;
    if result
        .iter()
        .flatten()
        .any(|v| !v.is_finite() || (*v as f32).is_infinite())
    {
        return Err(SceneError(
            "creation world transform exceeds finite range".into(),
        ));
    }
    Ok(result)
}

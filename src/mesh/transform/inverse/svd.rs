// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
//! The pinned TNT-derived four-dimensional bidiagonal SVD.
use super::{Matrix, checked, error};
use crate::scene::{Result, SceneError};
type Mat4 = [[f32; 4]; 4];

fn finite(u: Mat4, v: Mat4, s: [f32; 4], e: [f32; 4]) -> Result<()> {
    checked(u)?;
    checked(v)?;
    if s.iter().chain(&e).all(|v| v.is_finite()) {
        Ok(())
    } else {
        Err(error())
    }
}
#[allow(clippy::needless_range_loop)]
fn decompose(mut a: Mat4, limit: usize) -> Result<(Mat4, [f32; 4], Mat4)> {
    checked(a)?;
    let mut u = [[0.; 4]; 4];
    let mut v = [[0.; 4]; 4];
    let mut s = [0_f32; 4];
    let mut e = [0_f32; 4];
    let mut work = [0.; 4];
    for k in 0..3 {
        for row in k..4 {
            s[k] = s[k].hypot(a[row][k]);
        }
        if s[k] != 0. {
            if a[k][k] < 0. {
                s[k] = -s[k];
            }
            let inverse = 1. / s[k];
            for row in k..4 {
                a[row][k] *= inverse;
            }
            a[k][k] += 1.;
        }
        s[k] = -s[k];
        for j in k + 1..4 {
            if s[k] != 0. {
                let mut t = 0.;
                for row in k..4 {
                    t += a[row][k] * a[row][j];
                }
                t = -t / a[k][k];
                for row in k..4 {
                    a[row][j] += t * a[row][k];
                }
            }
            e[j] = a[k][j];
        }
        for row in k..4 {
            u[row][k] = a[row][k];
        }
        if k < 2 {
            e[k] = 0.;
            for i in k + 1..4 {
                e[k] = e[k].hypot(e[i]);
            }
            if e[k] != 0. {
                if e[k + 1] < 0. {
                    e[k] = -e[k];
                }
                let inverse = 1. / e[k];
                for value in &mut e[k + 1..] {
                    *value *= inverse;
                }
                e[k + 1] += 1.;
            }
            e[k] = -e[k];
            if e[k] != 0. {
                for row in k + 1..4 {
                    work[row] = 0.;
                }
                for j in k + 1..4 {
                    for row in k + 1..4 {
                        work[row] += e[j] * a[row][j];
                    }
                }
                let inverse = 1. / e[k + 1];
                for j in k + 1..4 {
                    let t = -e[j] * inverse;
                    for row in k + 1..4 {
                        a[row][j] += t * work[row];
                    }
                }
            }
            for i in k + 1..4 {
                v[i][k] = e[i];
            }
        }
    }
    s[3] = a[3][3];
    e[2] = a[2][3];
    e[3] = 0.;
    u[3][3] = 1.;
    for k in (0..3).rev() {
        if s[k] != 0. {
            for j in k + 1..4 {
                let mut t = 0.;
                for row in k..4 {
                    t += u[row][k] * u[row][j];
                }
                t = -t / u[k][k];
                for row in k..4 {
                    u[row][j] += t * u[row][k];
                }
            }
            for row in k..4 {
                u[row][k] = -u[row][k];
            }
            u[k][k] += 1.;
            // Preserve the pinned source's i < k - 1 bound.
            for row in 0..k.saturating_sub(1) {
                u[row][k] = 0.;
            }
        } else {
            for row in 0..4 {
                u[row][k] = 0.;
            }
            u[k][k] = 1.;
        }
    }
    for k in (0..4).rev() {
        if k < 2 && e[k] != 0. {
            for j in k + 1..4 {
                let mut t = 0.;
                for row in k + 1..4 {
                    t += v[row][k] * v[row][j];
                }
                t = -t / v[k + 1][k];
                for row in k + 1..4 {
                    v[row][j] += t * v[row][k];
                }
            }
        }
        for row in 0..4 {
            v[row][k] = 0.;
        }
        v[k][k] = 1.;
    }
    finite(u, v, s, e)?;
    let eps = f32::from_bits(0x2580_0000); // exactly 2^-52, as in the pinned source.
    let mut p = 4;
    let mut steps = 0;
    while p > 0 {
        if steps == limit {
            return Err(SceneError(
                "safe transform SVD did not converge within its step budget".into(),
            ));
        }
        steps += 1;
        let mut k = p as isize - 2;
        while k >= 0 {
            let j = k as usize;
            if e[j].abs() <= eps * (s[j].abs() + s[j + 1].abs()) {
                e[j] = 0.;
                break;
            }
            k -= 1;
        }
        let case = if k == p as isize - 2 {
            4
        } else {
            let mut ks = p as isize - 1;
            while ks > k {
                let i = ks as usize;
                let t = (if i != p { e[i].abs() } else { 0. })
                    + (if ks != k + 1 { e[i - 1].abs() } else { 0. });
                if s[i].abs() <= eps * t {
                    s[i] = 0.;
                    break;
                }
                ks -= 1;
            }
            if ks == k {
                3
            } else if ks == p as isize - 1 {
                1
            } else {
                k = ks;
                2
            }
        };
        let mut k = (k + 1) as usize;
        match case {
            1 => {
                let mut f = e[p - 2];
                e[p - 2] = 0.;
                for j in (k..p - 1).rev() {
                    let mut t = s[j].hypot(f);
                    let inverse = 1. / t;
                    let cs = s[j] * inverse;
                    let sn = f * inverse;
                    s[j] = t;
                    if j != k {
                        f = -sn * e[j - 1];
                        e[j - 1] *= cs;
                    }
                    for row in 0..4 {
                        t = cs * v[row][j] + sn * v[row][p - 1];
                        v[row][p - 1] = -sn * v[row][j] + cs * v[row][p - 1];
                        v[row][j] = t;
                    }
                }
            }
            2 => {
                if k == 0 {
                    return Err(error());
                }
                let mut f = e[k - 1];
                e[k - 1] = 0.;
                for j in k..p {
                    let mut t = s[j].hypot(f);
                    let inverse = 1. / t;
                    let cs = s[j] * inverse;
                    let sn = f * inverse;
                    s[j] = t;
                    f = -sn * e[j];
                    e[j] *= cs;
                    for row in 0..4 {
                        t = cs * u[row][j] + sn * u[row][k - 1];
                        u[row][k - 1] = -sn * u[row][j] + cs * u[row][k - 1];
                        u[row][j] = t;
                    }
                }
            }
            3 => {
                let scale = s[p - 1]
                    .abs()
                    .max(s[p - 2].abs())
                    .max(e[p - 2].abs())
                    .max(s[k].abs())
                    .max(e[k].abs());
                let inverse = 1. / scale;
                let sp = s[p - 1] * inverse;
                let spm1 = s[p - 2] * inverse;
                let epm1 = e[p - 2] * inverse;
                let sk = s[k] * inverse;
                let ek = e[k] * inverse;
                let b = ((spm1 + sp) * (spm1 - sp) + epm1 * epm1) * 0.5;
                let c = (sp * epm1) * (sp * epm1);
                let mut shift = 0.;
                if b != 0. || c != 0. {
                    shift = (b * b + c).sqrt();
                    if b < 0. {
                        shift = -shift;
                    }
                    shift = c / (b + shift);
                }
                let mut f = (sk + sp) * (sk - sp) + shift;
                let mut g = sk * ek;
                for j in k..p - 1 {
                    let mut t = f.hypot(g);
                    let cs = if t == 0. { 0. } else { f / t };
                    let sn = if t == 0. { 0. } else { g / t };
                    if j != k {
                        e[j - 1] = t;
                    }
                    f = cs * s[j] + sn * e[j];
                    e[j] = cs * e[j] - sn * s[j];
                    g = sn * s[j + 1];
                    s[j + 1] *= cs;
                    for row in 0..4 {
                        t = cs * v[row][j] + sn * v[row][j + 1];
                        v[row][j + 1] = -sn * v[row][j] + cs * v[row][j + 1];
                        v[row][j] = t;
                    }
                    t = f.hypot(g);
                    let cs = if t == 0. { 0. } else { f / t };
                    let sn = if t == 0. { 0. } else { g / t };
                    s[j] = t;
                    f = cs * e[j] + sn * s[j + 1];
                    s[j + 1] = -sn * e[j] + cs * s[j + 1];
                    g = sn * e[j + 1];
                    e[j + 1] *= cs;
                    for row in 0..4 {
                        t = cs * u[row][j] + sn * u[row][j + 1];
                        u[row][j + 1] = -sn * u[row][j] + cs * u[row][j + 1];
                        u[row][j] = t;
                    }
                }
                e[p - 2] = f;
            }
            4 => {
                if s[k] <= 0. {
                    s[k] = if s[k] < 0. { -s[k] } else { 0. };
                    for row in 0..4 {
                        v[row][k] = -v[row][k];
                    }
                }
                while k < 3 && s[k] < s[k + 1] {
                    s.swap(k, k + 1);
                    for row in 0..4 {
                        v[row].swap(k, k + 1);
                        u[row].swap(k, k + 1);
                    }
                    k += 1;
                }
                p -= 1;
            }
            _ => unreachable!(),
        }
        finite(u, v, s, e)?;
    }
    Ok((u, s, v))
}
fn multiply(a: Mat4, b: Mat4) -> Mat4 {
    std::array::from_fn(|r| {
        std::array::from_fn(|c| {
            a[r][0] * b[0][c] + a[r][1] * b[1][c] + a[r][2] * b[2][c] + a[r][3] * b[3][c]
        })
    })
}
pub(super) fn pseudoinverse(m: Matrix, limit: usize) -> Result<Matrix> {
    let a = std::array::from_fn(|r| {
        std::array::from_fn(|c| {
            if r < 3 && c < 3 {
                m[r][c]
            } else if r == c {
                1.
            } else {
                0.
            }
        })
    });
    let (u, mut s, v) = decompose(a, limit)?;
    // The homogeneous unit adds one to the input's certified rank. Deflate only
    // exact null dimensions; do not widen the source's absolute 1e-8 cutoff.
    let rank = super::rank::exact(m) + 1;
    for value in &mut s[rank..] {
        *value = 0.;
    }
    let diagonal = std::array::from_fn(|r| {
        std::array::from_fn(|c| if r != c || s[r] < 1e-8 { 0. } else { 1. / s[r] })
    });
    let inverse = checked(multiply(
        multiply(v, diagonal),
        std::array::from_fn(|r| std::array::from_fn(|c| u[c][r])),
    ))?;
    Ok(std::array::from_fn(|r| {
        std::array::from_fn(|c| inverse[r][c])
    }))
}

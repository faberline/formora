// SPDX-FileCopyrightText: 2001 Intel Corporation
// SPDX-FileCopyrightText: 2009 Benoit Jacob
// SPDX-FileCopyrightText: 2010 Gael Guennebaud
// SPDX-License-Identifier: MPL-2.0
// Copyright (c) 2001 Intel Corporation.
// Permission is granted to use, copy, distribute and prepare derivative works
// of this library for any purpose and without fee, provided that the above
// copyright notice and this statement appear in all copies.
// Intel makes no representations about the suitability of this software for
// any purpose, and specifically disclaims all warranties.
// The complete upstream notices and MPL text are retained in
// docs/evidence/creation-contexts/source/.
// Scalar lanes of the frozen Eigen revision's 4x4 inverse.
// The reciprocal also preserves its ARM estimate and two refinement steps.
use crate::scene::{Result, SceneError};
type Lane = [f32; 4];
fn sw(a: Lane, b: Lane, i: [usize; 4]) -> Lane {
    [a[i[0]], a[i[1]], b[i[2]], b[i[3]]]
}
fn low(a: Lane, b: Lane) -> Lane {
    [a[0], a[1], b[0], b[1]]
}
fn high(a: Lane, b: Lane) -> Lane {
    [b[2], b[3], a[2], a[3]]
}
fn mul(a: Lane, b: Lane) -> Lane {
    std::array::from_fn(|i| a[i] * b[i])
}
fn add(a: Lane, b: Lane) -> Lane {
    std::array::from_fn(|i| a[i] + b[i])
}
fn sub(a: Lane, b: Lane) -> Lane {
    std::array::from_fn(|i| a[i] - b[i])
}
fn det(a: Lane) -> Lane {
    let d = mul(sw(a, a, [3, 3, 1, 1]), a);
    sub(d, high(d, d))
}
fn reciprocal(value: f32) -> f32 {
    let bits = value.to_bits();
    let exponent = (bits >> 23) & 255;
    if !(1..=252).contains(&exponent) {
        return 1. / value;
    }
    let scaled = 256 + ((bits >> 15) & 255);
    let estimate = (((1 << 19) / (2 * scaled + 1)) + 1) / 2;
    let seed = (bits & 0x80000000) | ((253 - exponent) << 23) | ((estimate - 256) << 15);
    let mut result = f32::from_bits(seed);
    for _ in 0..2 {
        result *= (-value).mul_add(result, 2.);
    }
    result
}
pub(crate) fn inverse(m: [[f32; 4]; 4]) -> Result<[[f32; 4]; 4]> {
    let col: [Lane; 4] = std::array::from_fn(|c| std::array::from_fn(|r| m[r][c]));
    let a = low(col[0], col[1]);
    let b = high(col[1], col[0]);
    let c = low(col[2], col[3]);
    let d = high(col[3], col[2]);
    let ab = sub(
        mul(sw(a, a, [3, 3, 0, 0]), b),
        mul(sw(a, a, [1, 1, 2, 2]), sw(b, b, [2, 3, 0, 1])),
    );
    let dc = sub(
        mul(sw(d, d, [3, 3, 0, 0]), c),
        mul(sw(d, d, [1, 1, 2, 2]), sw(c, c, [2, 3, 0, 1])),
    );
    let [da, db, dc_det, dd] = [a, b, c, d].map(det);
    let trace = mul(sw(dc, dc, [0, 2, 1, 3]), ab);
    let trace = add(trace, high(trace, trace));
    let trace = add(trace, sw(trace, trace, [1, 0, 0, 0]));
    let determinant = sub(add(mul(da, dd), mul(db, dc_det)), trace)[0];
    if !determinant.is_finite() || determinant == 0. {
        return Err(SceneError(
            "singular or nonfinite creation target transform".into(),
        ));
    }
    let reciprocal = reciprocal(determinant);
    let signs = [reciprocal, -reciprocal, -reciprocal, reciprocal];
    let id = sub(
        mul(d, [da[0]; 4]),
        add(
            mul(sw(c, c, [0, 0, 2, 2]), low(ab, ab)),
            mul(sw(c, c, [1, 1, 3, 3]), high(ab, ab)),
        ),
    );
    let ia = sub(
        mul(a, [dd[0]; 4]),
        add(
            mul(sw(b, b, [0, 0, 2, 2]), low(dc, dc)),
            mul(sw(b, b, [1, 1, 3, 3]), high(dc, dc)),
        ),
    );
    let ib = sub(
        mul(c, [db[0]; 4]),
        sub(
            mul(d, sw(ab, ab, [3, 0, 3, 0])),
            mul(sw(d, d, [1, 0, 3, 2]), sw(ab, ab, [2, 1, 2, 1])),
        ),
    );
    let ic = sub(
        mul(b, [dc_det[0]; 4]),
        sub(
            mul(a, sw(dc, dc, [3, 0, 3, 0])),
            mul(sw(a, a, [1, 0, 3, 2]), sw(dc, dc, [2, 1, 2, 1])),
        ),
    );
    let [ia, ib, ic, id] = [ia, ib, ic, id].map(|v| mul(v, signs));
    let columns = [
        sw(ia, ib, [3, 1, 3, 1]),
        sw(ia, ib, [2, 0, 2, 0]),
        sw(ic, id, [3, 1, 3, 1]),
        sw(ic, id, [2, 0, 2, 0]),
    ];
    let result: [[f32; 4]; 4] = std::array::from_fn(|r| std::array::from_fn(|c| columns[c][r]));
    if result.iter().flatten().any(|v| !v.is_finite()) {
        return Err(SceneError("creation inverse exceeds finite range".into()));
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn block_inverse_preserves_translation_and_singular_rejection() {
        let m = [
            [0.93629336, -0.27509585, 0.21835066, 4.],
            [0.2896295, 0.9564251, -0.03695701, -3.],
            [-0.19866933, 0.09784339, 0.9751703, 2.],
            [0., 0., 0., 1.],
        ];
        let inverse = inverse(m).unwrap();
        for (r, row) in m.iter().enumerate() {
            for c in 0..4 {
                let product: f32 = (0..4).map(|i| row[i] * inverse[i][c]).sum();
                assert!((product - if r == c { 1. } else { 0. }).abs() < 1e-6);
            }
        }
        assert_eq!(reciprocal(f32::from_bits(1_f32.to_bits() - 1)), 1.);
        assert!(super::inverse([[0.; 4]; 4]).is_err());
    }
}

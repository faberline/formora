//! Exact rank of finite float32 entries. No rounded determinant decides zero.
use super::Matrix;

fn parts(v: f32) -> (bool, u128, i32) {
    let bits = v.to_bits();
    let exponent = ((bits >> 23) & 255) as i32;
    let mantissa = bits & 0x7f_ffff;
    (
        bits >> 31 != 0,
        if exponent == 0 {
            mantissa as u128
        } else {
            (mantissa | 0x80_0000) as u128
        },
        if exponent == 0 { -149 } else { exponent - 150 },
    )
}
fn add_word(limbs: &mut [u64; 14], mut index: usize, mut word: u64) {
    while word != 0 {
        let (sum, carry) = limbs[index].overflowing_add(word);
        limbs[index] = sum;
        word = u64::from(carry);
        index += 1;
    }
}
fn add(limbs: &mut [u64; 14], value: u128, shift: usize) {
    let i = shift / 64;
    let b = shift % 64;
    let low = value as u64;
    let high = (value >> 64) as u64;
    add_word(limbs, i, low << b);
    add_word(limbs, i + 1, high << b);
    if b != 0 {
        add_word(limbs, i + 1, low >> (64 - b));
        add_word(limbs, i + 2, high >> (64 - b));
    }
}
fn zero_determinant(m: Matrix) -> bool {
    let mut positive = [0; 14];
    let mut negative = [0; 14];
    // Three float32 significands need at most 72 bits. A base exponent of -447
    // covers all finite entries. Six products and carries fit in 14 limbs.
    for (p, odd) in [
        ([0, 1, 2], false),
        ([0, 2, 1], true),
        ([1, 0, 2], true),
        ([1, 2, 0], false),
        ([2, 0, 1], false),
        ([2, 1, 0], true),
    ] {
        let mut sign = odd;
        let mut value = 1;
        let mut exponent = 447;
        for r in 0..3 {
            let (negative, mantissa, e) = parts(m[r][p[r]]);
            sign ^= negative;
            value *= mantissa;
            exponent += e;
        }
        if value != 0 {
            add(
                if sign { &mut negative } else { &mut positive },
                value,
                exponent as usize,
            );
        }
    }
    positive == negative
}
pub(super) fn exact(m: Matrix) -> usize {
    if m.iter().flatten().all(|v| *v == 0.) {
        return 0;
    }
    if !zero_determinant(m) {
        return 3;
    }
    for r in 0..3 {
        for rr in r + 1..3 {
            for c in 0..3 {
                for cc in c + 1..3 {
                    // Products of two float32 significands fit exactly in float64.
                    if f64::from(m[r][c]) * f64::from(m[rr][cc])
                        != f64::from(m[r][cc]) * f64::from(m[rr][c])
                    {
                        return 2;
                    }
                }
            }
        }
    }
    1
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_dyadic_rank_does_not_drop_a_small_genuine_determinant() {
        let e = f32::EPSILON;
        assert_eq!(exact([[1., 1., 1.], [1., 1. + e, 1.], [1., 1., 1. + e]]), 3);
        assert_eq!(exact([[1e-30, 0., 0.], [0., 1e30, 0.], [0., 0., 1.]]), 3);
        assert_eq!(exact([[1., 2., 0.], [0., 1., 1.], [1., 3., 1.]]), 2);
        assert_eq!(exact([[1e-30, 1e30, 0.], [2e-30, 2e30, 0.], [0.; 3]]), 1);
        assert_eq!(exact([[0.; 3]; 3]), 0);
    }
}

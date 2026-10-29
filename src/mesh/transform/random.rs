// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-FileCopyrightText: 2023 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
//! Explicit seeded streams. Blender path follows pinned BLI_rand.hh.
use super::RandomAlgorithm;

pub(super) enum Stream {
    Splitmix64(u64),
    Blender(u64),
}

impl Stream {
    pub fn new(algorithm: Option<RandomAlgorithm>, seed: u64) -> Self {
        match algorithm {
            Some(RandomAlgorithm::Blender52) => Self::Blender((seed << 16) | 0x330e),
            _ => Self::Splitmix64(seed),
        }
    }

    pub fn next(&mut self) -> f32 {
        match self {
            Self::Splitmix64(state) => {
                *state = state.wrapping_add(0x9e3779b97f4a7c15);
                let mut z = *state;
                z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
                z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
                (((z ^ (z >> 31)) >> 40) as u32) as f32 / 16_777_216.
            }
            Self::Blender(state) => {
                *state = state.wrapping_mul(0x5deece66d).wrapping_add(0xb) & 0x0000_ffff_ffff_ffff;
                (*state >> 17) as i32 as f32 / 2_147_483_648.
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn complete_pinned_cpp_sequences_match_float_bits_and_restart() {
        let raw = include_bytes!(
            "../../../baseline/reference/blender-5.2.3/random-falloff/first-sequence.bin"
        );
        let seeds = [
            0, 1, 2, 42, 65535, 65536, 1234567, 2147483647, 2147483648, 4294967295,
        ];
        assert_eq!(raw.len(), seeds.len() * 4096 * 4);
        for (seed, bytes) in seeds.into_iter().zip(raw.chunks_exact(4096 * 4)) {
            let mut first = Stream::new(Some(RandomAlgorithm::Blender52), seed);
            let mut repeat = Stream::new(Some(RandomAlgorithm::Blender52), seed);
            let mut independent = Stream::new(None, u64::MAX);
            for (index, bits) in bytes.chunks_exact(4).enumerate() {
                let expected = u32::from_le_bytes(bits.try_into().unwrap());
                assert_eq!(
                    first.next().to_bits(),
                    expected,
                    "seed {seed}, draw {index}"
                );
                independent.next();
                assert_eq!(repeat.next().to_bits(), expected);
            }
        }
    }

    #[test]
    fn complete_million_draw_source_sample_matches_float_bits() {
        let raw = include_bytes!(
            "../../../baseline/reference/blender-5.2.3/random-falloff/first-distribution.bin"
        );
        assert_eq!(raw.len(), 1048576 * 4);
        let mut stream = Stream::new(Some(RandomAlgorithm::Blender52), 42);
        for (index, bits) in raw.chunks_exact(4).enumerate() {
            let expected = u32::from_le_bytes(bits.try_into().unwrap());
            assert_eq!(stream.next().to_bits(), expected, "draw {index}");
        }
    }

    #[test]
    fn explicit_legacy_stream_preserves_all_seed_bits() {
        for seed in [0, 1, u32::MAX as u64, 1_u64 << 32, u64::MAX] {
            let mut implicit = Stream::new(None, seed);
            let mut explicit = Stream::new(Some(RandomAlgorithm::Splitmix64V1), seed);
            for _ in 0..4096 {
                assert_eq!(implicit.next().to_bits(), explicit.next().to_bits());
            }
        }
        assert_ne!(
            Stream::new(None, 0).next(),
            Stream::new(None, 1 << 32).next()
        );
    }

    #[test]
    fn source_float_rounding_can_reach_one_without_clamping_or_resampling() {
        // Solve the first-step high 32 bits for 0xffffffff, with the source's
        // fixed low seed. The resulting integer draw is 0x7fffffff.
        let mut stream = Stream::new(Some(RandomAlgorithm::Blender52), 3_799_816_143);
        assert_eq!(stream.next().to_bits(), 1_f32.to_bits());
        assert_ne!(stream.next().to_bits(), 1_f32.to_bits());
    }
}

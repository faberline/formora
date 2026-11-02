//! Complete triangle-aligned GPU uploads and global-to-local draw ranges.
use super::math::Vertex;
use crate::scene::{Result, SceneError};
use std::ops::Range;
use std::sync::Arc;
use wgpu::util::DeviceExt;

pub(super) struct Draw<'a> {
    pub vertex: &'a wgpu::Buffer,
    pub range: Range<u32>,
}

pub(super) struct VertexBuffers {
    source: Arc<Vec<Vertex>>,
    limit: u64,
    ranges: Vec<Range<u32>>,
    buffers: Vec<Arc<wgpu::Buffer>>,
}

pub(super) fn triangle_ranges(count: u32, limit: u64) -> Result<Vec<Range<u32>>> {
    let stride = std::mem::size_of::<Vertex>() as u64;
    if limit < 3 * stride {
        return Err(SceneError(
            "vertex buffer limit must hold a complete triangle".into(),
        ));
    }
    if count % 3 != 0 {
        return Err(SceneError(
            "vertex stream must contain complete triangles".into(),
        ));
    }
    let capacity = ((limit / stride / 3) * 3).min(u64::from(u32::MAX)) as u32;
    let mut ranges = Vec::new();
    let mut start = 0_u32;
    while start < count {
        let end = start.saturating_add(capacity).min(count);
        ranges.push(start..end);
        start = end;
    }
    Ok(ranges)
}

fn segments(
    chunks: &[Range<u32>],
    range: Range<u32>,
) -> impl Iterator<Item = (usize, Range<u32>)> + '_ {
    chunks.iter().enumerate().filter_map(move |(index, chunk)| {
        let start = range.start.max(chunk.start);
        let end = range.end.min(chunk.end);
        (start < end).then(|| (index, (start - chunk.start)..(end - chunk.start)))
    })
}

impl VertexBuffers {
    pub fn new(device: &wgpu::Device, source: Arc<Vec<Vertex>>, limit: u64) -> Result<Self> {
        if limit > device.limits().max_buffer_size {
            return Err(SceneError(
                "vertex buffer chunk limit exceeds device maximum".into(),
            ));
        }
        let count = u32::try_from(source.len()).map_err(|e| SceneError(e.to_string()))?;
        let ranges = triangle_ranges(count, limit)?;
        let mut buffers = Vec::with_capacity(ranges.len());
        for range in &ranges {
            let data = bytemuck::cast_slice(&source[range.start as usize..range.end as usize]);
            if data.len() as u64 > limit {
                return Err(SceneError(
                    "vertex chunk exceeds checked buffer limit".into(),
                ));
            }
            buffers.push(Arc::new(device.create_buffer_init(
                &wgpu::util::BufferInitDescriptor {
                    label: Some("Scene triangle chunk"),
                    contents: data,
                    usage: wgpu::BufferUsages::VERTEX,
                },
            )));
        }
        Ok(Self {
            source,
            limit,
            ranges,
            buffers,
        })
    }

    pub fn matches(&self, source: &Arc<Vec<Vertex>>, limit: u64) -> bool {
        self.limit == limit && Arc::ptr_eq(&self.source, source)
    }

    pub fn buffer_count(&self) -> usize {
        self.buffers.len()
    }

    pub fn append_draws<'a>(&'a self, range: Range<u32>, draws: &mut Vec<Draw<'a>>) -> Result<()> {
        if range.start > range.end
            || range.end as usize > self.source.len()
            || range.start % 3 != 0
            || range.end % 3 != 0
        {
            return Err(SceneError("invalid prepared vertex range".into()));
        }
        draws.extend(segments(&self.ranges, range).map(|(index, range)| Draw {
            vertex: &self.buffers[index],
            range,
        }));
        Ok(())
    }

    pub fn draws(&self, range: Range<u32>) -> Result<Vec<Draw<'_>>> {
        let mut draws = Vec::new();
        self.append_draws(range, &mut draws)?;
        Ok(draws)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn reported_large_stream_keeps_all_corners_in_two_legal_buffers() {
        let ranges = triangle_ranges(9_798_687, 268_435_456).unwrap();
        assert_eq!(ranges, vec![0..5_592_405, 5_592_405..9_798_687]);
        let sizes: Vec<_> = ranges
            .iter()
            .map(|r| u64::from(r.end - r.start) * 48)
            .collect();
        assert_eq!(sizes, vec![268_435_440, 201_901_536]);
        assert_eq!(sizes.iter().sum::<u64>(), 470_336_976);
        assert!(sizes.iter().all(|n| *n <= 268_435_456));
    }
    #[test]
    fn boundaries_round_only_capacity_and_never_drop_vertices() {
        assert!(triangle_ranges(0, 144).unwrap().is_empty());
        assert_eq!(triangle_ranges(6, 144).unwrap(), vec![0..3, 3..6]);
        assert_eq!(triangle_ranges(6, 146).unwrap(), vec![0..3, 3..6]);
        assert_eq!(triangle_ranges(15, 500).unwrap(), vec![0..9, 9..15]);
        for n in [0, 1, 47, 143] {
            assert!(triangle_ranges(3, n).is_err());
        }
        for n in [1, 2, 4, u32::MAX - 1] {
            assert!(triangle_ranges(n, 1024).is_err());
        }
    }
    #[test]
    fn maximum_count_arithmetic_does_not_overflow_or_allocate_source_data() {
        assert_eq!(
            triangle_ranges(u32::MAX, u64::MAX).unwrap(),
            vec![0..u32::MAX]
        );
        let ranges = triangle_ranges(u32::MAX, 268_435_456).unwrap();
        assert_eq!(ranges[0].start, 0);
        assert_eq!(ranges.last().unwrap().end, u32::MAX);
        assert!(ranges.windows(2).all(|w| w[0].end == w[1].start));
        assert_eq!(
            ranges
                .iter()
                .map(|r| u64::from(r.end - r.start))
                .sum::<u64>(),
            u64::from(u32::MAX)
        );
    }
    #[test]
    fn global_ranges_cross_buffer_boundaries_in_source_order() {
        let chunks = vec![0..6, 6..12, 12..15];
        assert_eq!(
            segments(&chunks, 3..15).collect::<Vec<_>>(),
            vec![(0, 3..6), (1, 0..6), (2, 0..3)]
        );
        assert_eq!(
            segments(&chunks, 6..12).collect::<Vec<_>>(),
            vec![(1, 0..6)]
        );
        assert!(segments(&chunks, 0..0).next().is_none());
        let mesh = segments(&chunks, 0..9).collect::<Vec<_>>();
        let annotations = segments(&chunks, 9..15).collect::<Vec<_>>();
        assert_eq!(mesh, vec![(0, 0..6), (1, 0..3)]);
        assert_eq!(annotations, vec![(1, 3..6), (2, 0..3)]);
    }
}

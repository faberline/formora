use super::{ErrorCode, Failure};
use std::io::Cursor;

pub(crate) struct Image {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<u8>,
}

pub(crate) struct Texel {
    pub position: [u32; 2],
    pub rgba8: [u8; 4],
    pub linear_rgba: [f64; 4],
}

impl Image {
    pub fn decode(bytes: &[u8]) -> Result<Self, Failure> {
        let invalid = |e| Failure::new(ErrorCode::InvalidImage, "decode_image", e);
        let mut reader = png::Decoder::new(Cursor::new(bytes))
            .read_info()
            .map_err(|e| invalid(e.to_string()))?;
        let info = reader.info();
        if info.bit_depth != png::BitDepth::Eight
            || info.color_type != png::ColorType::Rgb
            || info.trns.is_some()
            || info.animation_control.is_some()
            || info.source_gamma.is_some()
            || info.source_chromaticities.is_some()
            || info.srgb.is_some()
            || info.icc_profile.is_some()
        {
            return Err(Failure::new(
                ErrorCode::UnsupportedImage,
                "decode_image",
                "This profile requires RGB8 PNG without transparency, animation or embedded color metadata; declare srgb in the project",
            ));
        }
        let size = reader.output_buffer_size().ok_or_else(|| {
            Failure::new(
                ErrorCode::UnsupportedImage,
                "decode_image",
                "Image size overflow",
            )
        })?;
        let mut pixels = vec![0; size];
        let frame = reader
            .next_frame(&mut pixels)
            .map_err(|e| invalid(e.to_string()))?;
        pixels.truncate(frame.buffer_size());
        let (width, height) = (frame.width, frame.height);
        reader.finish().map_err(|e| invalid(e.to_string()))?;
        Ok(Self {
            width,
            height,
            pixels,
        })
    }

    pub fn sample(&self, uv: [f64; 2]) -> Result<Texel, Failure> {
        if !uv.iter().all(|x| x.is_finite()) {
            return Err(Failure::new(
                ErrorCode::InvalidSample,
                "sample",
                "UV must be finite",
            ));
        }
        let x =
            ((uv[0].clamp(0.0, 1.0) * f64::from(self.width)).floor() as u32).min(self.width - 1);
        let y = (((1.0 - uv[1].clamp(0.0, 1.0)) * f64::from(self.height)).floor() as u32)
            .min(self.height - 1);
        let offset = ((u64::from(y) * u64::from(self.width) + u64::from(x)) * 3) as usize;
        let rgba = [
            self.pixels[offset],
            self.pixels[offset + 1],
            self.pixels[offset + 2],
            255,
        ];
        let linear = [
            to_linear(rgba[0]),
            to_linear(rgba[1]),
            to_linear(rgba[2]),
            1.0,
        ];
        Ok(Texel {
            position: [x, y],
            rgba8: rgba,
            linear_rgba: linear,
        })
    }
}

fn to_linear(value: u8) -> f64 {
    let c = f64::from(value) / 255.0;
    if c <= 0.04045 {
        c / 12.92
    } else {
        ((c + 0.055) / 1.055).powf(2.4)
    }
}

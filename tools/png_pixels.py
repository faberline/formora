"""Read non-interlaced RGBA8 PNG captures for pixel assertions. No image edits."""
from pathlib import Path
import struct
import zlib


def paeth(a, b, c):
    prediction = a + b - c
    distances = [abs(prediction-a), abs(prediction-b), abs(prediction-c)]
    return [a, b, c][distances.index(min(distances))]


def read_rgba8(path):
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset, compressed, dimensions = 8, bytearray(), None
    while offset < len(data):
        size = struct.unpack(">I", data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        chunk = data[offset+8:offset+8+size]
        offset += size+12
        if kind == b"IHDR":
            width, height, bits, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunk)
            assert (bits, color, compression, filtering, interlace) == (8, 6, 0, 0, 0)
            dimensions = width, height
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
    assert dimensions is not None
    width, height = dimensions
    raw = zlib.decompress(compressed)
    stride = width*4
    assert len(raw) == (stride+1)*height
    rows, previous = [], bytearray(stride)
    for y in range(height):
        start = y*(stride+1)
        filter_type = raw[start]
        row = bytearray(raw[start+1:start+1+stride])
        assert 0 <= filter_type <= 4
        for i in range(stride):
            left = row[i-4] if i >= 4 else 0
            up = previous[i]
            corner = previous[i-4] if i >= 4 else 0
            predictor = [0, left, up, (left+up)//2, paeth(left, up, corner)][filter_type]
            row[i] = (row[i]+predictor) & 255
        rows.append(row)
        previous = row
    def pixel(x, y):
        assert 0 <= x < width and 0 <= y < height
        return list(rows[y][x*4:x*4+4])
    return width, height, pixel

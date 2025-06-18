from __future__ import annotations
import struct
import io
from typing import Optional
from PIL import Image


def _build_single_icon_ico(data: bytes, width: int, height: int, bit_count: int, color_count: int = 0) -> bytes:
    header = struct.pack('<HHH', 0, 1, 1)
    entry = struct.pack('<BBBBHHLL', width, height, color_count, 0, 1, bit_count, len(data), 22)
    return header + entry + data


def _build_single_cursor_cur(data: bytes, width: int, height: int, hotspot_x: int, hotspot_y: int, bit_count: int = 32) -> bytes:
    header = struct.pack('<HHH', 0, 2, 1)
    entry = struct.pack('<BBBBHHLL', width, height, 0, 0, hotspot_x, hotspot_y, len(data), 22)
    return header + entry + data


def _parse_bmp_header(data: bytes) -> tuple[int, int, int]:
    header_size = struct.unpack('<I', data[:4])[0]
    if header_size < 40:
        raise ValueError('Unsupported BITMAP header')
    width = struct.unpack('<I', data[4:8])[0]
    height = struct.unpack('<I', data[8:12])[0] // 2
    bit_count = struct.unpack('<H', data[14:16])[0]
    return width, height, bit_count


def decode_icon_resource(data: bytes, width: Optional[int] = None, height: Optional[int] = None,
                         bit_count: Optional[int] = None, color_count: int = 0) -> Image.Image:
    """Return a PIL Image from raw RT_ICON data."""
    if data[:4] == b'\x89PNG':
        img = Image.open(io.BytesIO(data))
        return img
    if width is None or height is None or bit_count is None:
        width_p, height_p, bit_p = _parse_bmp_header(data)
        width = width or width_p
        height = height or height_p
        bit_count = bit_count or bit_p
    ico_data = _build_single_icon_ico(data, width, height, bit_count, color_count)
    return Image.open(io.BytesIO(ico_data))


def decode_cursor_resource(data: bytes, width: Optional[int] = None, height: Optional[int] = None,
                           hotspot_x: int = 0, hotspot_y: int = 0,
                           bit_count: Optional[int] = None) -> Image.Image:
    """Return a PIL Image from raw RT_CURSOR data."""
    hotspot_x_r, hotspot_y_r = struct.unpack('<HH', data[:4])
    img_data = data[4:]
    if img_data[:4] == b'\x89PNG':
        img = Image.open(io.BytesIO(img_data))
        width = width or img.width
        height = height or img.height
        return img
    if width is None or height is None or bit_count is None:
        width_p, height_p, bit_p = _parse_bmp_header(img_data)
        width = width or width_p
        height = height or height_p
        bit_count = bit_count or bit_p
    cur_data = _build_single_cursor_cur(img_data, width, height,
                                        hotspot_x or hotspot_x_r, hotspot_y or hotspot_y_r,
                                        bit_count or 32)
    return Image.open(io.BytesIO(cur_data))


"""
Generate PNG icons from SVG for Chrome extension.
Creates 16x16, 32x32, 48x48, and 128x128 PNGs.
"""
import os
import struct
import zlib
import xml.etree.ElementTree as ET
import math

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
EXTENSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extension')
ICONS_DIR = os.path.join(ASSETS_DIR, 'icons')
os.makedirs(ICONS_DIR, exist_ok=True)

def create_png(width, height, pixels):
    """Create a minimal PNG file from RGBA pixel data."""
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', zlib.crc32(chunk) & 0xffffffff)

    # PNG signature
    sig = b'\x89PNG\r\n\x1a\n'

    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    ihdr = make_chunk(b'IHDR', ihdr_data)

    # IDAT
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # filter none
        for x in range(width):
            idx = (y * width + x) * 4
            raw_data += bytes(pixels[idx:idx+4])

    compressed = zlib.compress(raw_data)
    idat = make_chunk(b'IDAT', compressed)

    # IEND
    iend = make_chunk(b'IEND', b'')

    return sig + ihdr + idat + iend


def draw_shield_logo(size):
    """Draw the WebVeil shield+eye logo at given size."""
    pixels = [0] * (size * size * 4)  # RGBA

    cx, cy = size / 2, size / 2
    scale = size / 128.0

    def set_pixel(x, y, r, g, b, a=255):
        if 0 <= x < size and 0 <= y < size:
            idx = (int(y) * size + int(x)) * 4
            # Alpha blending
            old_a = pixels[idx + 3]
            if old_a == 0:
                pixels[idx] = r
                pixels[idx+1] = g
                pixels[idx+2] = b
                pixels[idx+3] = a
            else:
                fa = a / 255
                pixels[idx] = int(pixels[idx] * (1 - fa) + r * fa)
                pixels[idx+1] = int(pixels[idx+1] * (1 - fa) + g * fa)
                pixels[idx+2] = int(pixels[idx+2] * (1 - fa) + b * fa)
                pixels[idx+3] = min(255, old_a + a)

    def gradient_color(x, y):
        """Indigo to violet gradient."""
        t = (x + y) / (2 * size)
        t = max(0, min(1, t))
        r = int(79 * (1 - t) + 124 * t)
        g = int(70 * (1 - t) + 58 * t)
        b = int(229 * (1 - t) + 237 * t)
        return r, g, b

    def in_shield(px, py):
        """Check if point is inside shield shape."""
        # Normalize to 0-128 space
        nx = px / scale
        ny = py / scale
        # Shield: top point at (64, 8), sides curve to (16,30) and (112,30), bottom at (64, 98)
        if ny < 8 or ny > 98:
            return False
        # Top section (8 to 30): V shape from (64,8) to edges
        if ny < 30:
            t = (ny - 8) / 22
            left = 64 - 48 * t
            right = 64 + 48 * t
            return left <= nx <= right
        # Middle and bottom (30 to 98): shield body narrows
        t = (ny - 30) / 68
        width_at_y = 48 * (1 - t * t * 0.6)
        left = 64 - width_at_y
        right = 64 + width_at_y
        return left <= nx <= right

    def in_eye(px, py):
        """Check if point is inside the eye ellipse."""
        nx = px / scale
        ny = py / scale
        dx = (nx - 64) / 28
        dy = (ny - 56) / 17
        return dx*dx + dy*dy <= 1

    def in_iris(px, py):
        nx = px / scale
        ny = py / scale
        dx = nx - 64
        dy = ny - 56
        return dx*dx + dy*dy <= 11*11

    def in_pupil(px, py):
        nx = px / scale
        ny = py / scale
        dx = nx - 64
        dy = ny - 56
        return dx*dx + dy*dy <= 5*5

    # Draw pixels
    for y in range(size):
        for x in range(size):
            if in_shield(x, y):
                r, g, b = gradient_color(x, y)
                if in_eye(x, y):
                    if in_iris(x, y):
                        if in_pupil(x, y):
                            set_pixel(x, y, 255, 255, 255, 255)  # White pupil
                        else:
                            set_pixel(x, y, r, g, b, 255)  # Gradient iris
                    else:
                        set_pixel(x, y, 255, 255, 255, 240)  # White eye
                else:
                    set_pixel(x, y, r, g, b, 255)  # Shield body

    return pixels


# Generate icons at all sizes
for icon_size in [16, 32, 48, 128]:
    print(f"Generating {icon_size}x{icon_size} icon...")
    px = draw_shield_logo(icon_size)
    png_data = create_png(icon_size, icon_size, px)

    # Save to assets/icons/
    path = os.path.join(ICONS_DIR, f'icon{icon_size}.png')
    with open(path, 'wb') as f:
        f.write(png_data)
    print(f"  Saved: {path}")

    # Also copy to extension directory
    ext_path = os.path.join(EXTENSION_DIR, f'icon{icon_size}.png')
    with open(ext_path, 'wb') as f:
        f.write(png_data)
    print(f"  Copied to extension: {ext_path}")

print("\nDone! All icons generated.")

from PIL import Image, UnidentifiedImageError, ImageSequence
import io
import os
import struct

def save_resource_data_as_image(data: bytes, filepath: str, resource_type_id: int, rt_map: dict) -> bool:
    """
    Tries to save raw resource data as an image file using Pillow.
    Detects format (ICO, BMP, CUR) based on resource_type_id or filepath extension.
    Returns True on success, False on failure.
    """
    if not data:
        print("Error: No data to save.")
        return False

    try:
        img = Image.open(io.BytesIO(data))

        # Determine save format, prioritize extension if it's specific (ico, bmp, cur)
        # Otherwise, Pillow's save will try to infer from extension or use a default.
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()

        save_format = None
        if ext == ".ico" and (resource_type_id == rt_map.get("RT_ICON") or resource_type_id == rt_map.get("RT_GROUP_ICON")):
            save_format = "ICO"
        elif ext == ".bmp" and resource_type_id == rt_map.get("RT_BITMAP"):
            save_format = "BMP"
        elif ext == ".cur" and (resource_type_id == rt_map.get("RT_CURSOR") or resource_type_id == rt_map.get("RT_GROUP_CURSOR")):
            save_format = "CUR" # Pillow might not support CUR saving directly, needs check.
                                # ICO format might be used for .cur if Pillow handles it.
            # Pillow's ICO plugin can write CUR files if the extension is .cur
            if not Image.SAVE.get("CUR") and Image.SAVE.get("ICO"):
                 print("Warning: Pillow has no direct CUR save support, attempting ICO format for .cur file.")
                 save_format = "ICO" # Try saving as ICO if CUR is not supported
            elif not Image.SAVE.get("CUR"):
                 print("Error: Pillow does not support saving CUR files.")
                 return False


        if save_format:
            # For ICO, ensure all frames are saved if it's an animated or multi-icon source
            if save_format == "ICO" and hasattr(img, "n_frames") and img.n_frames > 1:
                frames = [frame.copy() for frame in ImageSequence.Iterator(img)]
                # Pillow's ICO saver handles sizes. For multi-size, pass sizes explicitly if needed.
                # Example: img.save(filepath, format=save_format, sizes=[(16,16), (32,32), (48,48)])
                # For now, default behavior.
                img.save(filepath, format=save_format, save_all=True, append_images=frames[1:])
            else:
                img.save(filepath, format=save_format)
        else: # Let Pillow infer from filepath extension
            img.save(filepath)

        print(f"Image data successfully saved to {filepath} (format: {save_format or 'inferred'}).")
        return True

    except UnidentifiedImageError:
        print(f"Error: Cannot identify image format for data to save to {filepath}.")
    except IOError as e:
        print(f"Error saving image data to {filepath}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving image: {e}")
    return False


# Placeholder for more complex BMP DIB saving if needed
def save_dib_as_bmp(dib_data: bytes, width: int, height: int, bpp: int, filepath: str) -> bool:
    """
    Creates a BMP file from raw DIB data.
    This is a more complex operation if Pillow cannot directly handle the DIB stream.
    For now, this is a placeholder. Pillow's Image.frombytes might be sufficient.
    """
    try:
        # Example mode based on bpp (this is simplified)
        mode = None
        if bpp == 24: mode = "RGB"
        elif bpp == 32: mode = "RGBA" # Assuming alpha
        elif bpp == 8: mode = "L" # Grayscale, or "P" with a palette
        # Add other modes as necessary (1-bit, 4-bit require palette handling)

        if not mode:
            print(f"Unsupported DIB bpp for direct Pillow conversion: {bpp}")
            # Fallback: just write the raw DIB data if we can't make a BMP
            # with open(filepath, "wb") as f: f.write(dib_data)
            # print(f"Wrote raw DIB data to {filepath} due to unsupported bpp for BMP conversion.")
            return False

        # Image.frombytes assumes uncompressed data. DIBs are usually uncompressed.
        # The size (width, height) must be correct.
        img = Image.frombytes(mode, (width, height), dib_data, 'raw', mode) # 'raw' decoder

        # BMPs are typically stored bottom-up, Pillow handles this by default on save.
        # If DIB data is top-down, it might need img.transpose(Image.FLIP_TOP_BOTTOM) before saving.
        # This depends on the source of the DIB data. Standard DIBs in resources are bottom-up.
        img.save(filepath, format="BMP")
        print(f"DIB data successfully saved as BMP to {filepath}")
        return True
    except Exception as e:
        print(f"Error converting DIB to BMP: {e}")
        return False


def open_raw_icon_or_cursor(data: bytes, is_cursor: bool = False):
    """Return a PIL Image from raw RT_ICON or RT_CURSOR resource data."""
    try:
        if len(data) < 40:
            return None
        header = struct.unpack('<IIIHH', data[:16])
        width = header[1]
        height = header[2] // 2 if not is_cursor else header[2] // 2
        bitcount = header[4]

        icon_dir = struct.pack('<HHH', 0, 2 if is_cursor else 1, 1)
        entry = struct.pack('<BBBBHHII',
                            width if width < 256 else 0,
                            height if height < 256 else 0,
                            0, 0,
                            1, bitcount,
                            len(data),
                            6 + 16)
        ico_data = icon_dir + entry + data
        return Image.open(io.BytesIO(ico_data))
    except Exception as e:
        print(f"Error converting raw icon/cursor: {e}")
        return None


if __name__ == "__main__":
    print("image_utils.py - contains image saving utilities.")
    # Add test cases here if you have sample data (e.g. raw DIB bytes)
    # Example:
    # dummy_rt_map = {"RT_ICON": 3, "RT_BITMAP": 2}
    # Create a dummy 1x1 red pixel BMP data
    # file_header = b'BM' + (14 + 40 + 3).to_bytes(4, 'little') + b'\x00\x00\x00\x00' + (14 + 40).to_bytes(4, 'little')
    # info_header = (40).to_bytes(4, 'little') + (1).to_bytes(4, 'little') + (1).to_bytes(4, 'little') + \
    #               (1).to_bytes(2, 'little') + (24).to_bytes(2, 'little') + b'\x00\x00\x00\x00' * 2 + \
    #               (1000).to_bytes(4, 'little') * 2 + b'\x00\x00\x00\x00' * 2
    # pixel_data = b'\x00\x00\xFF' # Red pixel (BGR)
    # dummy_bmp_data = file_header + info_header + pixel_data
    # save_resource_data_as_image(dummy_bmp_data, "test_dummy.bmp", dummy_rt_map["RT_BITMAP"], dummy_rt_map)
    # if os.path.exists("test_dummy.bmp"):
    #     print("Dummy BMP saved successfully for testing.")
    #     os.remove("test_dummy.bmp")



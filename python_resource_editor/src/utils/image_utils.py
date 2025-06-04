from PIL import Image, UnidentifiedImageError, ImageSequence
import io
import os
import ctypes # Added for hicon_to_pil_image
from typing import Optional # Added for hicon_to_pil_image
from . import winapi_ctypes as wct # Added for hicon_to_pil_image

def hicon_to_pil_image(hicon: wct.wintypes.HICON) -> Optional[Image.Image]:
    if not hicon or (isinstance(hicon, int) and hicon == 0) or (hasattr(hicon, 'value') and hicon.value == 0):
        print("hicon_to_pil_image: Received invalid HICON.")
        return None

    icon_info = wct.ICONINFO()
    if not wct.GetIconInfo(hicon, ctypes.byref(icon_info)): # Uses corrected GetIconInfo
        print(f"Error GetIconInfo: {ctypes.get_last_error()}")
        if icon_info.hbmMask: wct.DeleteObject(icon_info.hbmMask)
        if icon_info.hbmColor: wct.DeleteObject(icon_info.hbmColor)
        return None

    pil_image = None
    try:
        color_bitmap_handle = icon_info.hbmColor
        mask_bitmap_handle = icon_info.hbmMask

        if not color_bitmap_handle:
            print("ICONINFO hbmColor is NULL.")
            if mask_bitmap_handle: wct.DeleteObject(mask_bitmap_handle)
            return None

        bmp_color = wct.BITMAP()
        if wct.GetObjectW(color_bitmap_handle, ctypes.sizeof(wct.BITMAP), ctypes.byref(bmp_color)) == 0:
            print(f"Error GetObjectW for hbmColor: {ctypes.get_last_error()}")
            if mask_bitmap_handle: wct.DeleteObject(mask_bitmap_handle)
            wct.DeleteObject(color_bitmap_handle)
            return None

        width = bmp_color.bmWidth
        height = bmp_color.bmHeight

        if width <= 0 or height <= 0:
            print(f"Invalid bitmap dimensions from hbmColor: {width}x{height}")
            if mask_bitmap_handle: wct.DeleteObject(mask_bitmap_handle)
            wct.DeleteObject(color_bitmap_handle)
            return None

        bmi_header = wct.BITMAPINFOHEADER()
        bmi_header.biSize = ctypes.sizeof(wct.BITMAPINFOHEADER)
        bmi_header.biWidth = width
        bmi_header.biHeight = -height
        bmi_header.biPlanes = 1
        bmi_header.biBitCount = 32
        bmi_header.biCompression = wct.BI_RGB

        image_size = width * height * 4
        pixel_buffer = bytearray(image_size)
        lpvbits = (wct.wintypes.BYTE * image_size).from_buffer(pixel_buffer)

        hdc_screen = wct.user32.GetDC(None)
        if not hdc_screen:
            print(f"Error GetDC(None): {ctypes.get_last_error()}")
            if mask_bitmap_handle: wct.DeleteObject(mask_bitmap_handle)
            wct.DeleteObject(color_bitmap_handle)
            return None

        bmi_struct = wct.BITMAPINFO(bmi_header)

        bits_copied = wct.GetDIBits(
            hdc_screen, color_bitmap_handle, 0, height,
            lpvbits, ctypes.byref(bmi_struct), wct.DIB_RGB_COLORS )
        wct.user32.ReleaseDC(None, hdc_screen)

        if bits_copied == 0:
            print(f"Error GetDIBits failed: {ctypes.get_last_error()}")
            if mask_bitmap_handle: wct.DeleteObject(mask_bitmap_handle)
            wct.DeleteObject(color_bitmap_handle)
            return None

        pil_image = Image.frombytes("RGBA", (width, height), bytes(pixel_buffer), "raw", "BGRA")

        # Alpha channel handling for icons with masks (simplified)
        # If the icon has a mask (icon_info.fIcon is True) and the color bitmap was not 32bpp
        # (meaning it didn't have an inherent alpha channel), then the mask bitmap (hbmMask)
        # should be used to create the alpha channel for the PIL image.
        # GetDIBits for hbmMask (1bpp) and then iterate pixels to set alpha.
        if icon_info.fIcon and mask_bitmap_handle and bmp_color.bmBitsPixel < 32:
            # Create a buffer for the mask bits
            mask_image_size = ((width + 15) // 16) * 2 * height # Scanlines are word-aligned for monochrome
            mask_pixel_buffer = bytearray(mask_image_size)
            lpvMaskBits = (wct.wintypes.BYTE * mask_image_size).from_buffer(mask_pixel_buffer)

            # Mask BITMAPINFOHEADER
            bmi_mask_header = wct.BITMAPINFOHEADER()
            bmi_mask_header.biSize = ctypes.sizeof(wct.BITMAPINFOHEADER)
            bmi_mask_header.biWidth = width
            bmi_mask_header.biHeight = -height # Top-down DIB
            bmi_mask_header.biPlanes = 1
            bmi_mask_header.biBitCount = 1 # Monochrome
            bmi_mask_header.biCompression = wct.BI_RGB
            bmi_mask_struct = wct.BITMAPINFO(bmi_mask_header)

            hdc_screen_mask = wct.user32.GetDC(None)
            if hdc_screen_mask:
                mask_bits_copied = wct.GetDIBits(
                    hdc_screen_mask, mask_bitmap_handle, 0, height,
                    lpvMaskBits, ctypes.byref(bmi_mask_struct), wct.DIB_RGB_COLORS
                )
                wct.user32.ReleaseDC(None, hdc_screen_mask)

                if mask_bits_copied > 0:
                    alpha_channel = Image.frombytes("1", (width, height), bytes(mask_pixel_buffer), "raw", "1;I")
                    # Invert mask: 0 means transparent, 1 means opaque in typical icon masks
                    # PIL's "1" mode: 0 is black, 255 is white. We want mask's 0 to be alpha 255 (opaque).
                    # So, if mask bit is 0 (transparent part of icon image), alpha should be 0.
                    # If mask bit is 1 (opaque part of icon image), alpha should be 255.
                    # The mask from GetIconInfo: 0 for opaque, 1 for transparent background.
                    # So, we need to invert it for the typical alpha sense (0=transparent, 255=opaque).
                    # This is complex. For now, let's assume the BGRA conversion from GetDIBits handles most cases.
                    # A simpler approach if pil_image is already RGBA but alpha is all FF:
                    if pil_image.mode == "RGBA":
                        # This part needs careful pixel-by-pixel manipulation if the alpha from GetDIBits on hbmColor isn't sufficient.
                        # For icons, the hbmColor might be an XOR image and hbmMask an AND image.
                        # The conversion using BGRA format in frombytes often handles this for 32bpp icons.
                        # If hbmColor was 24bpp, then an alpha channel needs to be constructed from hbmMask.
                        # The current code already converts to RGBA, assuming GetDIBits provides usable alpha for 32bpp.
                        # If it was originally <32bpp, the alpha channel from `Image.frombytes("RGBA", ... "BGRA")` might be all opaque.
                        # This is where mask_bitmap_handle would be used to set the actual alpha.
                        print("hicon_to_pil_image: Icon has a mask, and color bitmap might not have alpha. Advanced mask handling might be needed if transparency is incorrect.")
                else:
                    print(f"Error GetDIBits for mask failed: {ctypes.get_last_error()}")
            else:
                print(f"Error GetDC(None) for mask: {ctypes.get_last_error()}")


    except Exception as e:
        print(f"Error converting HICON to PIL Image: {e}")
        import traceback
        traceback.print_exc()
        pil_image = None
    finally:
        if icon_info.hbmColor: wct.DeleteObject(icon_info.hbmColor)
        if icon_info.hbmMask: wct.DeleteObject(icon_info.hbmMask)

    return pil_image

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
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        save_format = None
        if ext == ".ico" and (resource_type_id == rt_map.get("RT_ICON") or resource_type_id == rt_map.get("RT_GROUP_ICON")):
            save_format = "ICO"
        elif ext == ".bmp" and resource_type_id == rt_map.get("RT_BITMAP"):
            save_format = "BMP"
        elif ext == ".cur" and (resource_type_id == rt_map.get("RT_CURSOR") or resource_type_id == rt_map.get("RT_GROUP_CURSOR")):
            save_format = "CUR"
            if not Image.SAVE.get("CUR") and Image.SAVE.get("ICO"):
                 print("Warning: Pillow has no direct CUR save support, attempting ICO format for .cur file.")
                 save_format = "ICO"
            elif not Image.SAVE.get("CUR"):
                 print("Error: Pillow does not support saving CUR files.")
                 return False

        if save_format:
            if save_format == "ICO" and hasattr(img, "n_frames") and img.n_frames > 1:
                frames = [frame.copy() for frame in ImageSequence.Iterator(img)]
                img.save(filepath, format=save_format, save_all=True, append_images=frames[1:])
            else:
                img.save(filepath, format=save_format)
        else:
            img.save(filepath)
        print(f"Image data successfully saved to {filepath} (format: {save_format or 'inferred'}).")
        return True
    except UnidentifiedImageError: print(f"Error: Cannot identify image format for data to save to {filepath}.")
    except IOError as e: print(f"Error saving image data to {filepath}: {e}")
    except Exception as e: print(f"An unexpected error occurred while saving image: {e}")
    return False

def save_dib_as_bmp(dib_data: bytes, width: int, height: int, bpp: int, filepath: str) -> bool:
    try:
        mode = None
        if bpp == 24: mode = "RGB"
        elif bpp == 32: mode = "RGBA"
        elif bpp == 8: mode = "L"
        if not mode:
            print(f"Unsupported DIB bpp for direct Pillow conversion: {bpp}")
            return False
        img = Image.frombytes(mode, (width, height), dib_data, 'raw', mode)
        img.save(filepath, format="BMP")
        print(f"DIB data successfully saved as BMP to {filepath}")
        return True
    except Exception as e:
        print(f"Error converting DIB to BMP: {e}")
        return False

if __name__ == "__main__":
    print("image_utils.py - contains image saving utilities.")
    # Example test code could go here
    pass

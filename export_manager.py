"""
export_manager.py
-----------------
Saves the finished A4 sheet to disk in the format the user picked.

Supported formats:
  * PNG  -> keeps transparency, lossless, 300 DPI
  * JPG  -> flattened onto white, smaller file, 300 DPI
  * PDF  -> a true A4 page (great for printing), 300 DPI

All exports are at 300 DPI = print quality.
"""

from PIL import Image

DPI = 300


def _flatten_on_white(img):
    """
    Put an RGBA (transparent) image onto a solid white background and return
    an RGB image. JPG and PDF do not support transparency, so we must do this
    first, otherwise transparent areas could turn black.
    """
    if img.mode != "RGBA":
        return img.convert("RGB")
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])   # split()[3] = the alpha channel
    return background


def export_png(img, path):
    """Save as PNG (keeps transparency)."""
    img.save(path, "PNG", dpi=(DPI, DPI))


def export_jpg(img, path):
    """Save as JPG (white background, quality 95)."""
    rgb = _flatten_on_white(img)
    rgb.save(path, "JPEG", dpi=(DPI, DPI), quality=95)


def export_pdf(img, path):
    """
    Save as a real A4 PDF page using reportlab.
    The image already has A4 proportions, so it fills the whole page.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.utils import ImageReader

    rgb = _flatten_on_white(img)
    page_w, page_h = A4                           # A4 size in PDF points (1/72 inch)

    c = pdf_canvas.Canvas(path, pagesize=A4)
    # Draw the image to cover the full page (0,0 is the bottom-left corner).
    c.drawImage(ImageReader(rgb), 0, 0, width=page_w, height=page_h)
    c.showPage()
    c.save()


def export(img, path, file_format):
    """
    Convenience helper: pick the right export function based on file_format,
    which should be one of: "PNG", "JPG", "PDF".
    """
    file_format = file_format.upper()
    if file_format == "PNG":
        export_png(img, path)
    elif file_format in ("JPG", "JPEG"):
        export_jpg(img, path)
    elif file_format == "PDF":
        export_pdf(img, path)
    else:
        raise ValueError("Unknown format: " + str(file_format))

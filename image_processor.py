"""
image_processor.py
------------------
All the image work happens here:

  * load_image()        -> open a file and return a PIL image (with transparency)
  * remove_background()  -> use the rembg AI model to cut out the background
  * autocrop_subject()   -> trim empty transparent space down to the actual subject
  * scale_to_fit()       -> resize an image to fit a slot WITHOUT stretching it
  * build_a4_sheet()     -> paste every photo onto the final A4 canvas

NOTE ON SPEED (important for an i3 / CPU-only machine):
  rembg uses an AI model. The FIRST time it runs it downloads a model file
  (~170 MB) from the internet and saves it in your home folder, so the first
  run needs internet and is slow. After that it works offline.
  If it is too slow, switch DEFAULT_MODEL below from "u2net" to "u2netp"
  (a smaller, faster, slightly lower-quality model).
"""

from PIL import Image
import layout_manager

# "u2net"  = best quality (slower on CPU)
# "u2netp" = lighter & faster on a weak CPU, slightly lower quality
DEFAULT_MODEL = "u2net"

# --- Smart auto-fit settings ---
# After background removal the subject (head/hair) is often small with lots of
# transparent empty space around it. These settings crop that empty space away
# and enlarge the subject so it fills most of its slot.
SUBJECT_FILL_RATIO = 0.90   # subject fills ~90% of the slot -> leaves a safe margin
AUTOCROP_PAD_RATIO = 0.04   # keep a small 4% padding around the subject when cropping
ALPHA_THRESHOLD = 12        # alpha above this counts as "part of the subject"

# We keep ONE rembg session and reuse it. Creating a session loads the model
# into memory, which is slow, so we only want to do it once.
_rembg_session = None


def _get_rembg_session(model_name=DEFAULT_MODEL):
    """Create the rembg model session once, then reuse it every time."""
    global _rembg_session
    if _rembg_session is None:
        # Imported here (not at the top) because rembg is heavy and slow to
        # import. Doing it lazily keeps the app's startup fast.
        from rembg import new_session
        _rembg_session = new_session(model_name)
    return _rembg_session


def load_image(path):
    """Open an image file and return it in RGBA mode (RGBA supports transparency)."""
    img = Image.open(path)
    return img.convert("RGBA")


def remove_background(img, model_name=DEFAULT_MODEL):
    """
    Remove the background from a single PIL image.
    Returns a new RGBA image where the background is transparent.
    """
    from rembg import remove                       # lazy import (see note above)
    session = _get_rembg_session(model_name)
    result = remove(img, session=session)          # rembg accepts & returns PIL images
    return result.convert("RGBA")


def autocrop_subject(img, alpha_threshold=ALPHA_THRESHOLD,
                     pad_ratio=AUTOCROP_PAD_RATIO):
    """
    Trim the empty transparent border around the subject.

    After background removal the image is mostly transparent with the
    person/head in the middle. We look at the alpha (transparency) channel to
    find the rectangle that actually contains the subject, then crop to it,
    keeping a small padding so hair edges are not clipped.

    If the image has no transparency (e.g. a normal photo that was NOT
    background-removed), this safely returns the image unchanged.
    """
    if img.mode != "RGBA":
        return img  # no transparency -> nothing to crop

    # Build a black/white mask: white where the subject is, black where empty.
    alpha = img.getchannel("A")
    mask = alpha.point(lambda a: 255 if a > alpha_threshold else 0)

    bbox = mask.getbbox()        # (left, top, right, bottom) of the white area
    if bbox is None:
        return img               # fully transparent -> leave as is

    left, top, right, bottom = bbox

    # Add a small safety padding around the subject.
    sub_w = right - left
    sub_h = bottom - top
    pad_x = int(sub_w * pad_ratio)
    pad_y = int(sub_h * pad_ratio)

    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(img.width, right + pad_x)
    bottom = min(img.height, bottom + pad_y)

    return img.crop((left, top, right, bottom))


def scale_to_fit(img, box_w, box_h):
    """
    Resize 'img' so it fits inside a box of size (box_w x box_h) while keeping
    its original proportions (aspect ratio). The image is NEVER stretched.

    We use the SMALLER of the two scale factors so the whole image fits.
    """
    iw, ih = img.size
    scale = min(box_w / iw, box_h / ih)
    new_w = max(1, int(iw * scale))
    new_h = max(1, int(ih * scale))
    # LANCZOS is a high-quality resizing filter -> keeps the photo sharp.
    return img.resize((new_w, new_h), Image.LANCZOS)


def build_a4_sheet(images, layout_count, bg_color=(255, 255, 255, 255),
                   smart_fit=True, fill_ratio=SUBJECT_FILL_RATIO):
    """
    Build the final A4 sheet.

    images       : list of PIL images (already background-removed or not)
    layout_count : 1, 2, 3 or 4
    bg_color     : page background colour, default solid white
    smart_fit    : if True, crop empty transparent space and enlarge the
                   subject to fill most of its slot (recommended)
    fill_ratio   : how much of the slot the subject fills (0.90 = 90%, which
                   leaves a clean safety margin so it never touches the edges)

    Only the first N images are used, where N is how many slots the layout has.
    Each image is scaled to fit its slot and centered inside it. Note: enlarging
    a small subject does resample its pixels (unavoidable when drawing onto a
    raster page), but the aspect ratio is always preserved -- nothing is stretched.
    """
    # Start with a blank A4 page.
    canvas = Image.new("RGBA",
                       (layout_manager.A4_WIDTH, layout_manager.A4_HEIGHT),
                       bg_color)

    slots = layout_manager.get_slots(layout_count)

    # zip() stops at whichever list is shorter, so extra images are ignored
    # and missing images simply leave that slot blank.
    for img, (sx, sy, sw, sh) in zip(images, slots):
        if smart_fit:
            # 1) crop away the empty transparent border around the subject
            img = autocrop_subject(img)
            # 2) shrink the target box a little so a safety margin remains
            target_w = max(1, int(sw * fill_ratio))
            target_h = max(1, int(sh * fill_ratio))
        else:
            target_w, target_h = sw, sh

        # 3) scale the (cropped) subject to fill the target box, keeping ratio
        fitted = scale_to_fit(img, target_w, target_h)
        fw, fh = fitted.size

        # 4) center the subject inside the FULL slot
        px = sx + (sw - fw) // 2
        py = sy + (sh - fh) // 2

        # alpha_composite respects transparency, so cut-out photos blend
        # cleanly onto the white page.
        canvas.alpha_composite(fitted, (px, py))

    return canvas

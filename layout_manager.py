"""
layout_manager.py
-----------------
This module knows WHERE each photo should be placed on the A4 page.

The page is treated as a grid of "slots". A slot is simply a rectangle:

        (x, y, width, height)

All numbers are in PIXELS on the full-resolution A4 canvas
(2480 x 3508 px = A4 at 300 DPI).

The actual image scaling/centering is done later in image_processor.py.
This file only does the math of "which rectangle does photo N live in".
"""

# ---------------------------------------------------------------------------
# A4 canvas size at 300 DPI
# A4 paper = 210 mm x 297 mm.
# At 300 dots-per-inch that is 2480 x 3508 pixels.
# ---------------------------------------------------------------------------
A4_WIDTH = 2480
A4_HEIGHT = 3508

# ---------------------------------------------------------------------------
# Spacing settings (in pixels). Change these if you want bigger/smaller gaps.
# ---------------------------------------------------------------------------
MARGIN = 120          # blank space between the page edge and the photos
GAP = 120             # blank space between two neighbouring photos
TOP_RATIO_3 = 0.52    # in the 3-photo layout, how much height the top photo gets


def get_slots(layout_count):
    """
    Return a list of slots for the chosen layout.

    layout_count : int  -> 1, 2, 3 or 4
    returns       : list of (x, y, width, height) rectangles
    """
    if layout_count == 1:
        return _layout_1()
    elif layout_count == 2:
        return _layout_2()
    elif layout_count == 3:
        return _layout_3()
    elif layout_count == 4:
        return _layout_4()
    else:
        raise ValueError("layout_count must be 1, 2, 3 or 4")


def _usable_area():
    """The rectangle inside the page margins where photos are allowed."""
    x = MARGIN
    y = MARGIN
    w = A4_WIDTH - 2 * MARGIN
    h = A4_HEIGHT - 2 * MARGIN
    return x, y, w, h


def _layout_1():
    """One big photo filling the whole usable area, centered."""
    x, y, w, h = _usable_area()
    return [(x, y, w, h)]


def _layout_2():
    """Two photos: one on top, one on the bottom, equal heights."""
    x, y, w, h = _usable_area()
    slot_h = (h - GAP) // 2                     # split height into two equal parts
    top = (x, y, w, slot_h)
    bottom = (x, y + slot_h + GAP, w, slot_h)   # push the second one down past the gap
    return [top, bottom]


def _layout_3():
    """
    Three photos (classic medical documentation style):
        - one wide photo across the top
        - two photos side-by-side on the bottom (left + right)
    """
    x, y, w, h = _usable_area()

    top_h = int((h - GAP) * TOP_RATIO_3)        # top photo gets a bit more height
    bottom_h = (h - GAP) - top_h
    col_w = (w - GAP) // 2                       # bottom row is split into two columns

    top = (x, y, w, top_h)                       # full width on top
    by = y + top_h + GAP                         # y position of the bottom row
    bottom_left = (x, by, col_w, bottom_h)
    bottom_right = (x + col_w + GAP, by, col_w, bottom_h)
    return [top, bottom_left, bottom_right]


def _layout_4():
    """Four photos in a clean 2x2 grid (TL, TR, BL, BR)."""
    x, y, w, h = _usable_area()
    col_w = (w - GAP) // 2
    row_h = (h - GAP) // 2

    top_left = (x, y, col_w, row_h)
    top_right = (x + col_w + GAP, y, col_w, row_h)
    bottom_left = (x, y + row_h + GAP, col_w, row_h)
    bottom_right = (x + col_w + GAP, y + row_h + GAP, col_w, row_h)
    return [top_left, top_right, bottom_left, bottom_right]

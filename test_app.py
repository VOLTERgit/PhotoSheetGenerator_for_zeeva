"""
test_app.py
-----------
Unit tests for the parts of the app that do NOT need a window:
  * layout_manager  (slot geometry)
  * image_processor (scaling + A4 compositing)
  * export_manager  (PNG / JPG / PDF output)

Run it with:
    python test_app.py

It prints PASS/FAIL for each check and exits with code 1 if anything fails.
(No external test framework needed.)
"""

import os
import tempfile
from PIL import Image

import layout_manager
import image_processor
import export_manager

_FAILS = []


def check(condition, message):
    print(("PASS" if condition else "FAIL") + " - " + message)
    if not condition:
        _FAILS.append(message)


# ---------------------------------------------------------------------------
# layout_manager
# ---------------------------------------------------------------------------
def test_layouts():
    W, H = layout_manager.A4_WIDTH, layout_manager.A4_HEIGHT
    check((W, H) == (2480, 3508), "A4 canvas is 2480 x 3508 (300 DPI)")

    for n in (1, 2, 3, 4):
        slots = layout_manager.get_slots(n)
        check(len(slots) == n, f"layout {n} returns exactly {n} slot(s)")
        for (x, y, w, h) in slots:
            inside = (x >= 0 and y >= 0 and x + w <= W and y + h <= H and w > 0 and h > 0)
            check(inside, f"layout {n}: slot ({x},{y},{w},{h}) stays inside the page")

    # invalid layout numbers must raise
    try:
        layout_manager.get_slots(5)
        check(False, "layout 5 should raise ValueError")
    except ValueError:
        check(True, "invalid layout count raises ValueError")


# ---------------------------------------------------------------------------
# image_processor.scale_to_fit  (must NEVER stretch / distort)
# ---------------------------------------------------------------------------
def test_scaling_keeps_aspect_ratio():
    cases = [
        (1200, 1600),   # portrait
        (1600, 1200),   # landscape
        (1000, 1000),   # square
        (300, 2000),    # very tall
        (4000, 500),    # very wide
    ]
    box_w, box_h = 1060, 1574
    for iw, ih in cases:
        img = Image.new("RGBA", (iw, ih))
        fitted = image_processor.scale_to_fit(img, box_w, box_h)
        fw, fh = fitted.size

        # 1) it must fit inside the box
        check(fw <= box_w and fh <= box_h,
              f"{iw}x{ih} fits inside {box_w}x{box_h}")

        # 2) NO STRETCH: both axes must use the SAME scale factor. We verify the
        #    output equals the proportionally-scaled size within 1 pixel
        #    (integer pixel rounding can only ever differ by <1px per axis).
        scale = min(box_w / iw, box_h / ih)
        no_stretch = abs(fw - iw * scale) <= 1 and abs(fh - ih * scale) <= 1
        check(no_stretch, f"{iw}x{ih} scaled by one factor (no stretch)")


# ---------------------------------------------------------------------------
# image_processor.build_a4_sheet  (centering + correct canvas)
# ---------------------------------------------------------------------------
def test_build_sheet():
    photos = [Image.new("RGBA", (1200, 1600), (200, 60, 60, 255)),
              Image.new("RGBA", (1600, 1200), (60, 120, 200, 255)),
              Image.new("RGBA", (1000, 1000), (60, 180, 90, 255)),
              Image.new("RGBA", (800, 1400), (200, 170, 40, 255))]

    for n in (1, 2, 3, 4):
        sheet = image_processor.build_a4_sheet(photos, n)
        check(sheet.size == (2480, 3508), f"layout {n}: built sheet is A4 size")

    # Fewer images than slots should NOT crash (extra slots just stay blank).
    sheet = image_processor.build_a4_sheet(photos[:2], 4)
    check(sheet.size == (2480, 3508), "fewer images than slots does not crash")


# ---------------------------------------------------------------------------
# export_manager  (all three formats produce valid files at 300 DPI)
# ---------------------------------------------------------------------------
def test_exports():
    sheet = image_processor.build_a4_sheet(
        [Image.new("RGBA", (1000, 1400), (120, 120, 120, 255))], 1)

    tmp = tempfile.mkdtemp()
    png = os.path.join(tmp, "s.png")
    jpg = os.path.join(tmp, "s.jpg")
    pdf = os.path.join(tmp, "s.pdf")

    export_manager.export(sheet, png, "PNG")
    export_manager.export(sheet, jpg, "JPG")
    export_manager.export(sheet, pdf, "PDF")

    # PNG / JPG: correct pixel size + 300 DPI
    for path, name in [(png, "PNG"), (jpg, "JPG")]:
        im = Image.open(path)
        check(im.size == (2480, 3508), f"{name} export is 2480x3508")
        dpi = tuple(round(d) for d in im.info.get("dpi", (0, 0)))
        check(dpi == (300, 300), f"{name} export is 300 DPI")

    # PDF: starts with the PDF magic bytes and is non-empty
    head = open(pdf, "rb").read(5)
    check(head == b"%PDF-", "PDF export has a valid PDF header")
    check(os.path.getsize(pdf) > 1000, "PDF export is a non-empty file")

    # Unknown format must raise
    try:
        export_manager.export(sheet, "x.bmp", "BMP")
        check(False, "unknown export format should raise")
    except ValueError:
        check(True, "unknown export format raises ValueError")


def main():
    test_layouts()
    test_scaling_keeps_aspect_ratio()
    test_build_sheet()
    test_exports()
    print("=" * 50)
    if _FAILS:
        print(f"{len(_FAILS)} TEST(S) FAILED: {_FAILS}")
        raise SystemExit(1)
    print("ALL UNIT TESTS PASSED")


if __name__ == "__main__":
    main()

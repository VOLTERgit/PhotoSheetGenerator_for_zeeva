"""
test_gui.py
-----------
Integration tests that build the REAL window and drive it like a user would:
upload images, switch all layouts, refresh the preview, run the background
removal thread (mocked so no model download), validate, and export.

Run it with:
    python test_gui.py                 (Windows / macOS)
    xvfb-run -a python test_gui.py     (headless Linux servers)

Background removal is replaced with a fast stand-in so the test does not need
the ~170 MB AI model. The real app still uses rembg normally.
"""

import os
import time
import tempfile

import ui
import image_processor
import layout_manager

_FAILS = []


def check(condition, message):
    print(("PASS" if condition else "FAIL") + " - " + message)
    if not condition:
        _FAILS.append(message)


def main():
    tmp = tempfile.mkdtemp()
    from PIL import Image
    paths = []
    for name, (w, h), color in [("p1.png", (1200, 1600), (200, 60, 60)),
                                ("p2.jpg", (1600, 1200), (60, 120, 200)),
                                ("p3.png", (1000, 1000), (60, 180, 90)),
                                ("p4.jpg", (800, 1400), (200, 170, 40))]:
        p = os.path.join(tmp, name)
        Image.new("RGB", (w, h), color).save(p)
        paths.append(p)

    # also write a non-image file to prove it is ignored
    junk = os.path.join(tmp, "notes.txt")
    open(junk, "w").write("not an image")

    # ---- silence dialogs and mock background removal ----
    warnings = []
    ui.messagebox.showwarning = lambda *a, **k: warnings.append("warn")
    ui.messagebox.showerror = lambda *a, **k: warnings.append("err")
    ui.messagebox.showinfo = lambda *a, **k: None
    ui.messagebox.askyesno = lambda *a, **k: True
    save_target = {"path": ""}
    ui.filedialog.asksaveasfilename = lambda **k: save_target["path"]
    image_processor.remove_background = lambda img, model_name="u2net": img.convert("RGBA")

    app = ui.App()
    app.update()

    # 1) uploading: junk file ignored, 4 valid images loaded
    app.add_paths(paths + [junk]); app.update()
    check(len(app.original_images) == 4, "non-image file is ignored, 4 valid loaded")
    check(app.sheet_cache is not None, "preview sheet built after upload")

    # 2) drag & drop path parsing (handles spaces wrapped in {braces})
    parsed = app.tk.splitlist("{/a/b c.png} /d/e.jpg")
    check(list(parsed) == ["/a/b c.png", "/d/e.jpg"],
          "drag&drop path parser handles spaces correctly")

    # 3) every layout builds + preview + zoom
    for label in ["1 Photo", "2 Photos", "3 Photos", "4 Photos"]:
        app.layout_var.set(label); app.on_layout_change(); app.update()
        check(app.sheet_cache.size == (layout_manager.A4_WIDTH, layout_manager.A4_HEIGHT),
              f"{label}: A4 sheet built")
        app.zoom_in(); app.zoom_out(); app.zoom_fit(); app.update()
        check(app._preview_photo is not None, f"{label}: preview image displayed")

    # 4) validation: 4-photo layout with only 2 images -> warns, no file
    app.clear_images(); app.add_paths(paths[:2]); app.update()
    app.layout_var.set("4 Photos"); app.on_layout_change(); app.update()
    warnings.clear(); save_target["path"] = os.path.join(tmp, "nope.png")
    app.export_clicked(); app.update()
    check("warn" in warnings, "warns when fewer images than layout needs")
    check(not os.path.exists(save_target["path"]), "no file saved on validation fail")

    # 5) export works in all three formats
    app.clear_images(); app.add_paths(paths); app.update()
    app.layout_var.set("4 Photos"); app.on_layout_change(); app.update()
    for fmt, ext in [("PNG", ".png"), ("JPG", ".jpg"), ("PDF", ".pdf")]:
        app.format_var.set(fmt)
        save_target["path"] = os.path.join(tmp, "out" + ext)
        app.export_clicked(); app.update()
        check(os.path.exists(save_target["path"]) and
              os.path.getsize(save_target["path"]) > 0,
              f"export {fmt} produced a file")

    # 6) background removal thread (mocked) completes + progress hits 100%
    app.progress.set(0)
    app.remove_background_clicked()
    t0 = time.time()
    while any(p is None for p in app.processed_images) and time.time() - t0 < 10:
        app.update(); time.sleep(0.02)
    check(all(p is not None for p in app.processed_images),
          "background removal thread processed every image")
    check(abs(app.progress.get() - 1.0) < 1e-6, "progress bar reaches 100%")

    # 7) export with zero images -> warns, no crash
    app.clear_images(); app.update()
    warnings.clear()
    app.export_clicked(); app.update()
    check("warn" in warnings, "export with no images warns instead of crashing")

    app.destroy()
    print("=" * 50)
    if _FAILS:
        print(f"{len(_FAILS)} GUI TEST(S) FAILED: {_FAILS}")
        raise SystemExit(1)
    print("ALL GUI TESTS PASSED")


if __name__ == "__main__":
    main()

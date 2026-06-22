"""
ui.py
-----
The whole user interface, built with CustomTkinter (modern dark-mode look).

Layout of the window:
  LEFT  panel  -> all the controls (upload, remove background, layout,
                  export format, export button, progress bar, status text)
  RIGHT panel  -> a live A4 preview with zoom in / zoom out / fit buttons

It also supports Drag & Drop (via tkinterdnd2). If tkinterdnd2 is not
installed the app still runs perfectly, just without drag & drop.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

import image_processor
import layout_manager
import export_manager

# ---------------------------------------------------------------------------
# Try to load drag & drop support. If it is missing we simply turn it off.
# ---------------------------------------------------------------------------
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False

# Maps the friendly dropdown text to a number of photos.
LAYOUT_OPTIONS = {
    "1 Photo": 1,
    "2 Photos": 2,
    "3 Photos": 3,
    "4 Photos": 4,
}

# File types we accept for upload.
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")

# Appearance settings.
ctk.set_appearance_mode("dark")        # dark mode as requested
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------
# Combine CustomTkinter's window (CTk) with tkinterdnd2 so we get BOTH the
# modern look AND drag & drop. This little trick is the standard way to do it.
# ---------------------------------------------------------------------------
if DND_AVAILABLE:
    class BaseTk(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)
else:
    class BaseTk(ctk.CTk):
        pass


class App(BaseTk):
    """The main application window."""

    def __init__(self):
        super().__init__()

        self.title("A4 Hair Transplant Photo Sheet Generator")
        self.geometry("1180x780")
        self.minsize(1000, 680)

        # -------------------- application state --------------------
        self.image_paths = []        # file paths the user added
        self.original_images = []    # PIL images as loaded from disk
        self.processed_images = []   # background-removed images (None until done)
        self.sheet_cache = None      # the last-built full-resolution A4 image
        self.zoom = 0.16             # preview zoom (0.16 ~ fits A4 in the panel)

        # -------------------- build the window --------------------
        self._build_layout()
        self._build_controls()
        self._build_preview()
        self._enable_drag_and_drop()

        self.set_status("Ready. Upload some photos to begin.")
        self._update_count_label()

    # =======================================================================
    # WINDOW SKELETON
    # =======================================================================
    def _build_layout(self):
        """Create the two main columns: controls (left) and preview (right)."""
        self.grid_columnconfigure(0, weight=0)   # left column: fixed width
        self.grid_columnconfigure(1, weight=1)   # right column: grows
        self.grid_rowconfigure(0, weight=1)

        self.left_panel = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew")
        self.left_panel.grid_propagate(False)

        self.right_panel = ctk.CTkFrame(self, corner_radius=0)
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel.grid_rowconfigure(1, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

    # =======================================================================
    # LEFT PANEL: all the controls
    # =======================================================================
    def _build_controls(self):
        pad = {"padx": 20, "pady": (10, 0)}

        title = ctk.CTkLabel(
            self.left_panel,
            text="Photo Sheet Generator",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(anchor="w", padx=20, pady=(20, 4))

        subtitle = ctk.CTkLabel(
            self.left_panel,
            text="Hair Transplant Documentation",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        )
        subtitle.pack(anchor="w", padx=20, pady=(0, 16))

        # ---- Drop zone (also works as a visual hint) ----
        dnd_text = ("Drag & drop images here\nor use the button below"
                    if DND_AVAILABLE else
                    "Drag & drop not available\nuse the button below")
        self.drop_zone = ctk.CTkLabel(
            self.left_panel,
            text=dnd_text,
            height=70,
            fg_color=("gray85", "gray20"),
            corner_radius=8,
            font=ctk.CTkFont(size=12),
        )
        self.drop_zone.pack(fill="x", padx=20, pady=(0, 10))

        # ---- Upload button ----
        self.upload_btn = ctk.CTkButton(
            self.left_panel, text="📁  Upload Images",
            command=self.upload_images,
        )
        self.upload_btn.pack(fill="x", **pad)

        # ---- Clear button ----
        self.clear_btn = ctk.CTkButton(
            self.left_panel, text="🗑  Clear All",
            fg_color="gray30", hover_color="gray25",
            command=self.clear_images,
        )
        self.clear_btn.pack(fill="x", **pad)

        # ---- count label ----
        self.count_label = ctk.CTkLabel(
            self.left_panel, text="0 images loaded",
            font=ctk.CTkFont(size=12), text_color="gray70",
        )
        self.count_label.pack(anchor="w", padx=20, pady=(8, 0))

        # ---- Remove background button ----
        self.remove_bg_btn = ctk.CTkButton(
            self.left_panel, text="✂  Remove Background",
            command=self.remove_background_clicked,
        )
        self.remove_bg_btn.pack(fill="x", padx=20, pady=(18, 0))

        # ---- Layout dropdown ----
        layout_lbl = ctk.CTkLabel(self.left_panel, text="Layout",
                                  font=ctk.CTkFont(size=13, weight="bold"))
        layout_lbl.pack(anchor="w", padx=20, pady=(18, 2))

        self.layout_var = ctk.StringVar(value="1 Photo")
        self.layout_menu = ctk.CTkOptionMenu(
            self.left_panel,
            values=list(LAYOUT_OPTIONS.keys()),
            variable=self.layout_var,
            command=self.on_layout_change,
        )
        self.layout_menu.pack(fill="x", padx=20)

        # ---- Smart auto-fit toggle ----
        # When on, the subject is cropped out of the empty transparent space
        # and enlarged to fill most of its slot (best after background removal).
        self.autofit_var = ctk.BooleanVar(value=True)
        self.autofit_check = ctk.CTkCheckBox(
            self.left_panel,
            text="Smart auto-fit subject",
            variable=self.autofit_var,
            command=self.rebuild_sheet,
        )
        self.autofit_check.pack(anchor="w", padx=20, pady=(12, 0))

        # ---- Export format dropdown ----
        fmt_lbl = ctk.CTkLabel(self.left_panel, text="Export format",
                               font=ctk.CTkFont(size=13, weight="bold"))
        fmt_lbl.pack(anchor="w", padx=20, pady=(18, 2))

        self.format_var = ctk.StringVar(value="PDF")
        self.format_menu = ctk.CTkOptionMenu(
            self.left_panel, values=["PNG", "JPG", "PDF"],
            variable=self.format_var,
        )
        self.format_menu.pack(fill="x", padx=20)

        # ---- Export button ----
        self.export_btn = ctk.CTkButton(
            self.left_panel, text="💾  Export Sheet",
            fg_color="#2e7d32", hover_color="#1b5e20",
            command=self.export_clicked,
        )
        self.export_btn.pack(fill="x", padx=20, pady=(18, 0))

        # ---- Progress bar ----
        self.progress = ctk.CTkProgressBar(self.left_panel)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=20, pady=(18, 4))

        # ---- Status text (wraps so long messages stay readable) ----
        self.status_label = ctk.CTkLabel(
            self.left_panel, text="", font=ctk.CTkFont(size=11),
            text_color="gray70", wraplength=280, justify="left",
        )
        self.status_label.pack(anchor="w", padx=20, pady=(4, 16))

    # =======================================================================
    # RIGHT PANEL: the live preview + zoom controls
    # =======================================================================
    def _build_preview(self):
        # Top bar with the zoom buttons.
        bar = ctk.CTkFrame(self.right_panel, height=44, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(bar, text="Live A4 Preview",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(side="left", padx=16, pady=8)

        self.zoom_in_btn = ctk.CTkButton(bar, text="＋", width=40,
                                         command=self.zoom_in)
        self.zoom_out_btn = ctk.CTkButton(bar, text="－", width=40,
                                          command=self.zoom_out)
        self.zoom_fit_btn = ctk.CTkButton(bar, text="Fit", width=50,
                                          command=self.zoom_fit)
        self.zoom_label = ctk.CTkLabel(bar, text="16%", width=50)

        self.zoom_fit_btn.pack(side="right", padx=(0, 16), pady=8)
        self.zoom_in_btn.pack(side="right", padx=4, pady=8)
        self.zoom_label.pack(side="right", padx=4, pady=8)
        self.zoom_out_btn.pack(side="right", padx=4, pady=8)

        # Scrollable area so a zoomed-in page can be scrolled around.
        self.preview_frame = ctk.CTkScrollableFrame(self.right_panel,
                                                    fg_color=("gray80", "gray15"))
        self.preview_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # We use a plain tk.Label (not CTkLabel) for the image. CTkLabel needs a
        # CTkImage, and swapping CTkImages in/out repeatedly causes a known
        # "image doesn't exist" crash. A tk.Label + ImageTk.PhotoImage that we
        # keep a strong reference to is rock-solid for a live-updating preview.
        self.preview_label = tk.Label(self.preview_frame, bd=0,
                                      bg="#242424", fg="#9a9a9a")
        self.preview_label.pack(expand=True)
        self._preview_photo = None       # strong reference so Tk keeps the image

        self._show_placeholder()

    def _show_placeholder(self):
        # image="" clears any image; we keep only the helper text.
        self._preview_photo = None
        self.preview_label.configure(
            image="",
            text="No preview yet.\nUpload images and pick a layout.",
            font=("Arial", 14),
        )

    # =======================================================================
    # DRAG & DROP
    # =======================================================================
    def _enable_drag_and_drop(self):
        if not DND_AVAILABLE:
            return
        # Register both the drop zone and the preview area as drop targets.
        for widget in (self.drop_zone, self.preview_frame):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self.handle_drop)

    def handle_drop(self, event):
        # event.data is a string of paths; splitlist parses it correctly even
        # when paths contain spaces (those are wrapped in {curly braces}).
        paths = self.tk.splitlist(event.data)
        self.add_paths(paths)

    # =======================================================================
    # IMAGE LOADING
    # =======================================================================
    def upload_images(self):
        paths = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[("Image files", "*.jpg *.jpeg *.png"),
                       ("All files", "*.*")],
        )
        if paths:
            self.add_paths(paths)

    def add_paths(self, paths):
        """Add valid image files to the project and refresh the preview."""
        added = 0
        for p in paths:
            if not p.lower().endswith(VALID_EXTENSIONS):
                continue                       # skip non-image files silently
            try:
                img = image_processor.load_image(p)
            except Exception as e:
                messagebox.showerror("Could not open image",
                                     f"{os.path.basename(p)}\n\n{e}")
                continue
            self.image_paths.append(p)
            self.original_images.append(img)
            self.processed_images.append(None)  # no background removal yet
            added += 1

        if added == 0:
            self.set_status("No valid images were added (use JPG, JPEG or PNG).")
            return

        self.set_status(f"Added {added} image(s).")
        self._update_count_label()
        self.rebuild_sheet()

    def clear_images(self):
        self.image_paths.clear()
        self.original_images.clear()
        self.processed_images.clear()
        self.sheet_cache = None
        self.progress.set(0)
        self._update_count_label()
        self._show_placeholder()
        self.set_status("Cleared all images.")

    def _update_count_label(self):
        n = len(self.original_images)
        needed = self._needed_count()
        self.count_label.configure(text=f"{n} images loaded  (layout needs {needed})")

    def _needed_count(self):
        return LAYOUT_OPTIONS[self.layout_var.get()]

    # =======================================================================
    # BACKGROUND REMOVAL
    #
    # Tkinter is NOT thread-safe: a worker thread must never call any Tk method
    # (including .after). So the worker only does the heavy AI work and pushes
    # results onto a thread-safe queue. The MAIN thread polls that queue with
    # .after() and safely updates the progress bar, status text and preview.
    # =======================================================================
    def remove_background_clicked(self):
        if not self.original_images:
            messagebox.showwarning("No images",
                                   "Please upload at least one image first.")
            return
        # Disable buttons while we work so the user cannot start it twice.
        self._set_buttons_enabled(False)
        self.progress.set(0)
        self.set_status("Removing backgrounds...\n(The first run downloads the AI "
                        "model and can take a minute. Please wait.)")

        self._bg_queue = queue.Queue()
        self._bg_total = len(self.original_images)
        # Pass a *copy* of the image list to the worker so it never touches
        # shared UI state directly.
        worker = threading.Thread(
            target=self._bg_worker,
            args=(list(self.original_images), self._bg_queue),
            daemon=True,
        )
        worker.start()
        # Start polling the queue from the main thread.
        self.after(100, self._poll_bg_queue)

    @staticmethod
    def _bg_worker(images, out_queue):
        """Runs in a background thread. Touches NO Tk objects."""
        for i, img in enumerate(images):
            try:
                processed = image_processor.remove_background(img)
                out_queue.put(("ok", i, processed))
            except Exception as e:
                out_queue.put(("error", i, str(e)))
        out_queue.put(("done", None, None))

    def _poll_bg_queue(self):
        """Runs on the main thread; safe to update widgets here."""
        try:
            while True:
                kind, index, payload = self._bg_queue.get_nowait()

                if kind == "ok":
                    self.processed_images[index] = payload
                elif kind == "error":
                    # Keep the original image for this one and report the error.
                    self.processed_images[index] = self.original_images[index]
                    messagebox.showerror("Background removal failed", str(payload))
                elif kind == "done":
                    self.progress.set(1)
                    self.set_status("Background removal complete.")
                    self._set_buttons_enabled(True)
                    self.rebuild_sheet()
                    return                      # stop polling

                # Update progress after each finished image.
                done = sum(1 for p in self.processed_images if p is not None)
                self.progress.set(done / max(1, self._bg_total))
        except queue.Empty:
            pass

        # Not finished yet -> check again shortly.
        self.after(100, self._poll_bg_queue)

    def _set_buttons_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for btn in (self.upload_btn, self.remove_bg_btn,
                    self.export_btn, self.clear_btn):
            btn.configure(state=state)

    # =======================================================================
    # BUILDING + SHOWING THE PREVIEW
    # =======================================================================
    def on_layout_change(self, _value=None):
        self._update_count_label()
        self.rebuild_sheet()

    def _images_for_sheet(self):
        """
        Return the list of images to place: use the background-removed version
        if it exists, otherwise fall back to the original.
        """
        result = []
        for original, processed in zip(self.original_images, self.processed_images):
            result.append(processed if processed is not None else original)
        return result

    def rebuild_sheet(self):
        """Build the full-resolution A4 sheet and refresh what is shown."""
        if not self.original_images:
            self._show_placeholder()
            return

        layout_count = self._needed_count()
        images = self._images_for_sheet()
        # build_a4_sheet only uses the first 'layout_count' images automatically.
        self.sheet_cache = image_processor.build_a4_sheet(
            images, layout_count, smart_fit=self.autofit_var.get())
        self._refresh_preview_display()

    def _refresh_preview_display(self):
        """Resize the cached A4 sheet to the current zoom and show it."""
        if self.sheet_cache is None:
            return

        disp_w = max(1, int(layout_manager.A4_WIDTH * self.zoom))
        disp_h = max(1, int(layout_manager.A4_HEIGHT * self.zoom))

        # Resize a copy of the full-res sheet down to the display size.
        # BILINEAR is fast and looks fine for an on-screen preview.
        resized = self.sheet_cache.resize((disp_w, disp_h), Image.BILINEAR)

        # Keep a strong reference in self._preview_photo, otherwise Tk would
        # garbage-collect the image and show a blank label.
        self._preview_photo = ImageTk.PhotoImage(resized)
        self.preview_label.configure(image=self._preview_photo, text="")
        self.zoom_label.configure(text=f"{int(self.zoom * 100)}%")

    # ---- zoom controls ----
    def zoom_in(self):
        self.zoom = min(self.zoom * 1.25, 1.0)
        self._refresh_preview_display()

    def zoom_out(self):
        self.zoom = max(self.zoom / 1.25, 0.05)
        self._refresh_preview_display()

    def zoom_fit(self):
        self.zoom = 0.16
        self._refresh_preview_display()

    # =======================================================================
    # EXPORT
    # =======================================================================
    def export_clicked(self):
        # 1) Must have a built sheet.
        if self.sheet_cache is None or not self.original_images:
            messagebox.showwarning("Nothing to export",
                                   "Please upload images first.")
            return

        # 2) Validate that the number of photos matches the chosen layout.
        needed = self._needed_count()
        have = len(self.original_images)
        if have < needed:
            messagebox.showwarning(
                "Not enough images",
                f"This layout needs {needed} image(s), but you uploaded {have}.\n\n"
                f"Please upload {needed} images.")
            return
        if have > needed:
            # Not an error, just let them know extras are ignored.
            proceed = messagebox.askyesno(
                "Extra images",
                f"You uploaded {have} images but the '{self.layout_var.get()}' "
                f"layout only uses {needed}.\n\nExport using the first {needed}?")
            if not proceed:
                return

        # 3) Ask where to save.
        fmt = self.format_var.get()
        ext = {"PNG": ".png", "JPG": ".jpg", "PDF": ".pdf"}[fmt]
        path = filedialog.asksaveasfilename(
            title="Save sheet as",
            defaultextension=ext,
            initialfile=f"photo_sheet{ext}",
            filetypes=[(f"{fmt} file", f"*{ext}")],
        )
        if not path:
            return

        # 4) Save it.
        try:
            export_manager.export(self.sheet_cache, path, fmt)
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
            return

        self.set_status(f"Saved: {os.path.basename(path)}")
        messagebox.showinfo("Done", f"Sheet exported successfully:\n{path}")

    # =======================================================================
    # SMALL HELPERS
    # =======================================================================
    def set_status(self, text):
        self.status_label.configure(text=text)

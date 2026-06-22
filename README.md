# A4 Hair Transplant Photo Sheet Generator

A simple desktop app that takes patient photos, removes their backgrounds, and
arranges them on a print-ready **A4 sheet** (2480 × 3508 px, 300 DPI). Built
with **CustomTkinter** in dark mode.

---

## Features

- Upload multiple JPG / JPEG / PNG photos (button **or** drag & drop)
- One-click AI background removal (transparent cut-outs) using `rembg`
- Four layouts: **1, 2, 3, or 4 photos** per page
- Photos are auto-scaled to fit, **never stretched**, always centered
- Live A4 preview with zoom in / out / fit
- Export to **PNG, JPG, or PDF** at 300 DPI print quality
- Friendly warnings (e.g. "Please upload 4 images")

---

## Folder structure

```
A4_Hair_Transplant_Photo_Sheet_Generator/
├── main.py              # run this to start the app
├── ui.py                # the CustomTkinter interface
├── image_processor.py   # load / background-removal / scaling / compositing
├── layout_manager.py    # where each photo goes on the page
├── export_manager.py    # save as PNG / JPG / PDF
├── assets/              # put an icon (icon.ico) here if you want one
├── requirements.txt
└── README.md
```

---

## 1. Install (one time)

You need **Python 3.10 or 3.11** (recommended — `rembg` works best on these).

```bash
# from inside the project folder
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

## 2. Run

```bash
python main.py
```

> **First background removal is slow.** The very first time you click
> "Remove Background", `rembg` downloads an AI model (~170 MB) and saves it in
> your home folder (`C:\Users\<you>\.u2net`). This needs internet **once**.
> After that it works offline.

---

## Performance tips for a weak CPU (e.g. Intel i3)

Background removal runs on the CPU, so it can take a few seconds per image.
To make it faster, open **`image_processor.py`** and change:

```python
DEFAULT_MODEL = "u2net"     # best quality (slower)
```
to:
```python
DEFAULT_MODEL = "u2netp"    # lighter & faster, slightly lower quality
```

Process photos one or two at a time rather than 10 at once on a slow machine.

---

## 3. Build a .exe for the doctor (Windows)

So the doctor can just double-click an icon — no Python needed.

```bash
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed ^
  --name "PhotoSheetGenerator" ^
  --collect-all customtkinter ^
  --collect-all tkinterdnd2 ^
  --collect-all rembg ^
  --collect-all onnxruntime ^
  main.py
```

The finished program appears in the **`dist/`** folder as
`PhotoSheetGenerator.exe`.

### Important notes about the .exe

1. **The AI model is NOT bundled.** On the doctor's PC, the first time they
   click "Remove Background" the app downloads the model (~170 MB) and needs
   internet **that one time only**. To avoid this, copy your own
   `C:\Users\<you>\.u2net` folder onto the doctor's machine at the same path
   (`C:\Users\<doctor>\.u2net`).
2. The first launch of a one-file exe is a little slow (it unpacks itself).
3. To add a custom icon, put `icon.ico` in `assets/` and add
   `--icon assets/icon.ico` to the command above.

---

## How the layouts look

```
1 Photo            2 Photos           3 Photos           4 Photos
┌──────────┐       ┌──────────┐       ┌──────────┐       ┌────┬────┐
│          │       │ PHOTO 1  │       │  PHOTO 1 │       │ P1 │ P2 │
│ PHOTO 1  │       ├──────────┤       ├────┬─────┤       ├────┼────┤
│          │       │ PHOTO 2  │       │ P2 │ P3  │       │ P3 │ P4 │
└──────────┘       └──────────┘       └────┴─────┘       └────┴────┘
```

---

## Running the tests

The project ships with two test files:

```bash
python test_app.py     # unit tests: layouts, scaling, A4 build, PNG/JPG/PDF export
python test_gui.py     # integration tests: drives the real window like a user
```

On a headless Linux server, run the GUI test under a virtual display:

```bash
xvfb-run -a python test_gui.py
```

`test_gui.py` mocks the AI background removal, so it runs fast and needs no
model download.

---

## Troubleshooting

- **Drag & drop does nothing** → `tkinterdnd2` isn't installed correctly. The
  app still works with the Upload button. Re-run `pip install tkinterdnd2`.
- **`rembg` install error** → make sure `onnxruntime` installed too, and that
  you are on Python 3.10 / 3.11.
- **Preview looks small** → use the **＋** zoom button in the preview bar.
```

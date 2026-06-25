# Box Annotator

A small desktop tool for drawing bounding boxes on images and saving them to
`annotations.json`. Built for the tree-detector training workflow.

## What it does

- Loads every image from `raw_images/`
- Lets you draw boxes by click-dragging on the image
- Saves boxes to `annotations.json` as `[x1, y1, x2, y2]` in **original image
  pixels** (top-left and bottom-right corners), e.g.:

```json
{
    "tile_001.jpg": [[120, 80, 140, 100], [310, 150, 330, 170]],
    "tile_002.jpg": [[45, 200, 65, 220], [180, 280, 200, 300]]
}
```

Every image in `raw_images/` appears in the file; images with no boxes get an
empty list (`[]`).

## Setup & run

Requires Python 3 with `tkinter` (bundled with most Python installs) and
Pillow.

```bash
# from the Training Classifier folder
python annotate.py
```

### One-click launch (macOS)
Double-click `run.command`. It reuses an active virtual environment if one is
set, otherwise creates a local `venv/` and installs the dependencies for you.

> If macOS blocks it, right-click `run.command` → Open, or run
> `chmod +x run.command` once in Terminal.

## Controls

| Action | How |
| --- | --- |
| Draw a box | Click and drag on the image |
| Delete a box | Right-click (or Control-click) on it |
| Undo last box | `Ctrl+Z` / `Cmd+Z`, or the **Undo** button |
| Clear all boxes on image | **Clear image** button |
| Previous / next image | `A` / `D` or `←` / `→` or toolbar buttons |
| Save | `S` or the **Save** button |

Notes:
- Boxes auto-save when you switch images and when you close the window.
- The image is scaled to fit the window, but saved coordinates are always in
  the original image's pixel space, so zoom doesn't affect the output.
- All images are kept in `annotations.json`; ones with no boxes get `[]`.
- Tiny accidental drags (under a few pixels) are ignored.

## Files

- `annotate.py` — the application
- `raw_images/` — put your images here (`.jpg`, `.png`, `.bmp`, `.tif`, `.webp`, …)
- `annotations.json` — generated output, used to train the model in `../model.ipynb`
- `requirements.txt` — Python dependencies (Pillow)
- `run.command` — one-click launcher (macOS)

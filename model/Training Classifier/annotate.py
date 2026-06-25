#!/usr/bin/env python3
"""
Bounding-box annotation tool.

Loads images from ./raw_images, lets you draw boxes with click-drag, and saves
them to ./annotations.json in the format:

    {
        "tile_001.jpg": [[120, 80, 140, 100], [310, 150, 330, 170]],
        "tile_002.jpg": [[45, 200, 65, 220], [180, 280, 200, 300]]
    }

Each box is [x1, y1, x2, y2] (top-left and bottom-right) in ORIGINAL image
pixel coordinates, regardless of how the image is zoomed on screen.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import messagebox

try:
    from PIL import Image, ImageTk
except ImportError:
    sys.stderr.write(
        "Pillow is required. Install it with:  pip install Pillow\n"
    )
    sys.exit(1)


HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(HERE, "raw_images")
ANNOTATION_FILE = os.path.join(HERE, "annotations.json")
VALID_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp")

# A box must be at least this many pixels on a side to count (avoids stray clicks).
MIN_BOX_SIZE = 3
# Click within this many screen pixels of a box edge/corner to select it.
HIT_TOLERANCE = 6


class Annotator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Box Annotator")
        self.geometry("1100x800")
        self.minsize(640, 480)

        self.images = self._discover_images()
        if not self.images:
            messagebox.showerror(
                "No images",
                f"No images found in:\n{IMAGE_DIR}\n\n"
                f"Supported types: {', '.join(VALID_EXTS)}",
            )
            self.destroy()
            return

        # annotations: { filename: [[x1,y1,x2,y2], ...] } in original pixels.
        self.annotations = self._load_annotations()

        self.index = 0
        self.pil_image = None        # current PIL image (original size)
        self.tk_image = None         # current PhotoImage (scaled for display)
        self.scale = 1.0             # display_px = original_px * scale
        self.offset = (0, 0)         # top-left of image on canvas (x, y)
        self.canvas_items = []       # list of (canvas_rect_id, box_index)

        # In-progress drag state.
        self._drag_start = None      # (canvas_x, canvas_y)
        self._drag_rect = None       # temp canvas rect id

        self._dirty = False          # unsaved changes since last write

        self._build_ui()
        self._bind_events()
        self.after(50, self.load_current)

    # ---------- discovery / persistence ----------

    def _discover_images(self):
        if not os.path.isdir(IMAGE_DIR):
            return []
        names = [
            f for f in os.listdir(IMAGE_DIR)
            if f.lower().endswith(VALID_EXTS) and not f.startswith(".")
        ]
        names.sort()
        return names

    def _load_annotations(self):
        if not os.path.isfile(ANNOTATION_FILE):
            return {}
        try:
            with open(ANNOTATION_FILE, "r") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            messagebox.showwarning(
                "Could not read annotations",
                f"{ANNOTATION_FILE}\n\n{exc}\n\nStarting with an empty set.",
            )
            return {}
        # Normalize: ensure lists of 4-int lists.
        clean = {}
        for name, boxes in data.items():
            if not isinstance(boxes, list):
                continue
            good = []
            for b in boxes:
                if isinstance(b, (list, tuple)) and len(b) == 4:
                    good.append([int(round(v)) for v in b])
            clean[name] = good
        return clean

    def save(self, show_message=False):
        # Include every image, even those with no boxes (empty list).
        out = {name: self.annotations.get(name, []) for name in self.images}
        # Keep any annotations for images that are no longer in raw_images too.
        for name, boxes in self.annotations.items():
            if name not in out:
                out[name] = boxes
        try:
            with open(ANNOTATION_FILE, "w") as fh:
                json.dump(out, fh, indent=4)
                fh.write("\n")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self._dirty = False
        self._update_status()
        if show_message:
            messagebox.showinfo("Saved", f"Wrote {len(out)} image(s) to\n{ANNOTATION_FILE}")

    # ---------- UI ----------

    def _build_ui(self):
        toolbar = tk.Frame(self, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="\u25C0 Prev (A)", command=self.prev_image).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="Next (D) \u25B6", command=self.next_image).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="Undo (Ctrl+Z)", command=self.undo_box).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="Clear image", command=self.clear_current).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="Save (S)", command=lambda: self.save(show_message=True)).pack(side=tk.LEFT, padx=2, pady=2)

        self.canvas = tk.Canvas(self, bg="#202020", highlightthickness=0, cursor="tcross")
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.status = tk.Label(self, text="", anchor=tk.W, bd=1, relief=tk.SUNKEN,
                               font=("TkDefaultFont", 11))
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        # Right-click (and Control-click on macOS) deletes the box under cursor.
        self.canvas.bind("<ButtonPress-2>", self.on_delete_click)
        self.canvas.bind("<ButtonPress-3>", self.on_delete_click)
        self.canvas.bind("<Control-Button-1>", self.on_delete_click)

        self.bind("<Configure>", self.on_resize)

        self.bind("<Left>", lambda e: self.prev_image())
        self.bind("<Right>", lambda e: self.next_image())
        self.bind("a", lambda e: self.prev_image())
        self.bind("d", lambda e: self.next_image())
        self.bind("s", lambda e: self.save(show_message=True))
        self.bind("<Control-z>", lambda e: self.undo_box())
        self.bind("<Command-z>", lambda e: self.undo_box())

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- image loading / layout ----------

    @property
    def current_name(self):
        return self.images[self.index]

    @property
    def current_boxes(self):
        return self.annotations.setdefault(self.current_name, [])

    def load_current(self):
        path = os.path.join(IMAGE_DIR, self.current_name)
        try:
            self.pil_image = Image.open(path)
            self.pil_image.load()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not open image", f"{path}\n\n{exc}")
            self.pil_image = None
            return
        self.render()

    def _compute_layout(self):
        """Compute scale + offset to fit the original image inside the canvas."""
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        iw, ih = self.pil_image.size
        self.scale = min(cw / iw, ch / ih)
        # Never upscale past a sane limit, but allow some zoom for tiny tiles.
        self.scale = min(self.scale, 8.0)
        disp_w = max(int(iw * self.scale), 1)
        disp_h = max(int(ih * self.scale), 1)
        self.offset = ((cw - disp_w) // 2, (ch - disp_h) // 2)
        return disp_w, disp_h

    def render(self):
        self.canvas.delete("all")
        self.canvas_items = []
        if self.pil_image is None:
            return

        disp_w, disp_h = self._compute_layout()
        resample = Image.NEAREST if self.scale > 1 else Image.LANCZOS
        shown = self.pil_image.resize((disp_w, disp_h), resample)
        self.tk_image = ImageTk.PhotoImage(shown)
        ox, oy = self.offset
        self.canvas.create_image(ox, oy, anchor=tk.NW, image=self.tk_image)

        for i, box in enumerate(self.current_boxes):
            x1, y1, x2, y2 = self._img_to_canvas(box)
            rect = self.canvas.create_rectangle(
                x1, y1, x2, y2, outline="#00ff66", width=2, tags=("box",)
            )
            self.canvas.create_rectangle(
                x1, y1, x2, y2, outline="#003311", width=4
            )
            self.canvas.tag_lower(  # keep thin bright line on top
                rect
            )
            self.canvas.tag_raise(rect)
            self.canvas_items.append((rect, i))

        self._update_status()

    # ---------- coordinate transforms ----------

    def _img_to_canvas(self, box):
        ox, oy = self.offset
        x1, y1, x2, y2 = box
        return (
            ox + x1 * self.scale,
            oy + y1 * self.scale,
            ox + x2 * self.scale,
            oy + y2 * self.scale,
        )

    def _canvas_to_img(self, cx, cy):
        ox, oy = self.offset
        iw, ih = self.pil_image.size
        x = (cx - ox) / self.scale
        y = (cy - oy) / self.scale
        # Clamp into image bounds.
        x = min(max(x, 0), iw)
        y = min(max(y, 0), ih)
        return x, y

    # ---------- drawing ----------

    def on_press(self, event):
        if self.pil_image is None:
            return
        self._drag_start = (event.x, event.y)
        self._drag_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#ffcc00", width=2, dash=(4, 3)
        )

    def on_drag(self, event):
        if self._drag_rect is None:
            return
        x0, y0 = self._drag_start
        self.canvas.coords(self._drag_rect, x0, y0, event.x, event.y)

    def on_release(self, event):
        if self._drag_rect is None:
            return
        x0, y0 = self._drag_start
        x1, y1 = x0, y0
        x2, y2 = event.x, event.y
        self.canvas.delete(self._drag_rect)
        self._drag_rect = None
        self._drag_start = None

        # Convert to image coords and normalize so x1<x2, y1<y2.
        ix1, iy1 = self._canvas_to_img(x1, y1)
        ix2, iy2 = self._canvas_to_img(x2, y2)
        bx1, bx2 = sorted((ix1, ix2))
        by1, by2 = sorted((iy1, iy2))

        if (bx2 - bx1) < MIN_BOX_SIZE or (by2 - by1) < MIN_BOX_SIZE:
            return  # too small, ignore

        box = [int(round(bx1)), int(round(by1)), int(round(bx2)), int(round(by2))]
        self.current_boxes.append(box)
        self._dirty = True
        self.render()

    def on_delete_click(self, event):
        """Delete the topmost box whose edge is near the click."""
        if self.pil_image is None:
            return
        target = self._box_at(event.x, event.y)
        if target is None:
            return
        del self.current_boxes[target]
        self._dirty = True
        self.render()

    def _box_at(self, cx, cy):
        """Return index of the box under (cx, cy), or None. Prefers smallest."""
        best = None
        best_area = None
        for i, box in enumerate(self.current_boxes):
            x1, y1, x2, y2 = self._img_to_canvas(box)
            if (x1 - HIT_TOLERANCE <= cx <= x2 + HIT_TOLERANCE and
                    y1 - HIT_TOLERANCE <= cy <= y2 + HIT_TOLERANCE):
                area = (x2 - x1) * (y2 - y1)
                if best_area is None or area < best_area:
                    best, best_area = i, area
        return best

    # ---------- box ops ----------

    def undo_box(self):
        if self.current_boxes:
            self.current_boxes.pop()
            self._dirty = True
            self.render()

    def clear_current(self):
        if not self.current_boxes:
            return
        if messagebox.askyesno("Clear image",
                               f"Remove all {len(self.current_boxes)} box(es) "
                               f"from {self.current_name}?"):
            self.current_boxes.clear()
            self._dirty = True
            self.render()

    # ---------- navigation ----------

    def next_image(self):
        if self.index < len(self.images) - 1:
            self.save()  # autosave on navigation
            self.index += 1
            self.load_current()

    def prev_image(self):
        if self.index > 0:
            self.save()
            self.index -= 1
            self.load_current()

    # ---------- misc events ----------

    def on_resize(self, event):
        # Only re-render on canvas size changes, not every child event.
        if event.widget is self and self.pil_image is not None:
            self.render()

    def _update_status(self):
        if self.pil_image is None:
            self.status.config(text="")
            return
        iw, ih = self.pil_image.size
        dirty = " *unsaved*" if self._dirty else ""
        self.status.config(
            text=(
                f"[{self.index + 1}/{len(self.images)}]  {self.current_name}   "
                f"{iw}x{ih}px   zoom {self.scale:.2f}x   "
                f"boxes: {len(self.current_boxes)}{dirty}    "
                f"drag=draw  |  right/ctrl-click=delete  |  A/D=prev/next  "
                f"|  Ctrl+Z=undo  |  S=save"
            )
        )

    def on_close(self):
        self.save()
        self.destroy()


def main():
    app = Annotator()
    # If init failed (no images), the window is already destroyed.
    if app.winfo_exists():
        app.mainloop()


if __name__ == "__main__":
    main()

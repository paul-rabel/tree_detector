# To generate 2x the training data by mirroring images
import json
import os
import sys

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

def mirror(images: list, annotations: dict):

    for name in images:
        path = os.path.join(IMAGE_DIR, name)
        img = Image.open(path)
        horizontal_mirror = img.transpose(Image.FLIP_LEFT_RIGHT)
        horizontal_name = f"HFlip{name}"  

        width, height = horizontal_mirror.size
        
        boxes = annotations[name]
        annotations[horizontal_name] = [] # for new image (mirrored) entries
        for box in boxes:
            x1, y1, x2, y2 = box
            newX1 = width - x1
            newY1 = height - y1
            newX2 = width - x2
            newY2 = height - y2
            annotations[horizontal_name].append((newX1, newY1, newX2, newY2))
        
        # Save new image
        horizontal_saved_path = os.path.join(IMAGE_DIR, horizontal_name)
        horizontal_mirror.save(horizontal_saved_path)

def get_annotations():
    if not os.path.isfile(ANNOTATION_FILE):
        return {}

    with open(ANNOTATION_FILE, "r") as fh:
        data = json.load(fh)

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

def get_images():
    if not os.path.isdir(IMAGE_DIR):
        return []
    names = [
        f for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith(VALID_EXTS) and not f.startswith(".")
    ]
    names.sort()
    return names

def save(annotations: dict, images: list):
    # Include every image, even those with no boxes (empty list).
    out = {name: annotations.get(name, []) for name in images}

    try:
        with open(ANNOTATION_FILE, "w") as fh:
            json.dump(out, fh, indent=4)
            fh.write("\n")
    except OSError as exc:
        print("Save failed", str(exc))

def main():
    images = get_images()
    annotations = get_annotations()
    mirror(images, annotations)
    save(annotations, images)
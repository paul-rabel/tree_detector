# Server fixes — TODO (temporary)

Notes on making `server/server.py` actually call the model. Scratchpad; delete
when done.

Current blocking bugs recap:

- `import model.test_model as ml` fails — repo root isn't on `sys.path` when run
  from `server/`.
- `ml.inference(saved_path.name, ...)` passes a bare filename, not the path to
  the file in `server/captures/`.
- `load_model()` reads `"weights.pt"` relative to the process cwd (`server/`),
  but the file lives at `model/weights.pt`.
- Model is reloaded on every request (slow — rebuilds ResNet50 + reads 166 MB).
- Response returns raw tensors → not JSON-serializable, and wrong shape.

---

## 1. Make `test_model` importable

Options:

- **`sys.path` append (preferred):** one line at top of `server.py`, then import
  as a module. Needs `model/__init__.py` (or relies on 3.3+ namespace packages).

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import model.test_model as ml
```

- **Run from repo root:** no code change, just launch differently:
  `python -m server.server`.
- **Move/symlink** `test_model.py` next to `server.py`.
- **importlib (most self-contained, no launch assumptions):**

```python
import importlib.util
from pathlib import Path
_spec = importlib.util.spec_from_file_location(
    "test_model",
    Path(__file__).resolve().parent.parent / "model" / "test_model.py",
)
ml = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ml)
```

---

## 2. Fix the weights path

Key point: a relative path like `"weights.pt"` resolves against the process's
**current working directory**, NOT the directory of `test_model.py`. The server
starts in `server/`, so it looks for `server/weights.pt`. Options:

- **Anchor to `__file__` (preferred)** — in `test_model.py`:

```python
from pathlib import Path
WEIGHTS_PATH = Path(__file__).resolve().parent / "weights.pt"
# ...
model.load_state_dict(torch.load(WEIGHTS_PATH, weights_only=True))
```

- **Parameterize:** `load_model(weights_path)` and pass it from the server.
- **`os.chdir(model_dir)`** at startup — works, but fragile global side effect.
- **Env var:** `torch.load(os.environ["WEIGHTS"])` — flexible, but must be set.

Recommended combo: `sys.path` insert for #1 + `__file__`-anchored path for #2.

---

## 3. Pass the real capture path + load model once

- Pass the full path to inference, not the filename:
  `ml.inference(str(saved_path), model)` (or pass the `Path` directly).
- Load the model a single time at startup and reuse it for every request, rather
  than calling `load_model()` inside `do_POST`. E.g. build it in `main()` and
  hand it to the handler / store it as a module-level/global.

---

## 4. Convert tensor output to JSON

`predictions[0]` is a dict with `boxes` (Tensor[N,4]), `scores` (Tensor[N]),
`labels` (Tensor[N]). Move to CPU (required on MPS) and `.tolist()`, then filter:

```python
def to_detections(predictions, threshold=0.5):
    pred = predictions[0]
    boxes = pred["boxes"].cpu().tolist()    # -> [[x1, y1, x2, y2], ...]
    scores = pred["scores"].cpu().tolist()  # -> [float, ...]
    return [
        {"box": box, "score": score}
        for box, score in zip(boxes, scores)
        if score > threshold
    ]
```

Then in the handler:

```python
self._send_json(200, {"detections": to_detections(predictions)})
```

This yields the `[{ "box": [x1,y1,x2,y2], "score": ... }]` shape that
`background.js` expects; the extension computes the center from the box. Boxes
are already in screenshot-pixel space, so no rescaling is needed.

# Tree Detector — Detection Server

A small local HTTP server that the [Tree Detector Chrome extension](../extension)
talks to. It receives a screenshot of the OSM iD editor's aerial view, runs a
fine-tuned Faster R-CNN tree detector, and returns bounding boxes for the
extension to overlay.

```
extension  ──POST /detect (PNG + threshold)──▶  server.py  ──▶  Faster R-CNN
    ▲                                                │
    └────────────  detections JSON  ◀────────────────┘
```

## Requirements

- Python 3.10+
- [PyTorch](https://pytorch.org/) + torchvision
- Pillow
- Model weights at `../model/final_weights.pt` (loaded via `model/test_model.py`)

The server imports the model code from `../model/test_model.py`, which is added
to `sys.path` at startup, so no install/packaging of the model is needed.

## Running

```bash
python server.py
```

You should see:

```
Running on mps            # or cpu
Debug detection server running at http://localhost:8080/detect
Captures will be saved to .../server/captures
```

The model is loaded **once** at startup and reused for every request.

## API

### `POST /detect`

Request body:

```json
{
  "image": "data:image/png;base64,iVBORw0KGgo...",
  "threshold": 0.45
}
```

| Field | Required | Description |
| --- | --- | --- |
| `image` | yes | PNG screenshot as a `data:` URL (device-pixel resolution) |
| `threshold` | no | Minimum score to keep a detection (defaults to `DEFAULT_THRESHOLD`, `0.45`) |

Response:

```json
{
  "detections": [
    { "box": [x1, y1, x2, y2], "score": 0.92 },
    ...
  ]
}
```

Boxes are in the input image's pixel space (the full screenshot resolution), so
no rescaling is needed on the extension side. Errors return a non-200 status
with `{ "error": "..." }`.

### `OPTIONS /detect`

Answers the browser's CORS preflight. All responses send
`Access-Control-Allow-Origin: *`.

## Captures

Every received screenshot is written to `server/captures/capture-<timestamp>.png`
for debugging (so you can see exactly what the extension sent). This directory is
not committed; clear it whenever you like.

## Layout

| File | Role |
| --- | --- |
| `server.py` | HTTP server: decode → save → run model → return detections |
| `captures/` | Saved screenshots (generated at runtime) |

## Notes

- This runs over plain HTTP on `localhost` and is intended for **local
  development only**.
- The model dependency lives in `../model`. See that folder for training and the
  weights.

"""Detection server for the Tree Detector extension.

Pipeline per `POST /detect` request:

  1. Accepts `{ "image": "data:image/png;base64,...", "threshold": 0.45 }`
     (threshold optional).
  2. Saves the decoded screenshot to `server/captures/` so you can eyeball
     exactly what the extension captured.
  3. Runs the Faster R-CNN tree detector (model/test_model.py) and returns the
     boxes whose score is above the threshold.

Run it with the project venv: `python server.py`.
"""

import base64
import json
import struct
import http.server
import socketserver
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import model.test_model as ml

PORT = 8080
CAPTURE_DIR = Path(__file__).resolve().parent / "captures"
DEBUG = False


model = ml.load_model()

# Used when a request doesn't specify its own score threshold.
DEFAULT_THRESHOLD = 0.45


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Read (width, height) from a PNG byte string via its IHDR chunk.

    PNG layout: 8-byte signature, then the IHDR chunk whose data starts at byte
    16 with width and height as big-endian uint32s.
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG image")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def decode_data_url(data_url: str) -> bytes:
    """Strip a `data:image/...;base64,` prefix and return the raw bytes."""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    return base64.b64decode(data_url)


def to_detections(predictions, threshold):
    """Convert raw model output to JSON-friendly detections above `threshold`."""
    pred = predictions[0]
    boxes = pred["boxes"].cpu().tolist()    # -> [[x1, y1, x2, y2], ...]
    scores = pred["scores"].cpu().tolist()  # -> [float, ...]
    return [
        {"box": box, "score": score}
        for box, score in zip(boxes, scores)
        if score > threshold
    ]


class DetectHandler(http.server.BaseHTTPRequestHandler):
    # --- CORS helpers ------------------------------------------------------
    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802 (http.server naming)
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    # --- main route --------------------------------------------------------
    def do_POST(self) -> None:  # noqa: N802 (http.server naming)
        if self.path != "/detect":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            data_url = payload.get("image", "")
            if not data_url:
                self._send_json(400, {"error": "missing 'image'"})
                return

            image_bytes = decode_data_url(data_url)
            saved_path = self._save_capture(image_bytes)
            width, height = png_dimensions(image_bytes)

            if DEBUG:
                print(
                    f"[debug-server] saved {saved_path.name} "
                    f"({width}x{height}px, {len(image_bytes)} bytes)"
                )

            threshold = float(payload.get("threshold", DEFAULT_THRESHOLD))

            # the ml model:
            predictions = ml.inference(saved_path, model)
            ret = to_detections(predictions, threshold)

            # delete screenshots
            if not DEBUG:
                self._delete_captures(saved_path)

            # send back
            self._send_json(200, {"detections": ret})
        except Exception as err:  # debug server: surface everything
            print(f"[debug-server] error: {err}")
            self._send_json(500, {"error": str(err)})

    # --- helpers -----------------------------------------------------------
    def _save_capture(self, image_bytes: bytes) -> Path:
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = CAPTURE_DIR / f"capture-{stamp}.png"
        path.write_bytes(image_bytes)
        return path
    
    def _delete_captures(self, path: Path):
        path.unlink(missing_ok=True)

    def _send_json(self, status: int, body: dict) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args) -> None:  # quiet default request logging
        pass


def main() -> None:
    with socketserver.TCPServer(("", PORT), DetectHandler) as httpd:
        print(f"Debug detection server running at http://localhost:{PORT}/detect")
        print(f"Captures will be saved to {CAPTURE_DIR}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping server...")
            httpd.server_close()


if __name__ == "__main__":
    main()

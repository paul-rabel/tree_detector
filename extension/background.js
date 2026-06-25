// Where the detection server lives. Adjust if your server uses a different
// host/port/path or expects a different request/response shape.
const SERVER_URL = "http://localhost:8080/detect";

// captureVisibleTab can only run in the service worker, and only one capture
// at a time per window, so we serialize requests behind a single in-flight job.
let inFlight = false;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.action !== "captureAndDetect") return;

  // Drop overlapping requests; the map is still moving, a fresh one will come.
  if (inFlight) {
    sendResponse({ ok: false, error: "busy" });
    return false;
  }

  handleCaptureAndDetect(sender)
    .then((result) => sendResponse({ ok: true, ...result }))
    .catch((err) => sendResponse({ ok: false, error: String(err) }));

  // Keep the message channel open for the async response.
  return true;
});

async function handleCaptureAndDetect(sender) {
  inFlight = true;
  try {
    const windowId = sender?.tab?.windowId;
    const dataUrl = await chrome.tabs.captureVisibleTab(windowId, {
      format: "png",
    });

    // Score threshold is set in the popup and read fresh on every request, so
    // changing the slider takes effect on the next capture.
    const { threshold } = await chrome.storage.local.get({ threshold: 0.45 });

    // Request: { image: "data:image/png;base64,...", threshold: 0.45 }
    const res = await fetch(SERVER_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl, threshold }),
    });

    if (!res.ok) {
      throw new Error(`server responded ${res.status}`);
    }

    const json = await res.json();
    return { detections: normalizeDetections(json) };
  } finally {
    inFlight = false;
  }
}

// Accepts a few shapes and normalizes to:
//   [{ box: [x1, y1, x2, y2] | null, center: [cx, cy] | null, score: number }]
// All coordinates are in the captured image's pixel space.
function normalizeDetections(json) {
  const list = Array.isArray(json)
    ? json
    : json.detections || json.trees || json.predictions || [];

  return list.map((d) => {
    const box = d.box || d.bbox || null;
    let center = d.center || null;
    if (!center && Array.isArray(box) && box.length === 4) {
      center = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
    }
    if (!center && d.x != null && d.y != null) {
      center = [d.x, d.y];
    }
    return {
      box: Array.isArray(box) && box.length === 4 ? box : null,
      center: Array.isArray(center) && center.length === 2 ? center : null,
      score: d.score ?? d.confidence ?? null,
    };
  });
}

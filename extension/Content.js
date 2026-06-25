// Tree Detector content script.
//
// Flow: when the OSM map stops moving, ask the background worker to screenshot
// the tab and POST it to the detection server, then overlay the returned
// bounding boxes + center points on top of the map.

const SETTLE_MS = 700; // how long the map must be still before we capture
let enabled = true;
let settleTimer = null;

// ---------------------------------------------------------------------------
// Overlay
// ---------------------------------------------------------------------------

const overlay = document.createElement("div");
overlay.id = "tree-detector-overlay";
Object.assign(overlay.style, {
  position: "fixed",
  inset: "0",
  pointerEvents: "none",
  zIndex: "100000",
});
document.documentElement.appendChild(overlay);

function clearOverlay() {
  overlay.replaceChildren();
}

// Resolves only after the overlay's removal has actually been painted to the
// screen. We need this because captureVisibleTab() photographs whatever pixels
// are currently on screen, on a timeline that is NOT synced to our DOM updates.
//
// The catch: requestAnimationFrame fires its callback *just before* a paint, and
// the web platform exposes no "paint finished" event. So a single rAF only tells
// us a paint is *about* to happen, not that the overlay-clear has landed -- the
// screenshot can still catch the stale box (this is why only *some* captures
// showed it). Waiting for a second rAF means the browser has begun the frame
// *after* the clear was painted, which is our proof the clear is now on screen.
// Two rAFs is the standard idiom for "run after the next paint".
function nextPaint() {
  return new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  );
}

function renderDetections(detections) {
  clearOverlay();
  // Image is captured at device pixel resolution; convert back to CSS pixels.
  const dpr = window.devicePixelRatio || 1;

  for (const det of detections) {
    if (det.box) {
      const [x1, y1, x2, y2] = det.box;
      const box = document.createElement("div");
      Object.assign(box.style, {
        position: "absolute",
        left: `${x1 / dpr}px`,
        top: `${y1 / dpr}px`,
        width: `${(x2 - x1) / dpr}px`,
        height: `${(y2 - y1) / dpr}px`,
        border: "2px solid #1db954",
        boxSizing: "border-box",
      });
      overlay.appendChild(box);
    }

    if (det.center) {
      const [cx, cy] = det.center;
      const dot = document.createElement("div");
      Object.assign(dot.style, {
        position: "absolute",
        left: `${cx / dpr - 4}px`,
        top: `${cy / dpr - 4}px`,
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        background: "red",
      });
      overlay.appendChild(dot);
    }
  }
}

// ---------------------------------------------------------------------------
// Capture pipeline
// ---------------------------------------------------------------------------

async function captureAndDetect() {
  if (!enabled) return;

  // Hide our overlay so it doesn't end up inside the screenshot, then wait for
  // the clear to actually paint before asking the worker to capture.
  clearOverlay();
  await nextPaint();

  chrome.runtime.sendMessage({ action: "captureAndDetect" }, (response) => {
    if (chrome.runtime.lastError) {
      console.warn("[TreeDetector]", chrome.runtime.lastError.message);
      return;
    }
    if (!response?.ok) {
      if (response?.error !== "busy") {
        console.warn("[TreeDetector] detection failed:", response?.error);
      }
      return;
    }
    renderDetections(response.detections || []);
  });
}

function scheduleCapture() {
  if (!enabled) return;
  clearTimeout(settleTimer);
  settleTimer = setTimeout(captureAndDetect, SETTLE_MS);
}

// ---------------------------------------------------------------------------
// Movement detection
// ---------------------------------------------------------------------------

// Renderer-agnostic movement detection. Rather than watching a specific map
// library's DOM (the OSM iD editor doesn't use Leaflet, and we only care about
// the aerial view there), we treat any pan/zoom input gesture as "the view may
// have changed" and re-detect once things settle.
//
// Listeners are attached on window in the capture phase so we still see the
// events even if the map widget calls stopPropagation() on them in the bubble
// phase. The debounce in scheduleCapture() collapses a burst of events (e.g. a
// drag-pan) into a single capture once the gesture ends.
function watchMapMovement() {
  const events = [
    "wheel", // scroll-to-zoom
    "mouseup", // end of a drag-pan
    "pointerup",
    "touchend", // mobile pan/zoom
    "keyup", // arrow-key pan, +/- zoom
    "dblclick", // double-click zoom
  ];
  for (const evt of events) {
    window.addEventListener(evt, scheduleCapture, {
      capture: true,
      passive: true,
    });
  }

  // The iD editor reflects the current map view in the URL hash, so a hash
  // change is a reliable signal that the view moved (incl. programmatic moves).
  window.addEventListener("hashchange", scheduleCapture);
}

function init() {
  chrome.storage?.local.get({ enabled: true }, (data) => {
    enabled = data.enabled;
    if (enabled) scheduleCapture(); // initial detection on load
  });

  chrome.storage?.onChanged.addListener((changes) => {
    if (changes.enabled) {
      enabled = changes.enabled.newValue;
      if (enabled) scheduleCapture();
      else clearOverlay();
    }
  });

  watchMapMovement();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

// Tree Detector content script.
//
// When the OSM map settles after a pan or zoom, ask the background worker to
// screenshot the tab and send it to the detection server, then draw the
// returned bounding boxes and center points over the map. Clicking a center
// point plots a `natural=tree` node in the iD editor at that location.

const SETTLE_MS = 10; // idle time after a gesture before we capture
const DOT_HIT_PX = 30; // clickable diameter around a center point (forgives near-misses)
const DPR = () => window.devicePixelRatio || 1;

let enabled = true;
let settleTimer = null;

// Set while a tree is being plotted, to pause capture so the overlay isn't
// cleared out from under the user mid-action.
let suppressCapture = false;

// Set if the extension is reloaded while this tab stays open, which orphans the
// content script. The only fix is a page reload, so we stop working and say so.
let contextInvalidated = false;

// `chrome.runtime.id` is undefined once the content script is orphaned.
function extensionAlive() {
  try {
    return !!chrome.runtime?.id;
  } catch {
    return false;
  }
}

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

// Resolve after the next paint. captureVisibleTab() photographs whatever is
// currently on screen, so before capturing we clear the overlay and wait for
// that clear to land — otherwise the screenshot can include our own markers.
// A single requestAnimationFrame runs just before a paint; a second one runs
// after it, which is our signal that the clear is now visible.
function nextPaint() {
  return new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  );
}

// Draw one detection (bounding box + clickable center point) as a group so the
// whole suggestion can be removed at once when its tree is plotted.
function renderDetection(det) {
  const dpr = DPR();
  const group = document.createElement("div");
  Object.assign(group.style, {
    position: "absolute",
    inset: "0",
    pointerEvents: "none",
  });

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
    group.appendChild(box);
  }

  if (det.center) {
    const [cx, cy] = det.center;
    // A transparent hit area larger than the visible dot, so a near-miss still
    // registers. The overlay ignores pointer events; opt this target back in.
    const target = document.createElement("div");
    Object.assign(target.style, {
      position: "absolute",
      left: `${cx / dpr - DOT_HIT_PX / 2}px`,
      top: `${cy / dpr - DOT_HIT_PX / 2}px`,
      width: `${DOT_HIT_PX}px`,
      height: `${DOT_HIT_PX}px`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "50%",
      pointerEvents: "auto",
      cursor: "pointer",
    });
    target.title = "Click to plot a tree here";

    const dot = document.createElement("div");
    Object.assign(dot.style, {
      width: "10px",
      height: "10px",
      borderRadius: "50%",
      background: "red",
      pointerEvents: "none",
    });
    target.appendChild(dot);

    target.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      acceptSuggestion(det, group, dot);
    });
    group.appendChild(target);
  }

  overlay.appendChild(group);
}

function renderDetections(detections) {
  clearOverlay();
  detections.forEach(renderDetection);
}

// ---------------------------------------------------------------------------
// Capture pipeline
// ---------------------------------------------------------------------------

async function captureAndDetect() {
  if (!enabled || contextInvalidated) return;
  if (!extensionAlive()) {
    handleContextInvalidated();
    return;
  }

  // Hide our markers so they aren't part of the screenshot.
  clearOverlay();
  await nextPaint();

  try {
    chrome.runtime.sendMessage({ action: "captureAndDetect" }, (response) => {
      if (chrome.runtime.lastError) {
        console.warn(
          "[TreeDetector] messaging failed:",
          chrome.runtime.lastError.message
        );
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
  } catch (err) {
    // sendMessage throws synchronously when the context is gone.
    handleContextInvalidated(err);
  }
}

function handleContextInvalidated(err) {
  if (contextInvalidated) return;
  contextInvalidated = true;
  clearTimeout(settleTimer);
  console.warn(
    "[TreeDetector] Extension context invalidated — reload this OSM tab to " +
      "resume detection.",
    err?.message || err || ""
  );
}

function scheduleCapture() {
  if (!enabled || suppressCapture || contextInvalidated) return;
  clearTimeout(settleTimer);
  settleTimer = setTimeout(captureAndDetect, SETTLE_MS);
}

// ---------------------------------------------------------------------------
// Plotting a tree in the iD editor
// ---------------------------------------------------------------------------
//
// On openstreetmap.org/edit the iD editor runs inside a same-origin iframe
// (<iframe id="id-embed">), so we can drive its UI with synthetic events, the
// same steps a person takes to place a tree:
//   1. press "1" to enter "add a point" mode,
//   2. click the map at the detection's location to drop a node,
//   3. search "Tree" in the feature-type chooser and select it.
// The edit lands in iD's normal undo history, so it can be reverted with Ctrl+Z.
//
// This relies on iD's keyboard shortcut and DOM selectors, which are not a
// public API and may change with iD updates.

const ADD_POINT_DELAY_MS = 150; // let "add point" mode activate before clicking
const UI_WAIT_MS = 2500; // max wait for iD's async panels to appear

function getIdIframe() {
  return document.getElementById("id-embed") || document.querySelector("iframe");
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Poll until fn() returns something truthy, or resolve null on timeout.
function waitFor(fn, timeout = UI_WAIT_MS, interval = 60) {
  return new Promise((resolve) => {
    const start = Date.now();
    (function poll() {
      let value = null;
      try {
        value = fn();
      } catch {
        value = null;
      }
      if (value) return resolve(value);
      if (Date.now() - start >= timeout) return resolve(null);
      setTimeout(poll, interval);
    })();
  });
}

// Dispatch a keypress into the iframe. Events are built with the iframe's own
// constructors so any instanceof checks inside iD (a different realm) pass.
function pressKey(win, doc, key, code, keyCode) {
  for (const type of ["keydown", "keyup"]) {
    doc.dispatchEvent(
      new win.KeyboardEvent(type, {
        key,
        code,
        keyCode,
        which: keyCode,
        bubbles: true,
        cancelable: true,
        view: win,
      })
    );
  }
}

// Fire a full pointer + mouse click sequence at (x, y), in iframe-relative CSS
// pixels. iD reads the pointer position at click time to place the node.
function clickAt(win, doc, x, y) {
  const target = doc.elementFromPoint(x, y) || doc.body;
  const base = {
    bubbles: true,
    cancelable: true,
    composed: true,
    view: win,
    clientX: x,
    clientY: y,
    button: 0,
  };
  const pointer = { pointerId: 1, pointerType: "mouse", isPrimary: true };
  const sequence = [
    ["pointermove", win.PointerEvent, { ...base, ...pointer, buttons: 0 }],
    ["mousemove", win.MouseEvent, { ...base, buttons: 0 }],
    ["pointerdown", win.PointerEvent, { ...base, ...pointer, buttons: 1 }],
    ["mousedown", win.MouseEvent, { ...base, buttons: 1 }],
    ["pointerup", win.PointerEvent, { ...base, ...pointer, buttons: 0 }],
    ["mouseup", win.MouseEvent, { ...base, buttons: 0 }],
    ["click", win.MouseEvent, { ...base, buttons: 0 }],
  ];
  for (const [type, EventCtor, options] of sequence) {
    if (typeof EventCtor !== "function") continue;
    target.dispatchEvent(new EventCtor(type, options));
  }
}

// Set a value on iD's search input through the native setter so its "input"
// handler picks up the change.
function setInputValue(input, value) {
  const proto = input.ownerDocument.defaultView.HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (setter) setter.call(input, value);
  else input.value = value;
}

// Convert a detection center (screenshot device pixels) into a click position
// inside the iD iframe (iframe-relative CSS pixels).
function detectionToIframePoint(center, iframe) {
  const [cx, cy] = center;
  const rect = iframe.getBoundingClientRect();
  return { x: cx / DPR() - rect.left, y: cy / DPR() - rect.top };
}

async function plotTreeAt(center) {
  const iframe = getIdIframe();
  if (!iframe) throw new Error("iD iframe (#id-embed) not found");

  let win;
  let doc;
  try {
    win = iframe.contentWindow;
    doc = iframe.contentDocument;
  } catch {
    throw new Error("iD iframe is cross-origin; cannot inject events");
  }
  if (!win || !doc) throw new Error("iD iframe not accessible yet");

  const { x, y } = detectionToIframePoint(center, iframe);

  pressKey(win, doc, "1", "Digit1", 49);
  await delay(ADD_POINT_DELAY_MS);

  clickAt(win, doc, x, y);

  const search = await waitFor(() => doc.querySelector(".preset-search-input"));
  if (search) {
    setInputValue(search, "Tree");
    search.dispatchEvent(new win.Event("input", { bubbles: true }));
  }

  const button = await waitFor(() => {
    const buttons = [...doc.querySelectorAll(".preset-list-button")];
    const exact = buttons.find(
      (b) => b.querySelector(".label")?.textContent.trim().toLowerCase() === "tree"
    );
    return exact || buttons[0] || null;
  });
  if (!button) throw new Error("Tree preset not found in feature chooser");
  button.click();

  // Deselect the new node so the editor panel closes and the map is ready for
  // the next action — no need to manually click away.
  await delay(ADD_POINT_DELAY_MS);
  pressKey(win, doc, "Escape", "Escape", 27);
}

// Plot the tree for a suggestion. On success the suggestion is removed from the
// overlay; on failure the dot is restored so it can be retried.
async function acceptSuggestion(det, group, dot) {
  if (!det.center) return;

  suppressCapture = true;
  clearTimeout(settleTimer);
  dot.style.background = "#f5c518"; // in progress

  try {
    await plotTreeAt(det.center);
    group.remove();
  } catch (err) {
    console.warn("[TreeDetector] plot failed:", err);
    dot.style.background = "red";
  } finally {
    // Let iD settle before allowing gesture-triggered captures again.
    setTimeout(() => {
      suppressCapture = false;
    }, 1000);
  }
}

// ---------------------------------------------------------------------------
// Movement detection
// ---------------------------------------------------------------------------
//
// We re-detect on genuine pan/zoom gestures, but not on a plain click (which
// selects a feature or plots a tree). Pointer gestures only count once the
// pointer has moved past a small threshold; wheel, double-click, pan/zoom keys,
// and hash changes always count. Listeners use the capture phase so we still
// see events the map widget might stop from bubbling.

const DRAG_THRESHOLD_PX = 25; // min pointer travel to treat a gesture as a drag

const MOVEMENT_KEYS = new Set([
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "+",
  "-",
  "=",
  "_",
]);

let pointerStart = null;

function onPointerDown(e) {
  pointerStart = { x: e.clientX, y: e.clientY };
}

function onPointerUp(e) {
  if (!pointerStart) return;
  const dx = e.clientX - pointerStart.x;
  const dy = e.clientY - pointerStart.y;
  pointerStart = null;
  if (Math.hypot(dx, dy) >= DRAG_THRESHOLD_PX) scheduleCapture();
}

function onPointerCancel() {
  pointerStart = null;
}

function onMovementKeyUp(e) {
  if (MOVEMENT_KEYS.has(e.key)) scheduleCapture();
}

function attachMovementListeners(target) {
  const opts = { capture: true, passive: true };
  target.addEventListener("pointerdown", onPointerDown, opts);
  target.addEventListener("pointerup", onPointerUp, opts);
  target.addEventListener("pointercancel", onPointerCancel, opts);
  target.addEventListener("wheel", scheduleCapture, opts);
  target.addEventListener("dblclick", scheduleCapture, opts);
  target.addEventListener("keyup", onMovementKeyUp, opts);
  target.addEventListener("hashchange", scheduleCapture);
}

// Gestures happen inside the iD iframe, and DOM events don't cross the frame
// boundary, so we listen on the top window and inside the same-origin iframe.
function watchMapMovement() {
  attachMovementListeners(window);
  watchIframeMovement();
}

function watchIframeMovement() {
  const iframe = getIdIframe();
  if (!iframe) {
    // The iframe is injected after page load; retry until it exists.
    setTimeout(watchIframeMovement, 500);
    return;
  }

  const attach = () => {
    try {
      const win = iframe.contentWindow;
      // addEventListener de-dupes identical listeners, so re-attaching is safe.
      if (win) attachMovementListeners(win);
    } catch {
      // A cross-origin iframe would throw here; the OSM iD iframe is same-origin.
    }
  };

  attach();
  // A reload replaces the document and drops its listeners, so re-attach.
  iframe.addEventListener("load", attach);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

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

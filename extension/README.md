# Tree Detector — Chrome Extension

A Manifest V3 Chrome extension that detects trees on [OpenStreetMap](https://www.openstreetmap.org).
When you pan or zoom the map, it screenshots the viewport, sends it to a local
detection server, and overlays the returned bounding boxes and center points on
top of the map.

The detector is meant for **aerial/satellite imagery**, so use the OSM **iD
editor** (the "Edit" view, which shows Bing aerial tiles).

## How it works

1. **`Content.js`** (content script) watches for map movement. The iD editor
   keeps the map view (center and zoom) in the URL hash, so it re-detects
   whenever the hash changes via a `hashchange` listener — one signal that
   covers pans, zooms, and programmatic navigation alike.

   Because iD runs inside a same-origin `<iframe id="id-embed">` and the hash
   can change on either the top page or the iframe, the listener is attached on
   both the top `window` and the iframe's `contentWindow`. Once the view has
   been still for `10ms`, the script hides its overlay (so old markers aren't
   captured again), waits for that to paint, and then messages the service
   worker.
2. **`background.js`** (service worker) calls `chrome.tabs.captureVisibleTab()`
   — the screenshot API, which is only available in the background context, not
   in content scripts.
3. The screenshot is POSTed to the detection server and the JSON response is
   awaited.
4. The detections are relayed back to the content script and drawn as green
   boxes and red center dots over the map.
5. **`popup.html` / `popup.js`** provide an ON/OFF toggle and a **confidence
   threshold** slider, both persisted via `chrome.storage.local`. The threshold
   is read fresh on every request, so changing it takes effect on the next
   capture.

## Click-to-plot a tree

Each red center dot is a suggestion. Clicking one (or near it — the clickable
area is `DOT_HIT_PX` wide, so near-misses still register) plots a `natural=tree`
node in the iD editor at that location by driving iD's own UI:

1. Press **`1`** to enter "add a point" mode.
2. Click the map at the dot's location to drop a node.
3. Search **"Tree"** in the feature-type chooser and select it, tagging the node
   `natural=tree`.
4. Press **Escape** to deselect, so the node is committed and you can carry on
   without clicking away.

Because it uses the real editor, the edit appears on the map immediately and can
be undone with `Ctrl+Z`. While plotting, the dot turns yellow and detection is
paused so the overlay isn't cleared mid-action. Once the tree is placed, its
suggestion (box and dot) is removed from the overlay; if plotting fails, the dot
turns red again so it can be retried.

This depends on iD's `1` shortcut and its DOM selectors
(`.preset-search-input`, `.preset-list-button`), which are not a public API and
may change with iD updates — check these first in `Content.js` if plotting
breaks. The click position is `center / devicePixelRatio − iframeRect.topLeft`,
which assumes the iframe fills the viewport.

## Installation (development)

1. Open `chrome://extensions`.
2. Enable **Developer mode** (top-right).
3. Click **Load unpacked** and select this `extension/` folder.
4. Open the OSM **iD editor** (<https://www.openstreetmap.org/edit>), switch the
   background to aerial imagery if needed, and pan/zoom.


## Detection server contract

The server URL is configured at the top of `background.js`:

```js
const SERVER_URL = "http://localhost:8080/detect";
```

### Request

The extension sends a POST with a JSON body containing a base64 PNG data URL and
the current confidence threshold:

```json
{ "image": "data:image/png;base64,iVBORw0KGgo...", "threshold": 0.45 }
```

`threshold` is optional from the server's point of view (it falls back to a
default), but the extension always includes it.

### Response

The server should return detections in the screenshot's pixel space. Note the
image is captured at device resolution, i.e. `cssPixels * devicePixelRatio`.

```json
{
  "detections": [
    { "box": [x1, y1, x2, y2], "center": [cx, cy], "score": 0.92 }
  ]
}
```

The response parser is tolerant:

- The array may be keyed as `detections`, `trees`, or `predictions`, or be a
  bare top-level array.
- `bbox` is accepted as an alias for `box`.
- If `center` is omitted, it is computed from `box`.

### CORS

The server must send `Access-Control-Allow-Origin` (e.g. `*` or the OSM origin),
otherwise the browser will block the `fetch` request from the extension.

## Permissions

| Permission | Why |
| --- | --- |
| `tabs` | Access the active tab to screenshot it |
| `storage` | Persist the ON/OFF toggle and confidence threshold |
| `host_permissions: <all_urls>` | Required by `captureVisibleTab()` (a site-specific host permission is **not** sufficient), and also covers the `fetch` to `localhost:8080` |

## Files

| File | Role |
| --- | --- |
| `manifest.json` | Extension manifest (MV3) |
| `background.js` | Service worker: capture → POST → normalize response |
| `Content.js` | Movement detection + overlay rendering + click-to-plot |
| `popup.html` / `popup.js` | Toolbar popup: ON/OFF toggle + confidence slider |
| `assets/icon16.png` | Toolbar icon |
# Tree Detector — Chrome Extension

A Manifest V3 Chrome extension that detects trees on [OpenStreetMap](https://www.openstreetmap.org).
When you pan or zoom the map, it screenshots the viewport, sends it to a local
detection server, and overlays the returned bounding boxes and center points on
top of the map.

The detector is meant for **aerial/satellite imagery**, so use the OSM **iD
editor** (the "Edit" view, which shows Bing aerial tiles). The standard rendered
map uses stylized vector tiles where trees aren't drawn, so there's nothing for
the model to find there.

## How it works

1. **`Content.js`** (content script) detects map movement in a
   renderer-agnostic way: it listens for pan/zoom input gestures (`wheel`,
   `mouseup`/`pointerup`, `touchend`, `keyup`, `dblclick`) and `hashchange`
   events on `window`. This works in the iD editor, which doesn't use Leaflet.
   When the view has been still for `700ms`, it hides its own overlay (so old
   markers aren't captured again), waits for that clear to actually paint, and
   then messages the service worker.
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

## Installation (development)

1. Open `chrome://extensions`.
2. Enable **Developer mode** (top-right).
3. Click **Load unpacked** and select this `extension/` folder.
4. Open the OSM **iD editor** (<https://www.openstreetmap.org/edit>), switch the
   background to aerial imagery if needed, and pan/zoom.

> **Site access:** because `chrome.tabs.captureVisibleTab()` requires either the
> `<all_urls>` host permission or an `activeTab` user gesture, the manifest
> declares `<all_urls>`. After (re)loading the extension, make sure its **Site
> access** is set to **"On all sites"** (`chrome://extensions` → Details),
> otherwise automatic captures are blocked until you click the extension.

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

> `activeTab` is no longer relied upon for capturing — it only grants screenshot
> access right after a user gesture, which is why automatic captures failed
> before `<all_urls>` was added.

## Files

| File | Role |
| --- | --- |
| `manifest.json` | Extension manifest (MV3) |
| `background.js` | Service worker: capture → POST → normalize response |
| `Content.js` | Movement detection + overlay rendering |
| `popup.html` / `popup.js` | Toolbar popup: ON/OFF toggle + confidence slider |
| `assets/icon16.png` | Toolbar icon |

## Notes / limitations

- The screenshot includes OSM's own UI (zoom buttons, search bar, sidebar), not
  just the map tiles. If this interferes with detection, the screenshot can be
  cropped to the map element's bounds before sending.
- Captures are serialized: if the map is still moving while a request is in
  flight, overlapping requests are dropped and a fresh capture runs once it
  settles.

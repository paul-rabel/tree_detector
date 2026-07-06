# Tree Detector

Tree Detector enables you to plot trees in OpenStreetMap (OSM) extremely efficiently. Using a Faster R-CNN model, finetuned on satellite imagery of trees, Tree Detector suggests trees that a user can easily accept.

## Demo

![Demo Video of the Tree Detector](./README_media/tree_detector_demo_no_sidebar.gif)

## Installation

```bash
git clone URL
```

## Requirements

| Requirement | Simple Usage | More Training |
| --- | :---: | :---: |
| Chrome | ✅ | |
| Python 3.10+ | ✅ | ✅ |
| torch | ✅ | ✅ |
| torchvision | ✅ | ✅ |
| Pillow | ✅ | ✅ |
| numpy | | ✅ |
| pycocotools | | ✅ |
| Jupyter / Notebook | | ✅ |
| tkinter | | ✅ |

To install all (except Chrome & tkinter), run:
``` bash
pip install -r requirements.txt
```

## Simple Usage (no modifications / extra training)

1. Change to Developer Mode in Chrome Extensions
2. Upload (Load Unpack) `./extension`

![Upload Extension](./README_media/tree_detector_activate_extension.gif)

3. Activate the server (s.t. the browser extension can communicate with the backend)
```bash 
python server/server.py
```
4. Open OpenStreetMap and click the `Edit` button
4. Activate the browser extension in chrome
    - For best performance use zoom level $18 - 21$
    - Keep the left ID sidebar open - the tool needs it


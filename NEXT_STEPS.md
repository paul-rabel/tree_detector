# Next Steps

Planned work, captured for later. Nothing here is implemented yet.

## Capture accepted suggestions for fine-tuning

**Goal:** use the extension as a human-in-the-loop labeling tool. The model
proposes tree boxes, a human curates them, and the curated result is saved as
new training data to fine-tune the detector (active learning).

This breaks into two independent features.

### Feature A — Save / discard screenshots toggle

Add an option to keep or discard the screenshots the server receives.

- **Effort:** small (~15 min).
- **Sketch:** a checkbox in the popup → persisted to `chrome.storage.local` →
  sent in the `POST /detect` body → server skips `_save_capture()` when off.

Recommended save format: **PNG + a sidecar JSON** of the detections next to each
`capture-*.png`, so every saved frame carries the model output that produced it.
(A COCO-style export compatible with the existing training pipeline is a later
option.)

### Feature B — Record which suggestions were accepted

This is the valuable part, and the cost depends entirely on *how acceptance is
captured*. There is no accept interaction today — the overlay is passive
(`pointer-events: none`).

Options, cheapest to most involved:

1. **Corpus only (recommended first step).** Don't build accept UI yet. Just
   save `image + model-output JSON` pairs (Feature A) and re-annotate later with
   the existing `model/Training Classifier/annotate.py`. Decouples capturing
   from labeling. Effort: small.
2. **Interactive overlay.** Make the overlay clickable to accept/reject each box,
   add a submit action, and POST `{ image, accepted, rejected }` to a new server
   endpoint. Effort: moderate (a few hours).
3. **Full mini-annotator.** Accept/reject *and* draw boxes for trees the model
   missed. This is the only option that produces fine-tuning-safe labels (see
   caveat). Effort: largest.
4. **Tie to OSM edits.** Treat a suggestion as accepted when the user actually
   plots a tree node near it in the iD editor. Effort: hard / brittle (depends on
   iD's internal editing state).

### ⚠️ Caveat that drives the design

Object-detection training needs **complete** labels per image. If a saved frame
contains only the *accepted* boxes, then every real tree that wasn't boxed —
the model's misses and any false positives that are actually trees — becomes an
implicit "background" label. Training on that teaches the model to *suppress*
real trees and hurts recall.

So a fine-tuning-safe frame needs all three of:

1. Accepted suggestions (true positives),
2. Rejected suggestions removed (so false positives aren't learned as trees),
3. Boxes added for trees the model **missed**.

Requirement #3 is what turns Feature B from a thumbs-up/down widget into an
annotation tool — and is the main reason Option 1 (capture now, annotate later)
is the recommended starting point.

## Suggested order

1. Feature A (save toggle) + sidecar JSON.
2. Option 1 corpus collection during normal use.
3. Re-annotate the corpus with the existing tooling and fine-tune.
4. Revisit Options 2/3 only if in-browser annotation proves worth the effort.

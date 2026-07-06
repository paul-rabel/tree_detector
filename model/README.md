# Tree Detector Faster R-CNN

This folder includes several related files and folders:
- `model.ipynb`: A Python notebook to finetune the torchvision Faster R-CNN resnet50_fpn
    - The Faster R-CNN is finetuned with labeled satellite imagery.
    - The learned finetuned weights are saved in `final_weights.pt`.
- `test_model.py`: A Python script that loads the learned `final_weights.pt` and tests the finetuned Faster R-CNN model on images in `test_images`.
    - The functions `inference()` and `load_model()` are directly used during the application (see `server/server.py`).
- `Training Classifier`: This folder contains a program to manually label images in `Training Classifier/raw_images` such that they can be used in the `model.ipynb` Python notebook to learn `weights.pt`.
    - For more info see the dedicated `README.md` file in `Training Classifier`.
- `finetune_helpers`: The detection training/eval utilities imported by `model.ipynb`.
- `final_weights.pt`: The learned weights after finetuning both the classification layer of the model and the RPN layer.
- `weights.pt`: The learned weights after finetuning only the classification layer of the model.
- `test_images`: Folder with a few images to test the model on in `test_model`.

## Requirements
- Python 3.10+
- Inference only (what the server uses): `torch`, `torchvision`, `Pillow`
- Finetuning via `model.ipynb` additionally needs: `numpy`, `pycocotools`

```bash
pip install torch torchvision Pillow numpy pycocotools
```

A GPU is optional: the code uses Apple MPS when available, otherwise it
falls back to CPU.

## Running
- Decent weights are already provided. Thus, to run this project you do not need to run any code here.
- If you would like to generate your own weights / change optimization, `model.ipynb` contains thorough documentation on how to do so (simply follow the steps).